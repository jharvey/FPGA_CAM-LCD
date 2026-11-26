#!/usr/bin/env python3
"""Dimensioned machining drawing (PDF + PNG) of the MS3181 battery end block, variants A and B.
All numbers come from make_battery_block_ms3181.py, so the drawing follows the model.

Drawing frame (datums):  A = mounting face (the two bosses that sit on the PCB),
B = inner face of the shoulder plate (faces the PCB edge), C = centre plane through the cell axis.
X from datum B (+ toward the board), Y from C, depth Z from A.

    venv/bin/python scripts/draw_battery_block.py      (repo root; writes docs/mech/)
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon, Arc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_battery_block_ms3181 as M   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "mech")
B0 = M.PLATE_X[1]                       # datum B in model x (-0.2)
X = lambda x: x - B0                   # model x -> drawing X (from datum B)
LW, THIN = 0.9, 0.35
DIMC = "#1f3f8f"
VER = "#b00020"                         # provisional dimensions
F = 6.0                                 # dimension text size


def ln(ax, x0, y0, x1, y1, lw=LW, ls="-", c="k"):
    ax.plot([x0, x1], [y0, y1], lw=lw, ls=ls, color=c, solid_capstyle="butt")


def center(ax, x0, y0, x1, y1):
    ln(ax, x0, y0, x1, y1, lw=0.3, ls=(0, (8, 2, 1, 2)), c="0.35")


def arrow(ax, p, q):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="<|-|>", lw=0.45, color=DIMC, shrinkA=0, shrinkB=0,
                                                    mutation_scale=5))


def dim_h(ax, xa, xb, y_obj, y_dim, text, ver=False, above=True):
    """horizontal dimension between xa and xb, extension lines from y_obj to y_dim"""
    for x in (xa, xb):
        ln(ax, x, y_obj, x, y_dim + (0.8 if y_dim > y_obj else -0.8), lw=0.3, c=DIMC)
    arrow(ax, (xa, y_dim), (xb, y_dim))
    ax.text((xa + xb) / 2, y_dim + (0.5 if above else -0.5), text, ha="center", va="bottom" if above else "top",
            fontsize=F, color=VER if ver else DIMC)


def dim_v(ax, ya, yb, x_obj, x_dim, text, ver=False):
    for y in (ya, yb):
        ln(ax, x_obj, y, x_dim + (0.8 if x_dim > x_obj else -0.8), y, lw=0.3, c=DIMC)
    arrow(ax, (x_dim, ya), (x_dim, yb))
    ax.text(x_dim - 0.5, (ya + yb) / 2, text, ha="right", va="center", rotation=90, fontsize=F,
            color=VER if ver else DIMC)


def leader(ax, p, t, text, ver=False, ha="left"):
    ax.annotate(text, xy=p, xytext=t, fontsize=F, color=VER if ver else DIMC, ha=ha, va="center",
                arrowprops=dict(arrowstyle="-|>", lw=0.45, color=DIMC, mutation_scale=5, shrinkA=1, shrinkB=0))


def hatch_rect(ax, x0, y0, x1, y1):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, hatch="////", lw=0, ec="0.55"))


# ------------------------------------------------------------------ views
def section_view(ax):
    """section C-C: plane through the cell axis (Y = 0); X right, Z up (datum A at Z = 0)"""
    zb, zt, cz = M.Z_BOT, M.Z_TOP, M.CZ
    rb, rboss = M.BORE / 2, M.BOSS_D / 2
    xt, xp0, xp1, xf1 = X(M.BOSS_TIP), X(M.PLATE_X[0]), 0.0, X(M.FL_X[1])
    rel = -M.RELIEF
    # solid regions above and below the bore (hatched)
    up = [(xt, cz + rb), (xt, cz + rboss), (xp0, cz + rboss), (xp0, zt), (xp1, zt), (xp1, rel), (xf1, rel), (xf1, cz + rb)]
    lo = [(xt, cz - rb), (xt, cz - rboss), (xp0, cz - rboss), (xp0, zb), (xf1, zb), (xf1, cz - rb)]
    for poly in (up, lo):
        ax.add_patch(Polygon(poly, closed=True, fill=False, hatch="////", ec="0.55", lw=0))
        ax.add_patch(Polygon(poly, closed=True, fill=False, ec="k", lw=LW))
    # O-ring groove (both sides)
    g0, g1, gd = M.GROOVE
    for s in (1, -1):
        ax.add_patch(Rectangle((xt, cz + s * g0 if s > 0 else cz - g1), gd, g1 - g0, fc="w", ec="k", lw=LW))
    # bayonet pin hole at 90 deg (top)
    xp = X(M.PIN_X)
    ax.add_patch(Rectangle((xp - M.PIN_D / 2, cz + rb), M.PIN_D, rboss - rb, fc="w", ec="k", lw=LW))
    center(ax, xp, cz + rb - 1, xp, cz + rboss + 1.5)
    center(ax, xt - 3, cz, xf1 + 3, cz)
    # dims
    dim_h(ax, xt, xf1, zt, zt + 6, f"{xf1 - xt:.1f}")
    dim_h(ax, xt, xp0, cz + rboss, zt + 2.5, f"{xp0 - xt:.1f}")
    dim_h(ax, xp0, xp1, zt, zt + 2.5, f"{xp1 - xp0:.1f}")
    dim_h(ax, xp1, xf1, rel, zt + 2.5, f"{xf1:.1f}")
    dim_h(ax, xt, xp, cz - rboss, zb - 3.0, f"{xp - xt:.1f} *", ver=True, above=False)
    dim_v(ax, cz - rb, cz + rb, xf1, xf1 + 4.5, f"⌀{M.BORE:.1f} THRU")
    dim_v(ax, cz - rboss, cz + rboss, xt, xt - 3.0, f"⌀{M.BOSS_D:.1f} *", ver=True)
    dim_v(ax, cz, 0.0, xf1, xf1 + 9.0, f"{-cz:.1f}")
    dim_v(ax, zb, zt, xt, xt - 9.0, f"{zt - zb:.1f}")
    dim_v(ax, rel, 0.0, xf1, xf1 + 13.0, f"{M.RELIEF:.1f}")
    ln(ax, xf1 - 2, 0.0, xf1 + 13.8, 0.0, lw=0.3, c=DIMC)
    leader(ax, (xt + gd / 2, cz + (g0 + g1) / 2), (xt + 1.0, zb - 9.0),
           f"O-RING GROOVE ⌀{2 * g0:.1f}/⌀{2 * g1:.1f} x {gd:.2f} DP\nfor O-ring {2 * (M.ORING[0] - M.ORING[1]):.0f} x {2 * M.ORING[1]:.0f}",
           ha="left")
    leader(ax, (xp, cz + rboss), (xp + 6, zt + 9.5), f"3x ⌀{M.PIN_D:.1f} THRU WALL *\n(see view on end)", ver=True)
    ax.text(xp1 + 0.3, zt + 0.6, "B", fontsize=7, fontweight="bold", bbox=dict(boxstyle="square,pad=0.15", fc="w", lw=0.6))
    ax.text(xf1 - 1.5, 0.6, "A", fontsize=7, fontweight="bold", bbox=dict(boxstyle="square,pad=0.15", fc="w", lw=0.6))
    ax.set_title("SECTION C-C  (through the cell axis)", fontsize=8, loc="left")


def end_view(ax):
    """view on the boss end (from outboard): Y horizontal, Z up"""
    cz, zb, zt, h = M.CZ, M.Z_BOT, M.Z_TOP, M.PLATE_HALF
    ax.add_patch(Rectangle((-h, zb), 2 * h, zt - zb, fill=False, lw=LW))
    for d, ls in ((M.BOSS_D, "-"), (M.BORE, "-"), (2 * M.GROOVE[0], "-"), (2 * M.GROOVE[1], "-")):
        ax.add_patch(Circle((0, cz), d / 2, fill=False, lw=LW if ls == "-" else THIN))
    center(ax, -h - 2, cz, h + 2, cz)
    center(ax, 0, zb - 2, 0, zt + 2)
    for a in M.PIN_ANG:
        r = math.radians(a)
        dy, dz = math.cos(r), math.sin(r)
        r0, r1 = M.BOSS_D / 2, M.PIN_R_OUT
        p0 = (r0 * dy, cz + r0 * dz)
        # pin (protrudes beyond the boss), drawn as a short bar
        px, pz = -dz * M.PIN_D / 2, dy * M.PIN_D / 2
        ax.add_patch(Polygon([(p0[0] + px, p0[1] + pz), (r1 * dy + px, cz + r1 * dz + pz), (r1 * dy - px, cz + r1 * dz - pz),
                              (p0[0] - px, p0[1] - pz)], closed=True, fc="0.85", ec="k", lw=THIN))
        center(ax, 0, cz, (r1 + 2) * dy, cz + (r1 + 2) * dz)
    ax.add_patch(Arc((0, cz), 30, 30, theta1=90, theta2=210, lw=0.4, color=DIMC))
    ax.text(-10.5, cz + 10.5, "120°", fontsize=F, color=VER)
    ax.add_patch(Arc((0, cz), 30, 30, theta1=330, theta2=450, lw=0.4, color=DIMC))
    ax.text(8.0, cz + 10.5, "120°", fontsize=F, color=VER)
    dim_h(ax, -h, h, zt, zt + 3, f"{2 * h:.1f}")
    dim_v(ax, zb, zt, -h, -h - 4, f"{zt - zb:.1f}")
    leader(ax, (M.PIN_R_OUT * math.cos(math.radians(330)), cz + M.PIN_R_OUT * math.sin(math.radians(330))), (h + 3, zb - 2),
           f"3x PIN ⌀{M.PIN_D:.1f} PRESS, PROTRUDE TO ⌀{2 * M.PIN_R_OUT:.1f} *\nINNER END FLUSH WITH BORE", ver=True)
    ax.text(0, zt + 6.5, "pin at 90° points to datum A (PCB side)", fontsize=5.2, ha="center", color="0.3")
    ax.set_title("VIEW ON BOSS END", fontsize=8, loc="left")


def face_view(ax, v):
    """view on mounting face A (from the PCB side): X right (into the board), Y up"""
    h, fh = M.PLATE_HALF, M.FL_HALF
    xt, xp0, xf1 = X(M.BOSS_TIP), X(M.PLATE_X[0]), X(M.FL_X[1])
    ax.add_patch(Rectangle((xp0, -h), -xp0, 2 * h, fill=False, lw=LW))                       # plate
    ax.add_patch(Rectangle((xt, -M.BOSS_D / 2), xp0 - xt, M.BOSS_D, fill=False, lw=LW))       # boss (silhouette)
    nx0, ny0 = X(M.NOTCH[0]), M.NOTCH[1]
    ax.add_patch(Polygon([(0, -fh), (xf1, -fh), (xf1, ny0), (nx0, ny0), (nx0, fh), (0, fh)], closed=True, fill=False, lw=LW))
    ax.add_patch(Rectangle((nx0, ny0), xf1 - nx0, fh - ny0, fill=False, lw=THIN, ls="--"))
    # flip: drawing Y = -model y so that variant A matches the PCB view from the camera side? keep model y, label it.
    sx, sy = X(M.SCREW[0]), M.SCREW[1]
    px, py = X(M.PIN[v][0]), M.PIN[v][1]
    ax.add_patch(Circle((sx, sy), M.BOSS_SCREW / 2, fill=False, lw=THIN))
    ax.add_patch(Circle((sx, sy), M.SCREW_DRILL / 2, fill=False, lw=LW))
    ax.add_patch(Circle((sx, sy), 1.25, fill=False, lw=THIN, ls=(0, (3, 1.5))))
    ax.add_patch(Circle((px, py), M.BOSS_DOWEL / 2, fill=False, lw=THIN))
    ax.add_patch(Circle((px, py), M.DOWEL_D / 2, fill=False, lw=LW))
    for (cx, cy) in ((sx, sy), (px, py)):
        center(ax, cx - 3.5, cy, cx + 3.5, cy)
        center(ax, cx, cy - 3.5, cx, cy + 3.5)
    center(ax, xt - 2, 0, xf1 + 2, 0)
    # dims from datum B (X = 0) and centre plane C (Y = 0)
    dim_h(ax, 0, sx, sy, -h - 3, f"{sx:.1f}", above=False)
    dim_h(ax, 0, px, py, h + 3, f"{px:.1f}")
    dim_h(ax, 0, xf1, -fh, -h - 7, f"{xf1:.1f}", above=False)
    dim_h(ax, 0, nx0, fh, h + 7, f"{nx0:.1f}")
    dim_v(ax, 0, sy, sx, xf1 + 4, f"{abs(sy):.1f}")
    dim_v(ax, 0, py, px, xf1 + 4, f"{py:.1f}")
    dim_v(ax, -fh, fh, xf1, xf1 + 10, f"{2 * fh:.1f}")
    dim_v(ax, ny0, fh, xf1, xf1 + 15.5, f"{fh - ny0:.1f}")
    leader(ax, (sx + 0.9, sy - 0.9), (sx + 9, sy - 9.5),
           f"M2.5x0.45 - 6H, DRILL ⌀{M.SCREW_DRILL:.2f} x {M.SCREW_DEPTH:.1f} DP\nTHREAD {M.SCREW_DEPTH - 0.5:.1f} MIN, BOSS ⌀{M.BOSS_SCREW:.1f}")
    leader(ax, (px + 0.7, py + 0.7), (px + 9, py + 8.5),
           f"⌀{M.DOWEL_D:.1f} H7 x {M.DOWEL_DEPTH:.1f} DP (dowel press)\nBOSS ⌀{M.BOSS_DOWEL:.1f}")
    leader(ax, ((nx0 + xf1) / 2, (ny0 + fh) / 2), (xf1 + 3, h + 12),
           f"POCKET {xf1 - nx0:.1f} x {fh - ny0:.1f}, {M.NOTCH[2]:.1f} DP FROM A\n(clears header pin tails)")
    ax.text(xt, -h - 12, f"FACE A RELIEVED {M.RELIEF:.1f} EXCEPT THE 2 BOSSES (tracks may run under it)", fontsize=5.5, ha="left", color=DIMC)
    ax.text(-2.6, -h - 3.4, "B", fontsize=7, fontweight="bold", bbox=dict(boxstyle="square,pad=0.15", fc="w", lw=0.6))
    ax.text(xt - 1.5, 0.9, "C", fontsize=7, fontweight="bold", bbox=dict(boxstyle="square,pad=0.15", fc="w", lw=0.6))
    ax.set_title(f"VIEW ON MOUNTING FACE A  -  VARIANT {v}", fontsize=8, loc="left")


def setup(ax, xlim, ylim):
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")


NOTES = """NOTES
1. MATERIAL: ALUMINIUM 6061-T6.  FINISH: ELECTROLESS NICKEL 5-8 um (conductive, solderable to ENIG pad contact).
   NO ANODIZE.  Boss end face (inside O-ring groove and outside it) is the GND contact face: Ra 0.8, flat 0.02, no burrs.
2. GENERAL TOLERANCES ISO 2768-mK.  Break all edges 0.2 x 45 deg except the boss end face (sharp, deburred).
3. DATUMS: A = mounting face (top of the 2 bosses), B = inner face of the shoulder plate, C = centre plane of the cell bore.
   Bore, boss and groove coaxial within 0.05 to each other.  Bore axis parallel to A within 0.05.
4. DIMENSIONS MARKED *  (red) ARE PROVISIONAL: verify against a real MS3181-16 cap / MS3112-16 receptacle front shell
   before machining (boss OD, bayonet pin axial position, angles, diameter and protrusion).
5. BAYONET PINS: 3x stainless dowel, pressed from outside, inner end flush with (or 0.1 below) the bore. Retain with
   Loctite 638 if a slip fit is used.
6. VARIANT A and B differ ONLY in the dowel hole Y position (A: +9.3, B: +7.5 from C). A is used twice
   (cell 1 on the left and, turned 180 deg, cell 2 on the right).  Mark the variant letter on face B.
7. 3D MODELS: FCL_BatteryBlock_MS3181_A_edit.step / _B_edit.step (origin = A n B n C).  Model governs if in doubt,
   except provisional dims (note 4).
"""


def sheet(variants=("A", "B")):
    os.makedirs(OUT, exist_ok=True)
    pdf_pages = []
    from matplotlib.backends.backend_pdf import PdfPages
    pdf = PdfPages(os.path.join(OUT, "FCL_BatteryBlock_MS3181_drawing.pdf"))
    for v in variants:
        fig = plt.figure(figsize=(16.54, 11.69))       # A3 landscape
        fig.patch.set_facecolor("white")
        a1 = fig.add_axes([0.03, 0.40, 0.40, 0.51])
        a2 = fig.add_axes([0.45, 0.40, 0.25, 0.55])
        a3 = fig.add_axes([0.70, 0.40, 0.29, 0.55])
        section_view(a1)
        setup(a1, (-26, 32), (-40, 18))
        end_view(a2)
        setup(a2, (-22, 30), (-40, 16))
        face_view(a3, v)
        setup(a3, (-18, 36), (-30, 30))
        fig.text(0.03, 0.04, NOTES, fontsize=7.2, family="monospace", va="bottom")
        # title block
        tb = fig.add_axes([0.70, 0.03, 0.28, 0.22])
        tb.axis("off")
        tb.add_patch(Rectangle((0, 0), 1, 1, fill=False, lw=1.2, transform=tb.transAxes))
        rows = [("PART", f"FCL battery end block, MS3181-16 bayonet - VARIANT {v}"),
                ("PART No.", f"FCL-MECH-BLK-MS3181-{v}"),
                ("QTY / UNIT", "2 (A: cell 1 + cell 2 right)" if v == "A" else "1 (B: cell 3)"),
                ("MATERIAL", "6061-T6 Al, electroless Ni"),
                ("MASS", "14.6 g"),
                ("UNITS / SCALE", "mm  /  NTS (dimensions govern)"),
                ("PROJECT", "FPGA_CAM-LCD monocular (branch battery-blocks)"),
                ("SOURCE", "scripts/make_battery_block_ms3181.py"),
                ("REV / DATE", "0.1 PROVISIONAL / 2026-11-26")]
        for i, (k, val) in enumerate(rows):
            y = 1 - (i + 0.5) / len(rows)
            tb.text(0.02, y, k, fontsize=6.5, va="center", transform=tb.transAxes, color="0.35")
            tb.text(0.27, y, val, fontsize=7.2, va="center", transform=tb.transAxes, fontweight="bold" if i == 0 else None)
            if i:
                tb.plot([0, 1], [1 - i / len(rows)] * 2, lw=0.3, color="0.6", transform=tb.transAxes)
        fig.text(0.03, 0.975, f"FCL battery end block (MS3181-16 bayonet) - variant {v}  -  dimensions in mm",
                 fontsize=11, fontweight="bold", va="top")
        pdf.savefig(fig)
        fig.savefig(os.path.join(OUT, f"FCL_BatteryBlock_MS3181_{v}_drawing.png"), dpi=110)
        plt.close(fig)
    pdf.close()
    print("wrote", os.path.abspath(OUT))


def export_edit_models():
    """STEP for editing in Onshape / IronCAD / Fusion: origin at A n B n C, X toward the board, Z up = away from A? no:
    Z = 0 on A, block below (negative Z), same as the drawing."""
    import cadquery as cq
    for v in ("A", "B"):
        blk = M.make_block(v).translate((-B0, 0, 0))
        cq.exporters.export(blk, os.path.join(OUT, f"FCL_BatteryBlock_MS3181_{v}_edit.step"))
        cq.exporters.export(blk, os.path.join(OUT, f"FCL_BatteryBlock_MS3181_{v}_edit.stl"), tolerance=0.02, angularTolerance=0.1)
    print("edit models written")


if __name__ == "__main__":
    sheet()
    export_edit_models()
