#!/usr/bin/env python3
"""Aluminium battery end block (PG16 cell bore) - STEP models for fcl_local.3dshapes.

Variant A (BT12, cell 1) and B (BT32, cell 3) differ only in the dowel-pin hole (+9.3 / +7.5 mm from the
cell axis).  The same part A, turned 180 deg, is used on the right for cell 2.

Block frame ("board frame", mm): x = into the board from the board edge (ring outboard at x < 0),
y = along the board edge, + toward the bottom edge (board y grows downward), y = 0 on the cell axis,
Z = 0 at the PCB back face, negative = away from the PCB on the eye side.

    venv/bin/python scripts/make_battery_block_step.py          # writes both STEPs + a drawing-ready summary
"""
import os
import sys
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "footprints", "fcl_local.3dshapes")

CZ = -11.8              # cell axis
RING_X = (-6.5, -0.2)   # outboard threaded ring (beyond the board edge)
RING_HALF = 14.0        # 28 mm wide: seat for the 26 mm PG16 plug head
FL_X = (-0.2, 7.0)      # flange on the board
FL_HALF = 12.5
Z_BOT = CZ - RING_HALF  # -25.8
Z_TOP_RING = CZ + RING_HALF   # +2.2 (beyond the board edge only)
RELIEF = 0.6            # flange face stands 0.6 mm off the PCB except the bosses
TAP_DRILL_PG16 = 21.0   # PG16 tap drill; thread 22.5 x 18 TPI, cut with a PG16 tap
BORE = 19.2             # plain bore through the flange (18650 clearance)
SCREW = (4.4, -9.7)     # M2.5, from the PCB side
SCREW_DRILL, SCREW_DEPTH = 2.05, 5.5   # tap 5.0 deep (2 x d in 6061); deeper breaks into the cell bore
BOSS_SCREW = 4.6
PIN = {"A": (3.0, 9.3), "B": (3.0, 7.5)}
PIN_D, PIN_DEPTH, BOSS_PIN = 2.0, 3.5, 3.2
NOTCH = (4.0, 9.9, 4.0)  # x >= 4.0, y >= 9.9, 4 mm deep pocket for the servo-header pin tails


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def zcyl(x, y, d, z0, z1):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def make(variant):
    ring = box(*RING_X, -RING_HALF, RING_HALF, Z_BOT, Z_TOP_RING)
    flange = box(*FL_X, -FL_HALF, FL_HALF, Z_BOT, -RELIEF)
    blk = ring.union(flange)
    blk = blk.union(zcyl(*SCREW, BOSS_SCREW, -RELIEF - 0.01, 0.0))
    px, py = PIN[variant]
    blk = blk.union(zcyl(px, py, BOSS_PIN, -RELIEF - 0.01, 0.0))
    # notch for the servo-header pin tails (cut after the bosses so it also trims the pin boss edge)
    blk = blk.cut(box(NOTCH[0], FL_X[1] + 1, NOTCH[1], FL_HALF + 1, -NOTCH[2], 1.0))
    # bores along x
    blk = blk.cut(cq.Workplane("YZ").circle(TAP_DRILL_PG16 / 2).extrude(RING_X[1] - RING_X[0] + 0.02)
                  .translate((RING_X[0] - 0.01, 0, CZ)))
    blk = blk.cut(cq.Workplane("YZ").circle(BORE / 2).extrude(FL_X[1] - RING_X[0] + 1).translate((RING_X[0] - 0.5, 0, CZ)))
    # PG16 lead-in chamfer at the plug face
    blk = blk.cut(cq.Workplane("YZ").circle(TAP_DRILL_PG16 / 2 + 1.0).workplane(offset=1.0).circle(TAP_DRILL_PG16 / 2)
                  .loft().translate((RING_X[0] - 0.001, 0, CZ)))
    # tapped hole and pin hole from the PCB side
    blk = blk.cut(zcyl(*SCREW, SCREW_DRILL, -SCREW_DEPTH, 0.5))
    blk = blk.cut(zcyl(px, py, PIN_D, -PIN_DEPTH, 0.5))
    return blk


def check(blk, variant):
    s = blk.val()
    bb = s.BoundingBox()
    # minimum wall between the tapped hole (thread major dia 2.5) and the cell bore
    import math
    lat = abs(SCREW[1]) - 1.25          # thread major radius
    wall = math.hypot(lat, -SCREW_DEPTH - CZ) - BORE / 2
    px, py = PIN[variant]
    pwall = math.hypot(abs(py) - PIN_D / 2, -PIN_DEPTH - CZ) - BORE / 2
    print(f"variant {variant}: solids {len(s.Solids())}, volume {s.Volume() / 1000:.2f} cm3, "
          f"mass {s.Volume() / 1000 * 2.70:.1f} g (6061), bbox x {bb.xmin:.1f}..{bb.xmax:.1f} y {bb.ymin:.1f}..{bb.ymax:.1f} "
          f"z {bb.zmin:.1f}..{bb.zmax:.1f}; thread-to-bore wall {wall:.2f} mm, pin-hole-to-bore wall {pwall:.2f} mm")


def main():
    os.makedirs(OUT, exist_ok=True)
    for v in ("A", "B"):
        blk = make(v)
        check(blk, v)
        # KiCad mirrors a back-side model in z, so the footprint model is stored mirrored (z -> -z)
        cq.exporters.export(blk.mirror("XY"), os.path.join(OUT, f"FCL_BatteryBlock_PG16_{v}.step"))
        cq.exporters.export(blk, os.path.join(OUT, "..", "..", "..", "tmp3d", f"block_{v}_boardframe.step"))
    print("written to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
