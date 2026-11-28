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
# Soft iron (manual mode only): steel near the sensor bends the field, so the readings lie on an ellipsoid, not a
#   sphere, and the heading error then changes with direction.  When the readings cover at least five of the six
#   directions, an ellipsoid is fitted as well, and a 3 x 3 matrix that turns it back into a sphere is stored with the
#   offset.  It is used only if it fits clearly better than the sphere and is no more squashed than 1.5 : 1.  A
#   sphere fit that misses the readings by more than 3 % is not stored: on a bent field its centre is wrong too.
#
# Not corrected: anything that changes with time, such as a servo motor or a current-carrying wire next to the sensor.
import math

SPACING = 45            # counts between kept readings (1 count = 1.5 mG; the earth's field is about 300 counts)
MAX_PTS = 60
MANUAL_PTS = 24             # readings before a manual calibration may finish by itself (the ellipsoid needs them)
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
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


def jacobi3(a):
    """eigenvalues and eigenvectors of a symmetric 3 x 3 matrix -> ([l0, l1, l2], V with the vectors as columns)"""
    a = [list(r) for r in a]
    v = [list(r) for r in IDENTITY]
    for _ in range(50):
        p, q = 0, 1
        for i, j in ((0, 2), (1, 2)):
            if abs(a[i][j]) > abs(a[p][q]):
                p, q = i, j
        if abs(a[p][q]) < 1e-12:
            break
        th = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, sn = math.cos(th), math.sin(th)
        for k in range(3):                                   # a = J^T a J, v = v J
            akp, akq = a[k][p], a[k][q]
            a[k][p], a[k][q] = c * akp - sn * akq, sn * akp + c * akq
        for k in range(3):
            apk, aqk = a[p][k], a[q][k]
            a[p][k], a[q][k] = c * apk - sn * aqk, sn * apk + c * aqk
        for k in range(3):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * vkp - sn * vkq, sn * vkp + c * vkq
    return [a[0][0], a[1][1], a[2][2]], v


def ellipsoid(pts):
    """fit x'Ax + 2b'x = 1 (in scaled coordinates) -> (centre, W, ratio, rms) with |W(m - centre)| = r for points on
    it, r the geometric mean of the semi-axes; or None"""
    n = len(pts)
    mean = [sum(p[i] for p in pts) / n for i in range(3)]
    s = 1.0 / 256.0
    N = [[0.0] * 9 for _ in range(9)]
    B = [0.0] * 9
    for p in pts:
        x, y, z = (p[0] - mean[0]) * s, (p[1] - mean[1]) * s, (p[2] - mean[2]) * s
        row = (x * x, y * y, z * z, 2 * x * y, 2 * x * z, 2 * y * z, 2 * x, 2 * y, 2 * z)
        for i in range(9):
            B[i] += row[i]
            for j in range(9):
                N[i][j] += row[i] * row[j]
    v = solve(N, B)
    if v is None:
        return None
    M = [[v[0], v[3], v[4]], [v[3], v[1], v[5]], [v[4], v[5], v[2]]]
    qc = solve([list(r) for r in M], [-v[6], -v[7], -v[8]])
    if qc is None:
        return None
    k = 1.0 + sum(qc[i] * M[i][j] * qc[j] for i in range(3) for j in range(3))
    if k <= 0:
        return None
    lam, V = jacobi3([[M[i][j] / k for j in range(3)] for i in range(3)])
    if min(lam) <= 0:
        return None
    axes = [1.0 / math.sqrt(l) / s for l in lam]               # semi-axes in counts
    r = (axes[0] * axes[1] * axes[2]) ** (1.0 / 3.0)
    d = [r / a for a in axes]                                  # W = V diag(r / axis) V'
    W = [[sum(V[i][m] * d[m] * V[j][m] for m in range(3)) for j in range(3)] for i in range(3)]
    c = [qc[i] / s + mean[i] for i in range(3)]
    err = 0.0
    for p in pts:
        u = [p[i] - c[i] for i in range(3)]
        w = [sum(W[i][j] * u[j] for j in range(3)) for i in range(3)]
        err += (math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2]) - r) ** 2
    return c, W, max(axes) / min(axes), math.sqrt(err / n) / r, r


class MagCal:
    def __init__(self, store=None):
        self.store = store              # object with load() -> dict or None, save(dict)
        self.off = [0.0, 0.0, 0.0]      # counts, subtracted from the raw reading
        self.radius = 0.0               # field strength found, counts
        self.rms = 0.0                  # fit error, fraction of the radius
        self.soft = [list(r) for r in IDENTITY]     # soft-iron matrix, applied after the offset
        self.ratio = 1.0                # how squashed the readings were: longest / shortest axis
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
                w = d.get("soft")
                if w and len(w) == 9:
                    self.soft = [[float(w[3 * i + j]) for j in range(3)] for i in range(3)]
                    self.ratio = float(d.get("ratio", 1.0))
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
            if self.seen == 0x3F and len(self.pts) >= MANUAL_PTS:
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
        prev = (list(self.off), [list(r) for r in self.soft], self.ratio, self.radius, self.rms, self.state)
        ok = len(self.pts) >= 12 and self._fit(prior=False)
        soft = len(self.pts) >= 12 and self.radius and self._soft_fit()
        if not soft and self.radius and self.rms > 0.03:
            # the readings are not on a sphere (bent field) and the ellipsoid could not be used: keep what was there
            self.off, self.soft, self.ratio, self.radius, self.rms, self.state = prev
            self.save()
            ok = False
        self.manual = False
        return bool(ok or soft)

    def _soft_fit(self):
        """after a manual sphere fit: replace the sphere by an ellipsoid if that fits clearly better"""
        n_dirs = sum(1 for i in range(6) if self.seen >> i & 1)
        e = ellipsoid(self.pts) if n_dirs >= 5 and len(self.pts) >= 20 else None
        if e is None:
            return False
        c, W, ratio, rms, r = e
        if ratio > 1.5 or not (R_MIN <= r <= R_MAX) or rms > 0.04 or self.rms < 0.01 or rms > 0.7 * self.rms:
            return False                                  # no better than the sphere, or not believable
        self.off, self.soft, self.ratio, self.rms, self.radius = c, W, ratio, rms, r
        self.state = "manual"
        self.changed = True
        self.save()
        return True

    def reset(self):
        self.off, self.radius, self.rms, self.pts, self.state = [0.0, 0.0, 0.0], 0.0, 0.0, [], "none"
        self.soft, self.ratio = [list(r) for r in IDENTITY], 1.0
        self.changed = True
        self.save()

    def save(self):
        if self.store:
            try:
                self.store.save({"off": [round(v, 1) for v in self.off], "radius": round(self.radius, 1), "auto": self.auto,
                                 "soft": [round(self.soft[i][j], 4) for i in range(3) for j in range(3)], "ratio": round(self.ratio, 3)})
            except Exception:
                pass

    def status(self):
        """the fields of a $M line: state, offset x y z (mG), field (mG), fit error %, readings, directions seen (manual),
        auto / fixed, soft-iron axis ratio (1.00 = none corrected)"""
        st = "manual-running" if self.manual else self.state
        seen = sum(1 for i in range(6) if self.seen >> i & 1)
        return "%s,%d,%d,%d,%d,%.1f,%d,%d,%s,%.2f" % (st, round(self.off[0] * 1.5), round(self.off[1] * 1.5), round(self.off[2] * 1.5),
                                                     round(self.radius * 1.5), self.rms * 100.0, len(self.pts), seen,
                                                     "auto" if self.auto else "fixed", self.ratio)
