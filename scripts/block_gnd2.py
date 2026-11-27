#!/usr/bin/env python3
"""Block mount footprint: both screw holes are the same 3.0 mm GND pad with a 1.8 mm hole.

    flatpak run --command=python3 org.kicad.KiCad scripts/block_gnd2.py [S2_X]     (repo root, run once, after servo_block.py)

Screws go in from the camera side (the underside when the board lies block-up); the screw head on the GND ring
makes the electrical connection to the block.  Kapton tape between block and PCB, no washers.
S2 moves from x 3.1 to S2_X (default 3.5) so its pad clears the three edge tracks at cell 3 without moving them.
"""
import math
import re
import sys
import pcbnew

BOARD = "FCL.kicad_pcb"
LIB = "footprints/fcl_local.pretty"
NAME = "FCL_BatteryBlock_Mount_MS3181"
OX, OY = 78.0, 55.5
X2 = float(sys.argv[1]) if len(sys.argv) > 1 else 3.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM

p = f"{LIB}/{NAME}.kicad_mod"
s = open(p).read()
old = '(pad "" np_thru_hole circle (at 3.1 -9.3) (size 1.8 1.8) (drill 1.8) (layers "*.Cu" "*.Mask"))'
assert s.count(old) == 1, "already done?"
s = s.replace(old, f'(pad "1" thru_hole circle (at {X2} -9.3) (size 3.0 3.0) (drill 1.8) (layers "*.Cu" "*.Mask") (remove_unused_layers no))')
for a, b_ in (("(center 3.1 -9.3) (end 4.65 -9.3)", f"(center {X2} -9.3) (end {X2 + 1.55:.2f} -9.3)"),
              ("(center 3.1 -9.3) (end 4.60 -9.3)", f"(center {X2} -9.3) (end {X2 + 1.5:.2f} -9.3)"),
              ('(fp_text user "M1.6" (at 3.1 -9.3 0)', f'(fp_text user "M1.6" (at {X2} -9.3 0)')):
    assert s.count(a) == 1, a
    s = s.replace(a, b_)
s = re.sub(r'\(descr "[^"]*"\)',
           '(descr "Mount for the common FCL aluminium battery end block (MS3181-16 bayonet boss, 19.2 mm cell bore), flange 7 x 25 mm. '
           f'Two M1.6 screws, one each side of the cell: S1 (4.4, -9.7) and S2 ({X2}, +9.3) from the cell axis at the board edge. Both are '
           '3.0 mm GND pads with 1.8 mm holes. The screws go in from the camera side and thread into the block: the screw head on the GND '
           'ring is the electrical connection. Kapton tape between block and PCB. Same footprint at all three cells (cell 2: turned '
           '180 deg). Drawn mirrored in y for the back side.")', s, count=1)
open(p, "w").write(s)

b = pcbnew.LoadBoard(BOARD)
KEEP = []


def xy(q):
    return (round(mm(q.x) - OX, 3), round(mm(q.y) - OY, 3))


def near(a, c, tol=0.02):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


holes = []
for ref, expect in (("BT12", (4.4, 5.8)), ("BT32", (4.4, 46.8)), ("BT22", (80.6, 45.7))):
    old = b.FindFootprintByReference(ref)
    fields = {f.GetName(): f.GetText() for f in old.GetFields()}
    keep = (old.GetPath(), old.GetSheetname(), old.GetSheetfile(), old.GetPosition(), old.GetValue(), old.GetAttributes(),
            old.IsDNP(), old.GetOrientationDegrees())
    net = [q.GetNet() for q in old.Pads() if q.GetNumber()][0]
    KEEP.append(old)
    b.Remove(old)
    fp = pcbnew.FootprintLoad(LIB, NAME)
    KEEP.append(fp)
    b.Add(fp)
    fp.SetPosition(keep[3])
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    fp.SetOrientationDegrees(keep[7])
    assert any(near(xy(q.GetPosition()), expect) for q in fp.Pads()), ref
    fp.SetReference(ref)
    fp.SetValue(keep[4])
    fp.SetPath(keep[0])
    fp.SetSheetname(keep[1])
    fp.SetSheetfile(keep[2])
    fp.SetFPID(pcbnew.LIB_ID(pcbnew.UTF8("fcl_local"), pcbnew.UTF8(NAME)))
    fp.SetAttributes(keep[5])
    fp.SetDNP(keep[6])
    for k, v in fields.items():
        if k not in ("Reference", "Value", "Footprint"):
            fp.SetField(k, v)
    for f in fp.GetFields():
        if f.GetName() not in ("Reference", "Value"):
            f.SetVisible(False)
    for q in fp.Pads():
        q.SetNet(net)
        holes.append(xy(q.GetPosition()))
    print(ref, sorted(xy(q.GetPosition()) for q in fp.Pads()))
n = 0
for tr in list(b.GetTracks()):
    if tr.GetClass() == "PCB_VIA" and tr.GetNetname() == "GND":
        q = xy(tr.GetPosition())
        if any(math.hypot(q[0] - h[0], q[1] - h[1]) < 0.9 + 0.5 + 0.3 for h in holes):
            KEEP.append(tr)
            b.Remove(tr)
            n += 1
            print("  removed GND via at", q)
print("GND vias removed:", n)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
