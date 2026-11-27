#!/usr/bin/env python3
"""Battery block screws M2.5 -> M1.6, two screws at every block, no locating pin.

    flatpak run --command=python3 org.kicad.KiCad scripts/block_m16.py     (repo root, run once)

Block-local frame: x into the board from the edge, y along the edge (+ = board y down), origin on the cell axis.
Three M1.6 tapped holes in the common block:  T1 (4.4, -9.7)   T2 (2.6, +9.3)   T3 (3.4, +5.0)
    cell 1 (left):   T1 + T2   one each side of the cell
    cell 3 (left):   T1 + T3   one each side of the cell
    cell 2 (right):  T2 + T3   both on the same side (the T1 spot is under the USB pair: to be routed later)
Board: 1.8 mm holes.  T1 / T2 are plated GND pads (the block is the cell's negative contact), T3 is a bare hole.
The 2 mm pin holes go.  The spring land next to T3 becomes a plain 1.72 x 4.0 land (was L-shaped round the pin).
VBAT_OR (F.Cu) at the right block now passes between T2 and T3 and down the outside of T3.
R78 moves 0.15 mm right (courtyard clear of the T3 screw head at cell 3).
"""
import math
import re
import pcbnew

BOARD = "FCL.kicad_pcb"
LIB = "footprints/fcl_local.pretty"
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
HOLE = 1.8
T = {"T1": (4.4, -9.7), "T2": (2.6, 9.3), "T3": (3.4, 5.0)}
# footprint: (holes used, plated pad diameter per hole or None for a bare hole)
USE = {"C1": (("T1", 4.0), ("T2", 4.0)), "C3": (("T1", 4.0), ("T3", None)), "R": (("T2", 3.0), ("T3", None))}
WHAT = {"C1": "cell 1: screws in T1 + T2", "C3": "cell 3: screws in T1 + T3", "R": "right side, cell 2 (placed turned 180 deg): screws in T2 + T3"}

# ---- 1. block mount footprints
for k, holes in USE.items():
    p = f"{LIB}/FCL_BatteryBlock_Mount_MS3181_{k}.kicad_mod"
    s = open(p).read()
    assert "M1.6" not in s, "already done"
    s = re.sub(r"\t\(pad [^\n]*\n", "", s)
    s = re.sub(r"\t\(fp_circle \(center (?:4\.4 9\.7|2\.6 -9\.3)\)[^\n]*\n", "", s)
    s = re.sub(r'\t\(fp_text user "M2\.5" [^\n]*\n[^\n]*\n\t\)\n', "", s)
    assert 'fp_text user "M2.5"' not in s, "M2.5 marks left"
    s = re.sub(r'\(descr "[^"]*"\)',
               '(descr "Mount for the common FCL aluminium battery end block (MS3181-16 bayonet boss, 19.2 mm cell bore). The block has '
               'three M1.6 tapped holes, T1 (4.4, -9.7), T2 (2.6, +9.3) and T3 (3.4, +5.0), from the cell axis at the board edge; two are '
               f'used per site. This footprint, {WHAT[k]}. 1.8 mm holes; T1 / T2 are GND pads, T3 is a bare hole. Flat block face 0.5 mm '
               'off the PCB: one 0.5 mm washer between block and PCB at each screw. Drawn mirrored in y for the back side.")', s, count=1)
    add = ""
    for name, pad in holes:
        x, y = T[name][0], -T[name][1]
        add += f'\t(fp_circle (center {x} {y}) (end {x + 1.55:.2f} {y}) (stroke (width 0.05) (type solid)) (fill no) (layer "B.CrtYd"))\n'
        add += f'\t(fp_circle (center {x} {y}) (end {x + 1.5:.2f} {y}) (stroke (width 0.1) (type solid)) (fill no) (layer "B.Fab"))\n'
        add += (f'\t(fp_text user "M1.6" (at {x} {y} 0) (layer "B.Fab")\n'
                '\t\t(effects (font (size 0.6 0.6) (thickness 0.1)) (justify mirror))\n\t)\n')
        if pad:
            add += (f'\t(pad "1" thru_hole circle (at {x} {y}) (size {pad} {pad}) (drill {HOLE}) (layers "*.Cu" "*.Mask") '
                    '(remove_unused_layers no))\n')
        else:
            add += f'\t(pad "" np_thru_hole circle (at {x} {y}) (size {HOLE} {HOLE}) (drill {HOLE}) (layers "*.Cu" "*.Mask"))\n'
    i = s.index("\t(model ")
    open(p, "w").write(s[:i] + add + s[i:])
    print("footprint", k, [h for h, _ in holes])

# ---- 2. spring footprint next to T3: one plain land, courtyard stepped round the T3 hole
p = f"{LIB}/BAT-TH_MY-18650-05-J_LM.kicad_mod"
s = open(p).read()
a = "\t(pad 1 smd rect (at -3.925 0.68) (size 1.95 3.0) (layers F.Cu F.Paste F.Mask))\n"
c = "\t(pad 1 smd rect (at -5.925 0.08) (size 2.05 1.8) (layers F.Cu F.Paste F.Mask) (zone_connect 2))\n"
assert a in s and c in s
s = s.replace(a, "\t(pad 1 smd rect (at -4.95 0.04) (size 4.0 1.72) (layers F.Cu F.Paste F.Mask))\n").replace(c, "")
for old, new in (("(end -7.05 1.10)", "(end -7.05 1.05)"), ("(start -7.05 1.10) (end -5.05 1.10)", "(start -7.05 1.05) (end -3.00 1.05)"),
                 ("(start -5.05 1.10) (end -5.05 2.30)", "(start -3.00 1.05) (end -3.00 2.30)"), ("(start -5.05 2.30)", "(start -3.00 2.30)")):
    assert s.count(old) == 1, old
    s = s.replace(old, new)
open(p, "w").write(s)

# ---- 3. board
b = pcbnew.LoadBoard(BOARD)
KEEP = []
gnd = b.FindNet("GND")


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(p):
    return (round(mm(p.x) - OX, 3), round(mm(p.y) - OY, 3))


def near(a, c, tol=0.02):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


def reload(ref, expect):
    """swap a footprint for the library version, same place; expect = a pad position that must come out"""
    old = b.FindFootprintByReference(ref)
    name = str(old.GetFPID().GetLibItemName())
    fields = {f.GetName(): f.GetText() for f in old.GetFields()}
    keep = (old.GetPath(), old.GetSheetname(), old.GetSheetfile(), old.GetPosition(), old.GetValue(), old.GetAttributes(),
            old.IsDNP(), old.GetOrientationDegrees())
    nets = {p.GetNumber(): p.GetNet() for p in old.Pads() if p.GetNumber()}
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
        if p.GetNumber() in nets:
            p.SetNet(nets[p.GetNumber()])
    print(ref, name, "rot", fp.GetOrientationDegrees(), sorted((p.GetNumber(), xy(p.GetPosition())) for p in fp.Pads()))
    return fp


holes = []
for ref, exp in (("BT12", (4.4, 5.8)), ("BT32", (3.4, 61.5)), ("BT22", (81.6, 31.0))):
    for p in reload(ref, exp).Pads():
        holes.append(xy(p.GetPosition()))
reload("BT33", (5.46, 61.45))
reload("BT23", (79.54, 31.05))

# ---- 4. VBAT_OR on F.Cu at the right block: between T2 and T3, then down the outside of T3
fcu = b.GetLayerID("F.Cu")
path = [(80.15, 28.55), (80.45, 28.85), (82.6, 28.85), (83.7, 29.95), (83.7, 33.5), (82.55, 34.65)]
w = None
for p0, p1 in (((80.15, 28.55), (80.15, 30.4)), ((80.15, 30.4), (82.55, 32.8))):
    hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == "VBAT_OR" and t.GetLayer() == fcu
           and ((near(xy(t.GetStart()), p0) and near(xy(t.GetEnd()), p1)) or (near(xy(t.GetStart()), p1) and near(xy(t.GetEnd()), p0)))]
    assert len(hit) == 1, (p0, p1, len(hit))
    w = hit[0].GetWidth()
    KEEP.append(hit[0])
    b.Remove(hit[0])
hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == "VBAT_OR" and t.GetLayer() == fcu
       and (near(xy(t.GetStart()), (82.55, 32.8)) or near(xy(t.GetEnd()), (82.55, 32.8)))]
assert len(hit) == 1, len(hit)
if near(xy(hit[0].GetStart()), (82.55, 32.8)):
    hit[0].SetStart(V(*path[-1]))
else:
    hit[0].SetEnd(V(*path[-1]))
for p0, p1 in zip(path, path[1:]):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*p0))
    t.SetEnd(V(*p1))
    t.SetWidth(w)
    t.SetLayer(fcu)
    t.SetNet(b.FindNet("VBAT_OR"))
    b.Add(t)
print("VBAT_OR F.Cu re-routed, width", mm(w))


def seg_d(p, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


# ---- 5. GND vias in the new holes or under the new VBAT_OR path
n = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        q = xy(t.GetPosition())
        r = mm(t.GetWidth(pcbnew.F_Cu)) / 2
        if any(math.hypot(q[0] - h[0], q[1] - h[1]) < HOLE / 2 + 0.25 + r for h in holes) or \
           any(seg_d(q, p0, p1) < mm(w) / 2 + 0.2 + r for p0, p1 in zip(path, path[1:])):
            KEEP.append(t)
            b.Remove(t)
            n += 1
            print("  removed GND via at", q)
print("GND vias removed:", n)

# ---- 6. cell 3: R78 0.15 mm to the right, so its courtyard clears the T3 screw head (pad to head was 0.31 mm)
r78 = b.FindFootprintByReference("R78")
q = r78.GetPosition()
r78.SetPosition(pcbnew.VECTOR2I(q.x + MM(0.15), q.y))
hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == "Net-(J_SRV1-Pin_1)" and t.GetLayer() == fcu
       and {xy(t.GetStart()), xy(t.GetEnd())} == {(4.7, 65.25), (4.7, 66.6)}]
assert len(hit) == 1, len(hit)
hit[0].SetStart(V(5.0, 65.25))
hit[0].SetEnd(V(5.0, 66.6))
print("R78 moved to", xy(r78.GetPosition()))

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
