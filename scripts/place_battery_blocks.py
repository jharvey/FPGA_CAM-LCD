#!/usr/bin/env python3
"""Replace the left-side cell springs BT12 / BT32 by FCL_BatteryBlock_Mount_M2.5_Pin2 (aluminium end block,
one M2.5 screw + one 2 mm dowel pin).  H1 is removed: the cell-1 block screw sits on the same spot and
takes over as the GND mounting point.  Four GND stitching vias that sit on the new holes are removed.

    flatpak run --command=python3 org.kicad.KiCad scripts/place_battery_blocks.py   (run in the repo root)
"""
import math
import pcbnew

BOARD = "FCL.kicad_pcb"
LIB = "footprints/fcl_local.pretty"
FP = {"BT12": "FCL_BatteryBlock_Mount_M2.5_Pin2_A", "BT32": "FCL_BatteryBlock_Mount_M2.5_Pin2_B"}
OX, OY = 78.0, 55.5
TARGET = {"BT12": 15.5, "BT32": 56.5}            # cell axis (board y) of the block
SCREW = (4.4, -9.7)                               # board offsets from (edge, axis)
PIN = {"BT12": (3.0, 9.3), "BT32": (3.0, 7.5)}
DROP_VIAS = [(4.5, 7.1), (2.6, 24.88), (4.5, 48.26), (2.43, 65.88), (4.22, 64.14)]

mm = pcbnew.ToMM
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(BOARD)
KEEP = []   # removed items: keep the Python wrappers alive, KiCad crashes if they are garbage-collected
NEW = {ref: pcbnew.FootprintLoad(LIB, FP[ref]) for ref in TARGET}   # load before editing the board (a second load later crashes)
gnd = b.FindNet("GND")

# ---- remove H1 (the cell-1 block screw replaces it)
h1 = b.FindFootprintByReference("H1")
assert h1 is not None and abs(mm(h1.GetPosition().x) - OX - 5.7) < 0.05
KEEP.append(h1)
b.Remove(h1)
print("H1 removed", flush=True)


for ref, axis in TARGET.items():
    old = b.FindFootprintByReference(ref)
    assert old is not None and old.IsFlipped()
    uuid_path = old.GetPath()
    fields = [(f.GetName(), f.GetText()) for f in old.GetFields() if f.GetName() not in ("Reference", "Value", "Footprint", "Datasheet", "Description")]
    DESC = "Aluminium battery end block mount (PG16 cell bore): M2.5 screw + 2 mm dowel pin"
    sheetname, sheetfile = old.GetSheetname(), old.GetSheetfile()
    KEEP.append(old)
    b.Remove(old)
    print("old removed", ref, flush=True)
    fp = NEW[ref]
    print("loaded", fp, flush=True)
    fp.SetParent(b)
    b.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(MM(OX), MM(OY + axis)))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM if hasattr(pcbnew, "FLIP_DIRECTION_TOP_BOTTOM") else False)
    # find the orientation that puts the screw and pin where they belong
    ok = False
    for ang in (0, 90, 180, 270):
        fp.SetOrientationDegrees(ang)
        pads = {p.GetNumber(): (mm(p.GetPosition().x) - OX, mm(p.GetPosition().y) - OY) for p in fp.Pads()}
        s, pn = pads["1"], pads[""]
        if (abs(s[0] - SCREW[0]) < 0.01 and abs(s[1] - axis - SCREW[1]) < 0.01
                and abs(pn[0] - PIN[ref][0]) < 0.01 and abs(pn[1] - axis - PIN[ref][1]) < 0.01):
            ok = True
            break
    assert ok, f"{ref}: no orientation gives screw/pin targets (last {pads})"
    fp.SetReference(ref)
    fp.SetValue("BLOCK_MOUNT")
    fp.SetFPID(pcbnew.LIB_ID(pcbnew.UTF8("fcl_local"), pcbnew.UTF8(FP[ref])))
    for name, text in fields:
        fp.SetField(name, "" if name.upper().startswith("LCSC") or name == "MPN" else text)
    fp.SetField("Description", DESC)
    for f in fp.GetFields():
        if f.GetName() not in ("Reference", "Value"):
            f.SetVisible(False)
            f.SetLayer(pcbnew.B_Fab)
    print(ref, "fields", [(n, "" if n.upper().startswith("LCSC") else t) for n, t in fields])
    fp.SetPath(uuid_path)
    fp.SetSheetname(sheetname)
    fp.SetSheetfile(sheetfile)
    for p in fp.Pads():
        if p.GetNumber() == "1":
            p.SetNet(gnd)
    print(ref, "placed, orientation", fp.GetOrientationDegrees(), "flipped", fp.IsFlipped(), "pads", pads)

# ---- remove GND vias on the new holes
n = 0
removed = []   # keep the Python wrappers alive (KiCad crashes if they are collected)
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        p = t.GetPosition()
        if any(math.hypot(mm(p.x) - OX - x, mm(p.y) - OY - y) < 0.05 for x, y in DROP_VIAS):
            removed.append(t)
            b.Remove(t)
            n += 1
print("vias removed", n, flush=True)
assert n == len(DROP_VIAS), f"removed {n} vias, expected {len(DROP_VIAS)}"

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(BOARD)
print("saved")
