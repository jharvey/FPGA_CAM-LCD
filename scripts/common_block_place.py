#!/usr/bin/env python3
"""Place the common battery-block footprints (BT12 -> C1, BT32 -> C3, BT22 -> R), remove GND vias under the new
holes, and re-route the VBAT_OR F.Cu leg near the right block round the pin hole, remove the BAY_END_WALL_R rule area.

    flatpak run --command=python3 org.kicad.KiCad scripts/common_block_place.py     (repo root)
"""
import math
import pcbnew

BOARD = "FCL.kicad_pcb"
LIB = "footprints/fcl_local.pretty"
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
b = pcbnew.LoadBoard(BOARD)
KEEP = []
gnd = b.FindNet("GND")


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(p):
    return (round(mm(p.x) - OX, 3), round(mm(p.y) - OY, 3))


# ref: (footprint, origin, expected {(pad number, x, y)})
SITES = {
    "BT12": ("FCL_BatteryBlock_Mount_MS3181_C1", (0.0, 15.5), {("1", 4.4, 5.8), ("1", 2.6, 24.8)}),
    "BT32": ("FCL_BatteryBlock_Mount_MS3181_C3", (0.0, 56.5), {("1", 4.4, 46.8), ("", 3.2, 62.75)}),
    "BT22": ("FCL_BatteryBlock_Mount_MS3181_R", (85.0, 36.0), {("1", 82.4, 26.7), ("", 81.8, 29.75)}),
}
NEW = {ref: pcbnew.FootprintLoad(LIB, s[0]) for ref, s in SITES.items()}
holes = []
for ref, (name, org, expect) in SITES.items():
    old = b.FindFootprintByReference(ref)
    assert old is not None and old.IsFlipped(), ref
    fields = {f.GetName(): f.GetText() for f in old.GetFields()}
    path, sn, sf = old.GetPath(), old.GetSheetname(), old.GetSheetfile()
    KEEP.append(old)
    b.Remove(old)
    fp = NEW[ref]
    b.Add(fp)
    fp.SetPosition(V(*org))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    ok = False
    for ang in (0, 90, 180, 270):
        fp.SetOrientationDegrees(ang)
        got = {(p.GetNumber(),) + tuple(round(v, 2) for v in xy(p.GetPosition())) for p in fp.Pads()}
        if got == {(n, round(x, 2), round(y, 2)) for n, x, y in expect}:
            ok = True
            break
    assert ok, (ref, got)
    fp.SetReference(ref)
    fp.SetValue("Battery block MS3181")
    fp.SetPath(path)
    fp.SetSheetname(sn)
    fp.SetSheetfile(sf)
    fp.SetFPID(pcbnew.LIB_ID(pcbnew.UTF8("fcl_local"), pcbnew.UTF8(name)))
    for k, v in fields.items():
        if k in ("Reference", "Value", "Footprint"):
            continue
        if ref == "BT22" and k in ("LCSC", "LCSC Part", "MPN"):
            v = ""
        if k == "Description":
            continue
        fp.SetField(k, v)
    for f in fp.GetFields():
        if f.GetName() not in ("Reference", "Value"):
            f.SetVisible(False)
    for p in fp.Pads():
        if p.GetNumber() == "1":
            p.SetNet(gnd)
            holes.append((xy(p.GetPosition()), 1.35 + 0.55))
        else:
            holes.append((xy(p.GetPosition()), 1.05 + 0.55))
    print(ref, name, "orientation", fp.GetOrientationDegrees(), sorted(got))

# ---- GND vias that would sit in / too close to the new holes
n = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        x, y = xy(t.GetPosition())
        if any(math.hypot(x - hx, y - hy) < r for (hx, hy), r in holes):
            KEEP.append(t)
            b.Remove(t)
            n += 1
            print("  removed GND via at", (x, y))
print("GND vias removed:", n)

# ---- VBAT_OR near the right block: via (80.15, 28.55) -> (79.6, 28.6); F.Cu leg goes round the pin hole
fcu, bcu = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")
net = b.FindNet("VBAT_OR")


def near(a, c, tol=0.02):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


def find(layer, p0, p1):
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA" and t.GetNetname() == "VBAT_OR" and t.GetLayer() == layer:
            s, e = xy(t.GetStart()), xy(t.GetEnd())
            if (near(s, p0) and near(e, p1)) or (near(s, p1) and near(e, p0)):
                return t
    raise AssertionError(("not found", layer, p0, p1))


def add(layer, p0, p1, w):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*p0))
    t.SetEnd(V(*p1))
    t.SetWidth(w)
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)


VIA = (80.15, 28.55)
fd = find(fcu, VIA, (82.55, 30.95))
w_f = fd.GetWidth()
KEEP.append(fd)
b.Remove(fd)
add(fcu, VIA, (80.15, 30.4), w_f)
add(fcu, (80.15, 30.4), (82.55, 32.8), w_f)
moved = 0
for t in b.GetTracks():
    if t.GetNetname() == "VBAT_OR" and t.GetClass() != "PCB_VIA" and t.GetLayer() == fcu:
        s_, e_ = xy(t.GetStart()), xy(t.GetEnd())
        if near(s_, (82.55, 30.95)) and abs(e_[0] - 82.55) < 0.02 and e_[1] > 32.9:
            t.SetStart(V(82.55, 32.8)); moved += 1
        elif near(e_, (82.55, 30.95)) and abs(s_[0] - 82.55) < 0.02 and s_[1] > 32.9:
            t.SetEnd(V(82.55, 32.8)); moved += 1
print("VBAT_OR F.Cu leg re-routed round the pin hole; track end moved:", moved)
assert moved == 1

stub = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == "GND" and t.GetLayer() == bcu
        and {tuple(round(v, 1) for v in xy(t.GetStart())), tuple(round(v, 1) for v in xy(t.GetEnd()))} == {(4.8, 61.5), (3.0, 61.6)}]
print("GND stub tracks to the removed via at (2.98, 61.65):", len(stub))
for t in stub:
    KEEP.append(t)
    b.Remove(t)

for z in list(b.Zones()):
    if z.GetIsRuleArea() and z.GetZoneName() == "BAY_END_WALL_R":
        KEEP.append(z)
        b.Remove(z)
        print("removed rule area BAY_END_WALL_R")

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
