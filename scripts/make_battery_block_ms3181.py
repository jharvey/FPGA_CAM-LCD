#!/usr/bin/env python3
"""Aluminium battery end block for an MS3181-16 bayonet dust cap (MIL-DTL-26482 Series I, shell size 16).

Replaces the PG16-threaded ring of make_battery_block_step.py by a bayonet boss that copies the front shell
of an MS3112-16 receptacle: a 24.0 mm tube with three 2.4 mm pins, an O-ring in its end face, and the 19.2 mm
cell bore through it.  On-board flange 7 x 25 mm, two M1.6 tapped holes S1 / S2 (footprint FCL_BatteryBlock_Mount_MS3181), no dowel.

Contact stack inside the cap (outboard -> cell):  cap top | cap's own neoprene gasket (left whole) |
brass contact disc 24 x 0.8 (RTV-dotted to the gasket so it comes off with the cap) | Keystone 5220 coil spring
(solder lug soldered to the disc) | brass slug (17.5 mm tube, both ends closed) | cell - end.
The disc rim is clamped by the gasket onto the bare boss end face: that is the GND path (cap finish does not matter),
and the O-ring under the disc seals the bore.

PROVISIONAL (measure a real cap / spring and update): BOSS_D, CAP_*, PIN_X, PIN_ANG, SPRING_*.
Receptacle numbers: Milnec MS3112 datasheet (HM02), size 16: M = 1.000 in (25.4), U = 0.949 in (24.1).

Block frame ("board frame", mm): x = into the board from the board edge (outboard x < 0), y along the edge,
Z = 0 at the PCB back face, cell axis Z = -11.8.

    venv/bin/python scripts/make_battery_block_ms3181.py
"""
import math
import os
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "footprints", "fcl_local.3dshapes")
TMP = os.path.join(HERE, "..", "..", "tmp3d")

CZ = -11.8
# ---- on-board flange (unchanged from the PG16 block)
FL_X, FL_HALF, RELIEF = (-0.2, 7.0), 12.5, 0.5     # flat face 0.5 off the PCB: one 0.5 mm washer at each screw
SCREW, SCREW_DRILL, SCREW_DEPTH, BOSS_SCREW = (3.2, -10.3), 1.25, 5.5, 4.6     # S1: M1.6 tap drill 1.25
SCREW2 = (3.5, 9.3)                           # S2 (3.4 mm of metal over the cell bore at this depth)
PIN = {"A": (3.2, 6.25), "B": (3.2, 6.25)}      # one common block now: A and B are identical (names kept for the file names)
DOWEL_D, DOWEL_DEPTH, BOSS_DOWEL = 2.0, 3.0, 3.2
NOTCH = (4.3, 9.9, 4.0)
BORE = 19.2
# ---- outboard: shoulder plate + bayonet boss
PLATE_X, PLATE_HALF = (-3.0, -0.2), 14.0       # flush with the case outside (case wall at x = -3.0)
Z_BOT, Z_TOP = CZ - 14.0, CZ + 14.0            # -25.8 .. +2.2
BOSS_D = 24.0                                  # receptacle front shell OD (provisional)
BOSS_TIP = -13.5                               # boss end face (x)
PIN_D, PIN_R_OUT = 2.4, 13.4                   # bayonet pins, pressed through the boss wall, flush with the bore
PIN_X = -7.0
PIN_ANG = (90.0, 210.0, 330.0)                 # deg about the cell axis, 0 = +y, 90 = +Z (toward the PCB)
ORING = (10.8, 0.5)                            # face O-ring: centre radius, cross-section radius (20 x 1 mm)
GROOVE = (10.1, 11.5, 0.75)                    # groove r_in, r_out, depth
# ---- MS3181-16 cap (representative; Glenair table: D max 1.250 in = 31.8, height max 0.562 in = 14.3)
CAP_OD, CAP_ID, CAP_H, CAP_TOP, GASKET_T = 31.0, 24.4, 14.3, 2.0, 1.6
DISC_D, DISC_T = 24.0, 0.8
# ---- spring (Keystone 5220 class coil spring with solder lug) and slug
SPRING_H, SPRING_R0, SPRING_R1, SPRING_WIRE, SPRING_TURNS = 6.0, 6.0, 3.5, 0.7, 3.5
SLUG_D, SLUG_WALL = 17.5, 0.8
CELL_END = {"L": 12.2, "R": 85.0 - 77.2}       # cell - face in the block frame (right block is the same part turned)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def zcyl(x, y, d, z0, z1):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def xcyl(x0, x1, r, y=0.0, z=CZ):
    return cq.Workplane("YZ").circle(r).extrude(x1 - x0).translate((x0, y, z))


def xring(x0, x1, r_out, r_in):
    return xcyl(x0, x1, r_out).cut(xcyl(x0 - 0.01, x1 + 0.01, r_in))


def radial(x, ang, r0, r1, d):
    a = math.radians(ang)
    d3 = cq.Vector(0, math.cos(a), math.sin(a))
    p = cq.Vector(x, 0, CZ) + d3 * r0
    return cq.Workplane(obj=cq.Solid.makeCylinder(d / 2, r1 - r0, p, d3))


def make_block(variant):
    plate = box(*PLATE_X, -PLATE_HALF, PLATE_HALF, Z_BOT, Z_TOP)
    flange = box(*FL_X, -FL_HALF, FL_HALF, Z_BOT, -RELIEF)
    blk = plate.union(flange).union(xcyl(BOSS_TIP, PLATE_X[0] + 0.01, BOSS_D / 2))
    px, py = PIN[variant]
    blk = blk.cut(xcyl(BOSS_TIP - 1, FL_X[1] + 1, BORE / 2))
    blk = blk.cut(xring(BOSS_TIP - 0.01, BOSS_TIP + GROOVE[2], GROOVE[1], GROOVE[0]))     # O-ring groove
    for a in PIN_ANG:                                                                     # pin holes through the wall
        blk = blk.cut(radial(PIN_X, a, BORE / 2 - 0.5, BOSS_D / 2 + 0.5, PIN_D - 0.02))
    blk = blk.cut(zcyl(*SCREW, SCREW_DRILL, -SCREW_DEPTH, 0.5))
    blk = blk.cut(zcyl(*SCREW2, SCREW_DRILL, -SCREW_DEPTH, 0.5))
    return blk


def make_pins():
    return [radial(PIN_X, a, BORE / 2, PIN_R_OUT, PIN_D) for a in PIN_ANG]


def make_cap():
    top_out = BOSS_TIP - DISC_T - GASKET_T - CAP_TOP          # outer face of the cap top
    rim = top_out + CAP_H
    cap = xcyl(top_out, rim, CAP_OD / 2).cut(xcyl(top_out + CAP_TOP, rim + 1, CAP_ID / 2))
    # J-slots: axial entry from the rim, then 25 deg circumferential to the locked pin position
    for a in PIN_ANG:
        for k in range(0, 26, 1):
            cap = cap.cut(radial(PIN_X, a - k, CAP_ID / 2 - 0.5, CAP_OD / 2 + 0.5, PIN_D + 0.3))
        xs = PIN_X
        while xs < rim + 1.5:
            cap = cap.cut(radial(xs, a - 25, CAP_ID / 2 - 0.5, CAP_OD / 2 + 0.5, PIN_D + 0.3))
            xs += 0.4
    # knurl hint + lanyard eyelet on the top edge
    for i in range(24):
        cap = cap.cut(radial(top_out + 3.5, i * 15, CAP_OD / 2 - 0.4, CAP_OD / 2 + 1, 0.8))
    eye = cq.Workplane("XZ").center(top_out + 1.0, CZ - CAP_OD / 2 - 1.5).circle(2.6).circle(1.3).extrude(1.6).translate((0, 0.8, 0))
    cap = cap.union(eye)
    gasket = xcyl(top_out + CAP_TOP, top_out + CAP_TOP + GASKET_T, CAP_ID / 2 - 0.05)
    disc = xcyl(BOSS_TIP - DISC_T, BOSS_TIP, DISC_D / 2)
    return cap, gasket, disc


def make_oring():
    t = cq.Solid.makeTorus(ORING[0], ORING[1], cq.Vector(BOSS_TIP + ORING[1], 0, CZ), cq.Vector(1, 0, 0))
    return cq.Workplane(obj=t)


def make_spring():
    x0 = BOSS_TIP
    pitch = SPRING_H / SPRING_TURNS
    ang = -math.degrees(math.atan((SPRING_R0 - SPRING_R1) / SPRING_H))
    helix = cq.Wire.makeHelix(pitch, SPRING_H, SPRING_R0, center=cq.Vector(0, 0, 0), dir=cq.Vector(0, 0, 1), angle=ang)
    prof = cq.Workplane("XZ").center(SPRING_R0, 0).circle(SPRING_WIRE / 2)
    s = prof.sweep(cq.Workplane(obj=helix), isFrenet=True)
    s = s.rotate((0, 0, 0), (0, 1, 0), 90).translate((x0, 0, CZ))       # helix axis z -> +x
    lug = box(x0, x0 + 0.5, -2.5, 2.5, CZ + SPRING_R0 - 1.0, CZ + SPRING_R0 + 2.5)   # solder lug, flat on the disc, inside the bore
    return s.union(lug)


def make_slug(side):
    x0, x1 = BOSS_TIP + SPRING_H, CELL_END[side]
    tube = xring(x0, x1, SLUG_D / 2, SLUG_D / 2 - SLUG_WALL)
    return tube.union(xcyl(x0, x0 + SLUG_WALL, SLUG_D / 2)).union(xcyl(x1 - SLUG_WALL, x1, SLUG_D / 2))


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    for v in ("A", "B"):
        blk = make_block(v)
        s = blk.val()
        bb = s.BoundingBox()
        print(f"block {v}: solids {len(s.Solids())}, mass {s.Volume() / 1000 * 2.70:.1f} g (6061), "
              f"x {bb.xmin:.1f}..{bb.xmax:.1f} y {bb.ymin:.1f}..{bb.ymax:.1f} z {bb.zmin:.1f}..{bb.zmax:.1f}")
        cq.exporters.export(blk.mirror("XY"), os.path.join(OUT, f"FCL_BatteryBlock_MS3181_{v}.step"))
        cq.exporters.export(blk, os.path.join(TMP, f"blockms_{v}_boardframe.step"))
    cap, gasket, disc = make_cap()
    parts = {"cap": cap, "gasket": gasket, "disc": disc, "oring": make_oring(), "spring": make_spring(),
             "pins": cq.Workplane(obj=cq.Compound.makeCompound([p.val() for p in make_pins()]))}
    for side in ("L", "R"):
        parts["slug_" + side] = make_slug(side)
    for n, w in parts.items():
        cq.exporters.export(w, os.path.join(TMP, f"ms3181_{n}.step"))
        cq.exporters.export(w, os.path.join(TMP, f"ms3181_{n}.stl"), tolerance=0.03, angularTolerance=0.15)
    cq.exporters.export(make_block("A"), os.path.join(TMP, "ms3181_block.stl"), tolerance=0.03, angularTolerance=0.15)
    # clearances
    blk = make_block("A").val()
    for n in ("cap", "disc", "spring", "slug_L", "slug_R", "pins", "oring", "gasket"):
        v = blk.intersect(parts[n].val()).Volume()
        print(f"block x {n}: {v:.3f} mm3")
    print("cap x pins:", round(parts["cap"].val().intersect(parts["pins"].val()).Volume(), 3), "mm3")
    for side in ("L", "R"):
        print(f"slug {side}: length {CELL_END[side] - BOSS_TIP - SPRING_H:.1f} mm, mass "
              f"{parts['slug_' + side].val().Volume() / 1000 * 8.5:.1f} g brass")
    cb = parts["cap"].val().BoundingBox()
    print(f"cap x {cb.xmin:.1f}..{cb.xmax:.1f}, Z {cb.zmin:.1f}..{cb.zmax:.1f}")


if __name__ == "__main__":
    main()
