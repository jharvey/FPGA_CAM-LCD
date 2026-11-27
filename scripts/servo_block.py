#!/usr/bin/env python3
"""Servo headers moved right, one battery block mount footprint at all three cells.

    flatpak run --command=python3 org.kicad.KiCad scripts/servo_block.py     (repo root, run once, after block_m16.py)

1. J_SRV1..6 and R78..R83 move 3.5 mm to the right (2.54 mm pitch kept; J_SRV6 ends 0.7 mm short of J7).
2. Block mount footprint FCL_BatteryBlock_Mount_MS3181 (was ..._C1): outline is a plain 7 x 25 mm rectangle (the corner
   step is gone), screws S1 (4.4, -9.7) with a 3.0 mm GND pad and S2 (3.1, +9.3) as a bare hole, both M1.6 / 1.8 mm.
   The same footprint at BT12 (cell 1), BT32 (cell 3) and BT22 (cell 2, turned 180 deg).
3. Springs BT33 / BT23 back to the plain footprint (full lands).  VBAT_OR (F.Cu) at cell 2 straight again.
LEFT TO ROUTE BY HAND: cell 2, S1 at board (80.6, 45.7) (USB pair, TEMP_BAT_CELL1, +5V, VBAT_OR, CELL2_RAW).
"""
import math
import re
import pcbnew

BOARD, SCH = "FCL.kicad_pcb", "power.kicad_sch"
LIB = "footprints/fcl_local.pretty"
NAME = "FCL_BatteryBlock_Mount_MS3181"
OX, OY = 78.0, 55.5
D = 3.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM

# ---- 1. footprint: common name, square outline, S1 pad 3.0, S2 bare
s = open(f"{LIB}/{NAME}_C1.kicad_mod").read()
s = s.replace(f'"{NAME}_C1"', f'"{NAME}"', 1)
a = '(fp_poly (pts (xy 0 -12.5) (xy 4 -12.5) (xy 4 -9.9) (xy 7 -9.9) (xy 7 12.5) (xy 0 12.5))'
assert s.count(a) == 1
s = s.replace(a, '(fp_poly (pts (xy 0 -12.5) (xy 7 -12.5) (xy 7 12.5) (xy 0 12.5))')
c = '(fp_poly (pts (xy 0 -12.6) (xy 3.95 -12.6) (xy 3.95 -9.85) (xy 7.1 -9.85) (xy 7.1 12.6) (xy 0 12.6))'
assert s.count(c) == 1
s = s.replace(c, '(fp_poly (pts (xy 0 -12.6) (xy 7.1 -12.6) (xy 7.1 12.6) (xy 0 12.6))')
p1 = '(pad "1" thru_hole circle (at 4.4 9.7) (size 4.0 4.0) (drill 1.8) (layers "*.Cu" "*.Mask") (remove_unused_layers no))'
p2 = '(pad "1" thru_hole circle (at 2.6 -9.3) (size 4.0 4.0) (drill 1.8) (layers "*.Cu" "*.Mask") (remove_unused_layers no))'
assert s.count(p1) == 1 and s.count(p2) == 1
s = s.replace(p1, p1.replace("(size 4.0 4.0)", "(size 3.0 3.0)"))
s = s.replace(p2, '(pad "" np_thru_hole circle (at 3.1 -9.3) (size 1.8 1.8) (drill 1.8) (layers "*.Cu" "*.Mask"))')
for old_, new_ in (("(center 2.6 -9.3) (end 4.15 -9.3)", "(center 3.1 -9.3) (end 4.65 -9.3)"),
                   ("(center 2.6 -9.3) (end 4.10 -9.3)", "(center 3.1 -9.3) (end 4.60 -9.3)"),
                   ('(fp_text user "M1.6" (at 2.6 -9.3 0)', '(fp_text user "M1.6" (at 3.1 -9.3 0)')):
    assert s.count(old_) == 1, old_
    s = s.replace(old_, new_)
s = re.sub(r'\(descr "[^"]*"\)',
           '(descr "Mount for the common FCL aluminium battery end block (MS3181-16 bayonet boss, 19.2 mm cell bore), flange 7 x 25 mm. '
           'Two M1.6 screws, one each side of the cell: S1 (4.4, -9.7) with a GND pad and S2 (3.1, +9.3), a bare hole, from the cell axis '
           'at the board edge. 1.8 mm holes. Same footprint at all three cells (cell 2: turned 180 deg). Flat block face 0.5 mm off the '
           'PCB: one 0.5 mm washer between block and PCB at each screw. Drawn mirrored in y for the back side.")', s, count=1)
open(f"{LIB}/{NAME}.kicad_mod", "w").write(s)

# ---- 2. schematic: footprint names
t = open(SCH).read()
for k in ("C1", "C3", "R"):
    assert t.count(f'"fcl_local:{NAME}_{k}"') == 1, k
    t = t.replace(f'"fcl_local:{NAME}_{k}"', f'"fcl_local:{NAME}"')
assert t.count('"fcl_local:BAT-TH_MY-18650-05-J_LM"') == 2
t = t.replace('"fcl_local:BAT-TH_MY-18650-05-J_LM"', '"fcl_local:BAT-TH_MY-18650-05-J"')
open(SCH, "w").write(t)

# ---- 3. board
b = pcbnew.LoadBoard(BOARD)
KEEP = []
fcu = b.GetLayerID("F.Cu")


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(p):
    return (round(mm(p.x) - OX, 3), round(mm(p.y) - OY, 3))


def near(a, c, tol=0.02):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


NEWSEG = []


def add(net, layer, pts, w):
    for p0, p1 in zip(pts, pts[1:]):
        tr = pcbnew.PCB_TRACK(b)
        tr.SetStart(V(*p0))
        tr.SetEnd(V(*p1))
        tr.SetWidth(MM(w))
        tr.SetLayer(layer)
        tr.SetNet(b.FindNet(net))
        b.Add(tr)
        NEWSEG.append((p0, p1, w))




def swap(ref, name, expect):
    old = b.FindFootprintByReference(ref)
    fields = {f.GetName(): f.GetText() for f in old.GetFields()}
    keep = (old.GetPath(), old.GetSheetname(), old.GetSheetfile(), old.GetPosition(), old.GetValue(), old.GetAttributes(),
            old.IsDNP(), old.GetOrientationDegrees())
    net = [p.GetNet() for p in old.Pads() if p.GetNumber()][0]
    KEEP.append(old)
    b.Remove(old)
    fp = pcbnew.FootprintLoad(LIB, name)
    KEEP.append(fp)
    b.Add(fp)
    fp.SetPosition(keep[3])
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    for ang in (keep[7], 0, 90, 180, 270):
        fp.SetOrientationDegrees(ang)
        if any(near(xy(p.GetPosition()), expect) for p in fp.Pads()):
            break
    else:
        raise AssertionError((ref, [xy(p.GetPosition()) for p in fp.Pads()]))
    fp.SetReference(ref)
    fp.SetValue(keep[4])
    fp.SetPath(keep[0])
    fp.SetSheetname(keep[1])
    fp.SetSheetfile(keep[2])
    fp.SetFPID(pcbnew.LIB_ID(pcbnew.UTF8("fcl_local"), pcbnew.UTF8(name)))
    fp.SetAttributes(keep[5])
    fp.SetDNP(keep[6])
    for k, v in fields.items():
        if k not in ("Reference", "Value", "Footprint"):
            fp.SetField(k, v)
    for f in fp.GetFields():
        if f.GetName() not in ("Reference", "Value"):
            f.SetVisible(False)
    for p in fp.Pads():
        if p.GetNumber():
            p.SetNet(net)
    print(ref, name, "rot", fp.GetOrientationDegrees(), sorted(xy(p.GetPosition()) for p in fp.Pads()))
    return fp


# ---- 3a. servo row: parts and their own short tracks move by D
r78 = b.FindFootprintByReference("R78")
q = r78.GetPosition()
r78.SetPosition(pcbnew.VECTOR2I(q.x - MM(0.15), q.y))          # undo the 0.15 mm nudge of block_m16.py
for tr in b.GetTracks():
    if tr.GetClass() != "PCB_VIA" and tr.GetNetname() == "Net-(J_SRV1-Pin_1)" and {xy(tr.GetStart()), xy(tr.GetEnd())} == {(5.0, 65.25), (5.0, 66.6)}:
        tr.SetStart(V(4.7, 65.25))
        tr.SetEnd(V(4.7, 66.6))
refs = [f"J_SRV{i}" for i in range(1, 7)] + [f"R{i}" for i in range(78, 84)]
for r in refs:
    fp = b.FindFootprintByReference(r)
    q = fp.GetPosition()
    fp.SetPosition(pcbnew.VECTOR2I(q.x + MM(D), q.y))
moved = 0
for tr in b.GetTracks():
    if tr.GetClass() == "PCB_VIA" or tr.GetLayer() != fcu:
        continue
    n = tr.GetNetname()
    s0, e0 = xy(tr.GetStart()), xy(tr.GetEnd())
    row = (n.startswith("Net-(J_SRV") or n == "SERVO_V" or
           (n == "GND" and 71.5 < s0[1] < 73.2 and 71.5 < e0[1] < 73.2 and 5 < s0[0] < 18.5 and 5 < e0[0] < 18.5))
    if row and min(s0[1], e0[1]) > 64 and max(s0[0], e0[0]) < 19:
        tr.SetStart(V(s0[0] + D, s0[1]))
        tr.SetEnd(V(e0[0] + D, e0[1]))
        moved += 1
        if n != "GND":
            NEWSEG.append(((s0[0] + D, s0[1]), (e0[0] + D, e0[1]), mm(tr.GetWidth())))
print("servo row: 12 parts and", moved, "short tracks moved", D, "mm")

# ---- 3b. PWM tracks on F.Cu to the resistors' new places
OLD = {"SRV_PWM1": [((6.3, 62.15), (5.45, 63.0)), ((6.9, 62.15), (6.3, 62.15))],
       "SRV_PWM2": [((7.95, 62.9), (7.9, 62.95)), ((7.95, 60.4), (7.95, 62.9))],
       "SRV_PWM3": [((20.4, 52.85), (10.3, 62.95))],
       "SRV_PWM4": [((20.85, 55.0), (12.9, 62.95))],
       "SRV_PWM5": [((19.75, 58.7), (15.45, 63.0))],
       "SRV_PWM6": [((20.25, 60.9), (18.15, 63.0)), ((21.05, 60.9), (20.25, 60.9))]}
NEW = {"SRV_PWM1": [(6.9, 62.15), (7.42, 62.15), (8.55, 63.28)],
       "SRV_PWM2": [(7.95, 60.4), (10.83, 63.28), (11.05, 63.28)],
       "SRV_PWM3": [(20.4, 52.85), (13.4, 59.85), (13.4, 63.1)],
       "SRV_PWM4": [(20.85, 55.0), (16.0, 59.85), (16.0, 63.1)],
       "SRV_PWM5": [(19.75, 58.7), (18.6, 59.85), (18.6, 63.1)],
       "SRV_PWM6": [(21.05, 60.9), (21.25, 61.1), (21.25, 63.1)]}
for net, segs in OLD.items():
    for p0, p1 in segs:
        hit = [tr for tr in b.GetTracks() if tr.GetClass() != "PCB_VIA" and tr.GetNetname() == net and tr.GetLayer() == fcu
               and ((near(xy(tr.GetStart()), p0) and near(xy(tr.GetEnd()), p1)) or (near(xy(tr.GetStart()), p1) and near(xy(tr.GetEnd()), p0)))]
        assert len(hit) == 1, (net, p0, p1, len(hit))
        KEEP.append(hit[0])
        b.Remove(hit[0])
    add(net, fcu, NEW[net], 0.15)
for i in range(6):
    pad = [p for p in b.FindFootprintByReference(f"R{78 + i}").Pads() if p.GetNetname() == f"SRV_PWM{i + 1}"][0]
    print(f"  R{78 + i}.1 at", xy(pad.GetPosition()), "track ends at", NEW[f"SRV_PWM{i + 1}"][-1])

# ---- 3c. block mounts and springs
holes = []
for ref, exp in (("BT12", (4.4, 5.8)), ("BT32", (4.4, 46.8)), ("BT22", (80.6, 45.7))):
    for p in swap(ref, NAME, exp).Pads():
        holes.append(xy(p.GetPosition()))
swap("BT33", "BAT-TH_MY-18650-05-J", (6.18, 56.5))
swap("BT23", "BAT-TH_MY-18650-05-J", (78.82, 36.0))

# ---- 3d. cell 2: VBAT_OR on F.Cu straight again (it went round the third hole, which is gone)
old_path = [(80.15, 28.55), (80.45, 28.85), (82.6, 28.85), (83.7, 29.95), (83.7, 33.5), (82.55, 34.65)]
w = None
for p0, p1 in zip(old_path, old_path[1:]):
    hit = [tr for tr in b.GetTracks() if tr.GetClass() != "PCB_VIA" and tr.GetNetname() == "VBAT_OR" and tr.GetLayer() == fcu
           and ((near(xy(tr.GetStart()), p0) and near(xy(tr.GetEnd()), p1)) or (near(xy(tr.GetStart()), p1) and near(xy(tr.GetEnd()), p0)))]
    assert len(hit) == 1, (p0, p1, len(hit))
    w = mm(hit[0].GetWidth())
    KEEP.append(hit[0])
    b.Remove(hit[0])
add("VBAT_OR", fcu, [(80.15, 28.55), (82.55, 30.95), (82.55, 34.65)], w)


def seg_d(p, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    L = dx * dx + dy * dy
    u = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


# ---- 3e. GND vias under the moved parts, the new tracks or in the new holes
rects = []
for r in refs:
    for p in b.FindFootprintByReference(r).Pads():
        bb = p.GetBoundingBox()
        rects.append((mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY, p.GetNetname()))
n = 0
for tr in list(b.GetTracks()):
    if tr.GetClass() == "PCB_VIA" and tr.GetNetname() == "GND":
        q = xy(tr.GetPosition())
        r = mm(tr.GetWidth(pcbnew.F_Cu)) / 2
        hit = any(math.hypot(q[0] - h[0], q[1] - h[1]) < 0.9 + 0.5 + r for h in holes)
        hit = hit or any(seg_d(q, p0, p1) < wd / 2 + 0.2 + r for p0, p1, wd in NEWSEG)
        for x0, y0, x1, y1, net in rects:
            dx, dy = max(x0 - q[0], 0, q[0] - x1), max(y0 - q[1], 0, q[1] - y1)
            if net != "GND":
                hit = hit or math.hypot(dx, dy) < r + 0.25
            elif x1 - x0 > 1.5:                 # GND pin of a header: keep the via's hole 0.5 mm off the pin hole
                hit = hit or math.hypot(q[0] - (x0 + x1) / 2, q[1] - (y0 + y1) / 2) < 0.5 + 0.5 + 0.2
            if x1 - x0 > 1.5 and net != "GND":
                hit = hit or math.hypot(q[0] - (x0 + x1) / 2, q[1] - (y0 + y1) / 2) < 0.5 + 0.5 + 0.2
        if hit:
            KEEP.append(tr)
            b.Remove(tr)
            n += 1
            print("  removed GND via at", q)
print("GND vias removed:", n)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
