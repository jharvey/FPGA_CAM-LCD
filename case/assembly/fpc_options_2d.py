"""To-scale 2D side section (cut on the optical axis) comparing TFT ribbon routings.
Pure Python + PIL (fast). Every ribbon centre line is exactly FPC_LEN long.
Frame: y = board y (mm from the top edge, down the page), z = height from the PCB back
face (negative = toward the eye, drawn to the right).
Run: python case/assembly/fpc_options_2d.py   ->  case/renders/fpc_options.png
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

FPC_LEN, STIFF, INSERT = 27.0, 5.5, 3.5
Y0, Z0 = 69.12, -21.54            # ribbon leaves the TFT here, heading +y
SLOT_Z = -1.0                     # ZIF slot height above the PCB back face
CELL = (56.5, -11.8, 9.3)         # cell 3 axis (y, z), radius
BOARD_END = 79.0


class Path:
    def __init__(self):
        self.p = [(Y0, Z0)]
        self.h = (1.0, 0.0)
        self.L = 0.0
        self.minr = 1e9

    def line(self, d):
        y, z = self.p[-1]
        n = max(1, int(d / 0.1))
        for k in range(1, n + 1):
            self.p.append((y + self.h[0] * d * k / n, z + self.h[1] * d * k / n))
        self.L += d
        return self

    def arc(self, r, deg, turn=1):
        if deg <= 0:
            return self
        self.minr = min(self.minr, r)
        y, z = self.p[-1]
        hy, hz = self.h
        cy, cz = y - hz * turn * r, z + hy * turn * r
        n = max(2, int(deg))
        for k in range(1, n + 1):
            a = math.radians(deg * k / n) * turn
            vy, vz = y - cy, z - cz
            self.p.append((cy + vy * math.cos(a) - vz * math.sin(a), cz + vy * math.sin(a) + vz * math.cos(a)))
        a = math.radians(deg) * turn
        self.h = (hy * math.cos(a) - hz * math.sin(a), hy * math.sin(a) + hz * math.cos(a))
        self.L += r * math.radians(deg)
        return self


def opt_wrap():
    """ribbon as a belt concentric with cell 3 (best case found by wrap_solve.py)"""
    p = Path().arc(1.04, 54.4).arc(15.99, 76.3).arc(1.07, 49.3)
    p.line(FPC_LEN - p.L)
    end = p.p[-1][0]
    return p, ("flat", end - INSERT + (FPC_LEN - p.L), -1)


def opt_flat():
    """flat ZIF, C-shape: fold, straight drop, fold, stiffener straight into J7"""
    r = (FPC_LEN - STIFF - (SLOT_Z - Z0)) / (math.pi - 2)
    p = Path().arc(r, 90).line(SLOT_Z - Z0 - 2 * r).arc(r, 90).line(STIFF)
    return p, ("flat", p.p[-1][0] + INSERT, -1), r


def opt_vertical(max_y=75.5, conn_half=1.8, conn_h=5.6, cell_clear=1.0):
    """vertical-entry ZIF: bend R (90+phi), short diagonal d, reverse bend R (phi), then the
    stiffened end straight (>= STIFF) down into the connector. Largest R that keeps the
    bulge inside max_y and the connector body clear of cell 3. Exact length by construction."""
    depth = SLOT_Z - Z0
    best = None
    for i in range(60, 200):
        R = i * 0.05
        if Y0 + R > max_y:
            break
        for j in range(4, 340):
            phi = math.radians(j * 0.25)
            d = (FPC_LEN - depth - R * (math.pi / 2 + 2 * phi) + R * (1 + 2 * math.sin(phi))) / (1 - math.cos(phi))
            st = FPC_LEN - R * (math.pi / 2 + 2 * phi) - d
            if d < 0 or st < STIFF:
                continue
            yc = Y0 + R * math.cos(phi) - d * math.sin(phi) - R * (1 - math.cos(phi))
            clr = math.hypot(yc - conn_half - CELL[0], -conn_h - CELL[1]) - CELL[2]
            if clr < cell_clear:
                continue
            if best is None or R > best[0]:
                best = (R, phi, d, st, yc, clr)
    R, phi, d, st, yc, clr = best
    p = Path().arc(R, math.degrees(phi) + 90).line(d).arc(R, math.degrees(phi), -1).line(st)
    return p, ("vert", yc, 0), R, dict(phi=math.degrees(phi), d=d, straight=st, yc=yc, cell_clear=clr)


# ---------------------------------------------------------------- drawing ----
S = 24                                  # px per mm
YMIN, YMAX, ZMAX, ZMIN = 43.0, 83.0, 5.0, -27.0
W, H = int((ZMAX - ZMIN) * S), int((YMAX - YMIN) * S)
PAD_TOP = 150


def font(sz, bold=False):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", sz)
    except OSError:
        return ImageFont.load_default()


def panel(title, sub, path, conn, notes, ok):
    im = Image.new("RGB", (W, H + PAD_TOP), "white")
    d = ImageDraw.Draw(im)
    X = lambda z: (ZMAX - z) * S
    Y = lambda y: (y - YMIN) * S + PAD_TOP
    box = lambda y0, y1, z0, z1, **k: d.rectangle([X(max(z0, z1)), Y(y0), X(min(z0, z1)), Y(y1)], **k)
    box(YMIN, BOARD_END, 0, 1.6, fill=(34, 120, 50), outline="black")                 # PCB
    d.text((X(1.5) - 2, Y(45)), "PCB", font=font(20, True), fill="white")
    for cy in (36.0, 56.5):                                                           # cells
        d.ellipse([X(CELL[1] + CELL[2]), Y(cy - CELL[2]), X(CELL[1] - CELL[2]), Y(cy + CELL[2])],
                  fill=(240, 150, 215), outline="black", width=2)
    d.text((X(-8.5), Y(55.5)), "18650", font=font(22, True), fill=(90, 20, 70))
    d.text((X(-8.5), Y(57.0)), "cell 3", font=font(20), fill=(90, 20, 70))
    box(YMIN, Y0, -21.6, -23.86, fill=(200, 105, 30), outline="black")                 # TFT
    d.text((X(-24.3), Y(52)), "T\nF\nT", font=font(20, True), fill="black")
    d.line([X(ZMAX), Y(BOARD_END), X(ZMIN), Y(BOARD_END)], fill=(150, 150, 150), width=1)
    d.text((X(-16), Y(BOARD_END) + 4), "board bottom edge", font=font(18), fill=(110, 110, 110))
    kind, cy, _ = conn                                                                  # connector
    if kind == "flat":
        op = cy                       # opening face; body extends 6.4 mm away from it
        direction = -1 if path.h[0] < 0 else 1
        y0, y1 = sorted((op, op + direction * 6.4))
        box(y0, y1, -2.09, 0, fill=(235, 235, 235), outline="black", width=2)
        d.text((X(-2.6), Y((y0 + y1) / 2) - 10), "J7 flat ZIF", font=font(19, True), fill="black")
    else:
        box(cy - 1.8, cy + 1.8, -5.6, 0, fill=(235, 235, 235), outline="black", width=2)
        d.text((X(-6.2), Y(cy) - 10), "J7 vertical ZIF", font=font(19, True), fill="black")
    # ribbon: flexible part orange, stiffened end brown
    acc, cut = 0.0, FPC_LEN - STIFF
    for a, b in zip(path.p, path.p[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        col, wd = ((230, 120, 0), 5) if acc + seg / 2 < cut else ((120, 60, 0), 9)
        d.line([X(a[1]), Y(a[0]), X(b[1]), Y(b[0])], fill=col, width=wd)
        acc += seg
    d.rectangle([0, 0, W, PAD_TOP - 8], fill=(232, 245, 233) if ok else (253, 232, 232))
    d.text((14, 10), title, font=font(30, True), fill="black")
    for i, s in enumerate(sub):
        d.text((14, 52 + i * 30), s, font=font(23), fill=(40, 40, 40))
    d.rectangle([0, H + PAD_TOP - 34 * len(notes) - 16, W, H + PAD_TOP], fill="white")
    for i, s in enumerate(notes):
        d.text((14, H + PAD_TOP - 34 * (len(notes) - i) - 8), s, font=font(22, i == 0),
               fill=(0, 110, 0) if ok else (180, 0, 0))
    d.rectangle([0, 0, W - 1, H + PAD_TOP - 1], outline=(120, 120, 120))
    return im


def main():
    pw, cw = opt_wrap()
    pf, cf, rf = opt_flat()
    pv, cv, rv, vi = opt_vertical()
    panels = [
        panel("A  Wrap centred on the battery", ["flat J7, original direction, moved under cell 3",
                                                 f"ribbon {pw.L:.1f} mm"], pw, cw,
              ["Does not fit well", "wrap R16 uses 21 mm -> R1.0 kinks at both ends",
               "and the 5.5 mm stiffener would have to bend"], False),
        panel("B  Flat J7, two folds", ["flat J7, original direction, moved 6.4 mm toward cells",
                                        f"ribbon {pf.L:.1f} mm, stiffener kept straight"], pf, cf,
              [f"Marginal: fold radius only {rf:.2f} mm",
               "depth alone uses 26.0 of the 27.0 mm"], False),
        panel("C  Vertical-entry J7", ["ribbon drops straight into a top-entry ZIF",
                                       f"ribbon {pv.L:.1f} mm, stiffener straight"], pv, cv,
              [f"Fits: bend radius {rv:.1f} mm (6x option B)",
               f"J7 at y {vi['yc']:.1f}, beside cell 3; ribbon stays {BOARD_END - max(q[0] for q in pv.p):.1f} mm inside the edge"], True),
    ]
    out = Image.new("RGB", (W * 3 + 40, H + PAD_TOP), "white")
    for i, p in enumerate(panels):
        out.paste(p, (i * (W + 20), 0))
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "renders", "fpc_options.png")
    out.save(dst)
    print("wrap  L=%.2f minR=%.2f end=%s" % (pw.L, pw.minr, [round(v, 2) for v in pw.p[-1]]))
    print("flat  L=%.2f R=%.3f opening=%.2f body to %.2f" % (pf.L, rf, cf[1], cf[1] - 6.4))
    print("vert  L=%.2f R=%.2f maxY=%.2f end=%s %s" % (
        pv.L, rv, max(q[0] for q in pv.p), [round(v, 2) for v in pv.p[-1]], {k: round(v, 2) for k, v in vi.items()}))
    print("saved", os.path.normpath(dst))


if __name__ == "__main__":
    main()
