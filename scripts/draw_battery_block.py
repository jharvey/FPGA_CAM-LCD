#!/usr/bin/env python3
"""Dimensioned machining drawing (PDF + PNG) of the MS3181 battery end block (one part for all three cells).
All numbers come from make_battery_block_ms3181.py, so the drawing follows the model.

Drawing frame (datums):  A = PCB back face when mounted (0.5 above the flange face, set by the spacer washers),
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
    """view on the flange face (from the PCB side): X right (into the board), Y up"""
    h, fh = M.PLATE_HALF, M.FL_HALF
    xt, xp0, xf1 = X(M.BOSS_TIP), X(M.PLATE_X[0]), X(M.FL_X[1])
    ax.add_patch(Rectangle((xp0, -h), -xp0, 2 * h, fill=False, lw=LW))                       # plate
    ax.add_patch(Rectangle((xt, -M.BOSS_D / 2), xp0 - xt, M.BOSS_D, fill=False, lw=LW))       # boss (silhouette)
    ax.add_patch(Rectangle((0, -fh), xf1, 2 * fh, fill=False, lw=LW))                          # flange
    holes = [(X(M.SCREW[0]), M.SCREW[1], "S1"), (X(M.SCREW2[0]), M.SCREW2[1], "S2")]
    for (cx, cy, nm) in holes:
        ax.add_patch(Circle((cx, cy), M.SCREW_DRILL / 2, fill=False, lw=LW))
        ax.add_patch(Circle((cx, cy), 0.8, fill=False, lw=THIN, ls=(0, (3, 1.5))))            # M1.6 major diameter
        center(ax, cx - 3.0, cy, cx + 3.0, cy)
        center(ax, cx, cy - 3.0, cx, cy + 3.0)
        ax.text(cx + 1.4, cy + (1.2 if cy > 0 else -1.6), nm, fontsize=6.5, fontweight="bold")
    center(ax, xt - 2, 0, xf1 + 2, 0)
    (s1x, s1y, _), (s2x, s2y, _) = holes
    dim_h(ax, 0, s1x, s1y, -h - 3, f"{s1x:.1f}", above=False)
    dim_h(ax, 0, s2x, s2y, h + 3, f"{s2x:.1f}")
    dim_h(ax, 0, xf1, -fh, -h - 7, f"{xf1:.1f}", above=False)
    dim_v(ax, 0, s1y, s1x, xf1 + 4, f"{abs(s1y):.1f}")
    dim_v(ax, 0, s2y, s2x, xf1 + 4, f"{s2y:.1f}")
    dim_v(ax, -fh, fh, xf1, xf1 + 10, f"{2 * fh:.1f}")
    leader(ax, (s1x + 0.6, s1y - 0.6), (s1x - 14, s1y - 13.5),
           f"2x M1.6x0.35 - 6H (S1, S2)\nDRILL ⌀{M.SCREW_DRILL:.2f} x {M.SCREW_DEPTH:.1f} DP FROM THE FLANGE FACE\n"
           f"THREAD {M.SCREW_DEPTH - 1.0:.1f} MIN.  S2 MUST NOT BREAK INTO THE BORE")
    ax.text(xt, -h - 17, f"FLANGE FACE PLAIN, {M.RELIEF:.1f} BELOW DATUM A (0.5 SPACER WASHER AT EACH SCREW)",
            fontsize=5.5, ha="left", color=DIMC)
    ax.text(-2.6, -h - 3.4, "B", fontsize=7, fontweight="bold", bbox=dict(boxstyle="square,pad=0.15", fc="w", lw=0.6))
    ax.text(xt - 1.5, 0.9, "C", fontsize=7, fontweight="bold", bbox=dict(boxstyle="square,pad=0.15", fc="w", lw=0.6))
    ax.set_title("VIEW ON THE FLANGE FACE (PCB SIDE)", fontsize=8, loc="left")


def setup(ax, xlim, ylim):
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")


NOTES = """NOTES
1. MATERIAL: ALUMINIUM 6061-T6.  FINISH: ELECTROLESS NICKEL 5-8 um (conductive, solderable to ENIG pad contact).
   NO ANODIZE.  Boss end face (inside O-ring groove and outside it) is the GND contact face: Ra 0.8, flat 0.02, no burrs.
2. GENERAL TOLERANCES ISO 2768-mK.  Break all edges 0.2 x 45 deg except the boss end face (sharp, deburred).
3. DATUMS: A = PCB back face when mounted (flange face + 0.5, spacer washers), B = inner face of the shoulder plate,
   C = centre plane of the cell bore.
   Bore, boss and groove coaxial within 0.05 to each other.  Bore axis parallel to A within 0.05.
4. DIMENSIONS MARKED *  (red) ARE PROVISIONAL: verify against a real MS3181-16 cap / MS3112-16 receptacle front shell
   before machining (boss OD, bayonet pin axial position, angles, diameter and protrusion).
5. BAYONET PINS: 3x stainless dowel, pressed from outside, inner end flush with (or 0.1 below) the bore. Retain with
   Loctite 638 if a slip fit is used.
6. ONE PART FOR ALL THREE CELLS (cells 1 and 3 on the left, cell 2 on the right turned 180 deg).  Held by two
   M1.6 x 5 socket head screws from the camera side of the PCB into S1 / S2; the screw heads on the PCB's GND rings
   are the electrical connection.  No dowel, no pocket.
7. 3D MODEL: FCL_BatteryBlock_MS3181_edit.step (origin = A n B n C).  Model governs if in doubt,
   except provisional dims (note 4).
"""


def sheet(variants=("A",)):
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
        mass = M.make_block(v).val().Volume() / 1000 * 2.70
        rows = [("PART", "FCL battery end block, MS3181-16 bayonet"),
                ("PART No.", "FCL-MECH-BLK-MS3181"),
                ("QTY / UNIT", "3 (cells 1, 2, 3; cell 2 turned 180 deg)"),
                ("MATERIAL", "6061-T6 Al, electroless Ni"),
                ("MASS", f"{mass:.1f} g"),
                ("UNITS / SCALE", "mm  /  NTS (dimensions govern)"),
                ("PROJECT", "FPGA_CAM-LCD monocular (master)"),
                ("SOURCE", "scripts/make_battery_block_ms3181.py"),
                ("REV / DATE", "0.2 PROVISIONAL / 2026-11-26")]
        for i, (k, val) in enumerate(rows):
            y = 1 - (i + 0.5) / len(rows)
            tb.text(0.02, y, k, fontsize=6.5, va="center", transform=tb.transAxes, color="0.35")
            tb.text(0.27, y, val, fontsize=7.2, va="center", transform=tb.transAxes, fontweight="bold" if i == 0 else None)
            if i:
                tb.plot([0, 1], [1 - i / len(rows)] * 2, lw=0.3, color="0.6", transform=tb.transAxes)
        fig.text(0.03, 0.975, "FCL battery end block (MS3181-16 bayonet), one part for all three cells  -  dimensions in mm",
                 fontsize=11, fontweight="bold", va="top")
        pdf.savefig(fig)
        fig.savefig(os.path.join(OUT, "FCL_BatteryBlock_MS3181_drawing.png"), dpi=110)
        plt.close(fig)
    pdf.close()
    print("wrote", os.path.abspath(OUT))


def export_edit_models():
    """STEP for editing in Onshape / IronCAD / Fusion: origin at A n B n C, X toward the board, Z up = away from A? no:
    Z = 0 on A, block below (negative Z), same as the drawing."""
    import cadquery as cq
    blk = M.make_block("A").translate((-B0, 0, 0))
    cq.exporters.export(blk, os.path.join(OUT, "FCL_BatteryBlock_MS3181_edit.step"))
    cq.exporters.export(blk, os.path.join(OUT, "FCL_BatteryBlock_MS3181_edit.stl"), tolerance=0.02, angularTolerance=0.1)
    print("edit models written")


if __name__ == "__main__":
    sheet()
    export_edit_models()
