# Compass calibration (hard iron): finds the constant offset that the batteries, speaker magnet and screws
# add to the magnetometer, by fitting a sphere to readings taken in different directions.
# Runs on the ESP32 (MicroPython) and on a PC.  Low rate (10 readings a second), so plain floats are fine.
#
# Automatic: readings are collected whenever the unit is used.  With only a level pan (a circle of readings) the
#   offset across the pan is found and the rest is left as it was; the more ways the unit has been pointed, the
#   more of the offset is known.  A fit is used only if it passes the checks in _fit().
# Manual: `magcal start`, then turn the unit to point up, down, north, south, east and west (any order);
#   it finishes by itself when all six have been seen, or on `magcal stop`.
# The result is stored (magcal.json on the ESP32) and loaded at the next start.
#
# Not corrected: soft iron (the sphere squashed into an ellipsoid) and anything that changes with time,
# such as a servo motor or a current-carrying wire next to the sensor.
import math

SPACING = 45            # counts between kept readings (1 count = 1.5 mG; the earth's field is about 300 counts)
MAX_PTS = 60
R_MIN, R_MAX = 120, 480     # plausible field strength in counts: 0.18 .. 0.72 gauss
MIN_SPAN = 180              # counts between the two readings furthest apart, before a fit is trusted
DIRS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def solve(a, b):
    """Gaussian elimination with pivoting; a: n x n list of lists (changed), b: list -> x, or None if singular"""
    n = len(b)
    for i in range(n):
        p = i
        for r in range(i + 1, n):
            if abs(a[r][i]) > abs(a[p][i]):
                p = r
        if abs(a[p][i]) < 1e-9:
            return None
        a[i], a[p] = a[p], a[i]
        b[i], b[p] = b[p], b[i]
        for r in range(i + 1, n):
            f = a[r][i] / a[i][i]
            if f:
                for c in range(i, n):
                    a[r][c] -= f * a[i][c]
                b[r] -= f * b[i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = b[i]
        for c in range(i + 1, n):
            s -= a[i][c] * x[c]
        x[i] = s / a[i][i]
    return x


class MagCal:
    def __init__(self, store=None):
        self.store = store              # object with load() -> dict or None, save(dict)
        self.off = [0.0, 0.0, 0.0]      # counts, subtracted from the raw reading
        self.radius = 0.0               # field strength found, counts
        self.rms = 0.0                  # fit error, fraction of the radius
        self.pts = []
        self.auto = True
        self.manual = False
        self.state = "none"             # none | auto | manual | stored
        self.seen = 0                   # manual: bit per direction seen
        self.new = 0
        self.changed = False
        if store:
            try:
                d = store.load()
            except Exception:
                d = None
            if d and len(d.get("off", ())) == 3:
                self.off = [float(v) for v in d["off"]]
                self.radius = float(d.get("radius", 0))
                self.auto = bool(d.get("auto", True))
                self.state = "stored"

    # ---- readings
    def add(self, x, y, z):
        """one raw reading (counts). Returns True when the offset has just changed."""
        if not (self.auto or self.manual):
            return False
        sp2 = SPACING * SPACING
        for p in self.pts:
            dx, dy, dz = x - p[0], y - p[1], z - p[2]
            if dx * dx + dy * dy + dz * dz < sp2:
                return False
        self.pts.append((x, y, z))
        if len(self.pts) > MAX_PTS:
            del self.pts[0]
        self.new += 1
        if self.manual:
            self._seen(x, y, z)
            if self.seen == 0x3F and len(self.pts) >= 12:
                return self.manual_stop()
            return False
        if self.new >= 6 and len(self.pts) >= 14:
            self.new = 0
            return self._fit(prior=True)
        return False

    def _seen(self, x, y, z):
        # direction of the reading from the best centre so far (the mean of the readings while none is known)
        n = len(self.pts)
        c = self.off if self.radius else [sum(p[i] for p in self.pts) / n for i in range(3)]
        v = (x - c[0], y - c[1], z - c[2])
        m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
        for i, d in enumerate(DIRS):
            if (v[0] * d[0] + v[1] * d[1] + v[2] * d[2]) / m > 0.75:        # within about 40 degrees
                self.seen |= 1 << i

    # ---- the fit:  |m|^2 = 2 m.c + k   with k = r^2 - |c|^2, least squares for c and k
    def _fit(self, prior):
        pts = self.pts
        n = len(pts)
        mean = [sum(p[i] for p in pts) / n for i in range(3)]
        s = 1.0 / 256.0                                          # scale so single-precision floats keep their digits
        A0 = [[0.0] * 4 for _ in range(4)]
        B0 = [0.0] * 4
        for p in pts:
            q = ((p[0] - mean[0]) * s, (p[1] - mean[1]) * s, (p[2] - mean[2]) * s)
            row = (2 * q[0], 2 * q[1], 2 * q[2], 1.0)
            rhs = q[0] * q[0] + q[1] * q[1] + q[2] * q[2]
            for i in range(4):
                B0[i] += row[i] * rhs
                for j in range(4):
                    A0[i][j] += row[i] * row[j]
        # Directions the readings do not cover (a level pan leaves one) keep the present offset: a weak pull of
        # the centre toward it.  Repeating the fit from its own result removes the pull where the readings do
        # speak, and leaves it where they say nothing.
        lam = n * 4.0 * (18.0 * s) ** 2
        prev = list(self.off)
        x = None
        for _ in range(4 if prior else 1):
            A = [list(r) for r in A0]
            B = list(B0)
            if prior:
                for i in range(3):
                    A[i][i] += lam
                    B[i] += lam * (prev[i] - mean[i]) * s
            x = solve(A, B)
            if x is None:
                return False
            prev = [x[i] / s + mean[i] for i in range(3)]
        c = [x[i] / s + mean[i] for i in range(3)]
        r2 = x[3] / (s * s) + sum((c[i] - mean[i]) ** 2 for i in range(3))
        if r2 <= 0:
            return False
        r = math.sqrt(r2)
        err = 0.0
        far = 0.0
        for p in pts:
            d = math.sqrt((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2)
            err += (d - r) ** 2
            far = max(far, math.sqrt((p[0] - pts[0][0]) ** 2 + (p[1] - pts[0][1]) ** 2 + (p[2] - pts[0][2]) ** 2))
        rms = math.sqrt(err / n) / r
        # checks: a believable field strength, readings that lie on the sphere, and enough of a turn: the readings
        # must span MIN_SPAN counts (about a quarter turn of a level pan; a pan only draws a small circle)
        if not (R_MIN <= r <= R_MAX) or rms > 0.08 or far < MIN_SPAN:
            if rms > 0.15 and not self.manual:
                del self.pts[:len(self.pts) // 2]                # something disturbed the field: forget the older half
            return False
        move = math.sqrt(sum((c[i] - self.off[i]) ** 2 for i in range(3)))
        self.radius, self.rms = r, rms
        if move < 3.0 and self.state != "none":
            return False
        self.off = c
        self.state = "manual" if self.manual else "auto"
        self.changed = True
        self.save()
        return True

    # ---- manual mode and housekeeping
    def manual_start(self):
        self.manual, self.seen, self.new = True, 0, 0
        self.pts = []

    def manual_stop(self):
        ok = len(self.pts) >= 12 and self._fit(prior=False)
        self.manual = False
        return ok

    def reset(self):
        self.off, self.radius, self.rms, self.pts, self.state = [0.0, 0.0, 0.0], 0.0, 0.0, [], "none"
        self.changed = True
        self.save()

    def save(self):
        if self.store:
            try:
                self.store.save({"off": [round(v, 1) for v in self.off], "radius": round(self.radius, 1), "auto": self.auto})
            except Exception:
                pass

    def status(self):
        """the fields of a $M line: state, offset x y z (mG), field (mG), fit error %, readings, directions seen (manual)"""
        st = "manual-running" if self.manual else self.state
        seen = sum(1 for i in range(6) if self.seen >> i & 1)
        return "%s,%d,%d,%d,%d,%.1f,%d,%d,%s" % (st, round(self.off[0] * 1.5), round(self.off[1] * 1.5), round(self.off[2] * 1.5),
                                                round(self.radius * 1.5), self.rms * 100.0, len(self.pts), seen,
                                                "auto" if self.auto else "fixed")
