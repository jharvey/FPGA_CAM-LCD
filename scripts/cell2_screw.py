#!/usr/bin/env python3
"""Block screw S1 moved so it fits at cell 2 next to the USB pair; both pads 2.6 mm; spacer washers again.

    flatpak run --command=python3 org.kicad.KiCad scripts/cell2_screw.py     (repo root, run once)

Runs on the board of commit 3b29091f (thermistor vias and VBAT_OR already moved by hand at cell 2).
Footprint FCL_BatteryBlock_Mount_MS3181 (same at all three cells):
    S1 (3.2, -10.3)   S2 (3.5, +9.3)   both 2.6 mm GND pads, 1.8 mm holes
Cell 2 (footprint turned 180 deg): S1 is at board (81.8, 46.3), between the USB pair and VBAT_OR.
    USB_DP / USB_DN jog 0.5 mm to the left from y 44 down to their diagonal
    CELL2_RAW (B.Cu) goes round the pad on the edge side, 0.8 mm wide for 4.6 mm
"""
import math
import re
import pcbnew

BOARD = "FCL.kicad_pcb"
LIB = "footprints/fcl_local.pretty"
NAME = "FCL_BatteryBlock_Mount_MS3181"
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
S1, S2, PAD, HOLE = (3.2, -10.3), (3.5, 9.3), 2.6, 1.8

# ---- 1. footprint
p = f"{LIB}/{NAME}.kicad_mod"
s = open(p).read()
assert "(at 4.4 9.7) (size 3.0 3.0)" in s, "footprint is not the 1895854a version"
s = re.sub(r"\t\(pad [^\n]*\n", "", s)
s = re.sub(r"\t\(fp_circle \(center (?:4\.4 9\.7|3\.5 -9\.3)\)[^\n]*\n", "", s)
s = re.sub(r'\t\(fp_text user "M1\.6" [^\n]*\n[^\n]*\n\t\)\n', "", s)
s = re.sub(r'\(descr "[^"]*"\)',
           '(descr "Mount for the common FCL aluminium battery end block (MS3181-16 bayonet boss, 19.2 mm cell bore), flange 7 x 25 mm. '
           f'Two M1.6 screws, one each side of the cell: S1 ({S1[0]}, {S1[1]}) and S2 ({S2[0]}, +{S2[1]}) from the cell axis at the board '
           f'edge. Both are {PAD} mm GND pads with {HOLE} mm holes. The screws go in from the camera side and thread into the block: the '
           'screw head on the GND ring connects the block. Flat block face 0.5 mm off the PCB: one 0.5 mm washer between block and PCB at '
           'each screw. Same footprint at all three cells (cell 2: turned 180 deg). Drawn mirrored in y for the back side.")', s, count=1)
add = ""
for x, yl in (S1, S2):
    y = -yl
    add += f'\t(fp_circle (center {x} {y}) (end {x + 1.55:.2f} {y}) (stroke (width 0.05) (type solid)) (fill no) (layer "B.CrtYd"))\n'
    add += f'\t(fp_circle (center {x} {y}) (end {x + 1.5:.2f} {y}) (stroke (width 0.1) (type solid)) (fill no) (layer "B.Fab"))\n'
    add += f'\t(fp_text user "M1.6" (at {x} {y} 0) (layer "B.Fab")\n\t\t(effects (font (size 0.6 0.6) (thickness 0.1)) (justify mirror))\n\t)\n'
    add += f'\t(pad "1" thru_hole circle (at {x} {y}) (size {PAD} {PAD}) (drill {HOLE}) (layers "*.Cu" "*.Mask") (remove_unused_layers no))\n'
i = s.index("\t(model ")
open(p, "w").write(s[:i] + add + s[i:])

# ---- 2. board
b = pcbnew.LoadBoard(BOARD)
KEEP, NEWSEG = [], []
fcu, bcu = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(q):
    return (round(mm(q.x) - OX, 3), round(mm(q.y) - OY, 3))


def near(a, c, tol=0.02):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


def take(net, layer, p0, p1):
    hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == net and t.GetLayer() == layer
           and ((near(xy(t.GetStart()), p0) and near(xy(t.GetEnd()), p1)) or (near(xy(t.GetStart()), p1) and near(xy(t.GetEnd()), p0)))]
    assert len(hit) == 1, (net, p0, p1, len(hit))
    KEEP.append(hit[0])
    b.Remove(hit[0])
    return mm(hit[0].GetWidth())


def add_track(net, layer, pts, w):
    for p0, p1 in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(V(*p0))
        t.SetEnd(V(*p1))
        t.SetWidth(MM(w))
        t.SetLayer(layer)
        t.SetNet(b.FindNet(net))
        b.Add(t)
        NEWSEG.append((p0, p1, w))


holes = []
for ref, expect in (("BT12", (3.5, 24.8)), ("BT32", (3.5, 65.8)), ("BT22", (81.5, 26.7))):
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
    assert any(near(xy(q.GetPosition()), expect) for q in fp.Pads()), (ref, [xy(q.GetPosition()) for q in fp.Pads()])
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

# ---- 3. cell 2: USB pair 0.5 mm to the left where it passes the pad
w = take("USB_DN", fcu, (80.3, 46.505), (80.3, 33.6))
take("USB_DN", fcu, (73.455, 53.35), (80.3, 46.505))
add_track("USB_DN", fcu, [(80.3, 33.6), (80.3, 43.9), (79.8, 44.4), (79.8, 47.005), (73.455, 53.35)], w)
w = take("USB_DP", fcu, (80.65, 33.455), (80.65, 46.65))
take("USB_DP", fcu, (80.65, 46.65), (73.6, 53.7))
add_track("USB_DP", fcu, [(80.65, 33.455), (80.65, 44.05), (80.15, 44.55), (80.15, 47.15), (73.6, 53.7)], w)

# ---- 4. cell 2: CELL2_RAW on B.Cu round the pad, on the edge side
w = take("/power/CELL2_RAW", bcu, (82.7, 63.7), (82.7, 35.35))
add_track("/power/CELL2_RAW", bcu, [(82.7, 35.35), (82.7, 44.0)], w)
add_track("/power/CELL2_RAW", bcu, [(82.7, 44.0), (83.75, 45.05), (83.75, 47.55), (82.7, 48.6)], 0.8)
add_track("/power/CELL2_RAW", bcu, [(82.7, 48.6), (82.7, 63.7)], w)


def seg_d(q, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    L = dx * dx + dy * dy
    u = 0 if L == 0 else max(0, min(1, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / L))
    return math.hypot(q[0] - a[0] - u * dx, q[1] - a[1] - u * dy)


# ---- 5. GND vias in the new holes or under the new tracks
n = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        q = xy(t.GetPosition())
        r = mm(t.GetWidth(pcbnew.F_Cu)) / 2
        if any(math.hypot(q[0] - h[0], q[1] - h[1]) < HOLE / 2 + 0.5 + r for h in holes) or \
           any(seg_d(q, p0, p1) < wd / 2 + 0.2 + r for p0, p1, wd in NEWSEG):
            KEEP.append(t)
            b.Remove(t)
            n += 1
            print("  removed GND via at", q)
print("GND vias removed:", n)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
