#!/usr/bin/env python3
"""Board / schematic field clean-up before the JLC files.

    flatpak run --command=python3 org.kicad.KiCad scripts/fields_fix.py     (repo root, run once)

* J7 (C202115): FT Rotation Offset 180, no position offset (matched against JLC's EasyEDA footprint: all 40 pads
  line up at 180 deg, JLC's origin is our pad centre).
* BT12 / BT22 / BT32: one Description for the block mounts, same on board and schematic.
"""
import re
import pcbnew

DESC = "Aluminium battery end block mount (common block): two M1.6 screws from the camera side, GND pads"


def sch_field(path, ref, name, value):
    t = open(path).read()
    k = t.index('(property "Reference" "%s"' % ref)
    a = t.rindex("\n\t(symbol\n", 0, k)
    e = t.index("\n\t(symbol\n", k) if "\n\t(symbol\n" in t[k:] else len(t)
    blk, n = re.subn(r'\(property "%s" "[^"]*"' % re.escape(name), '(property "%s" "%s"' % (name, value), t[a:e], count=1)
    assert n == 1, (path, ref, name)
    open(path, "w").write(t[:a] + blk + t[e:])


sch_field("display.kicad_sch", "J7", "FT Rotation Offset", "180")
sch_field("display.kicad_sch", "J7", "FT Position Offset", "")
for r in ("BT12", "BT22", "BT32"):
    sch_field("power.kicad_sch", r, "Description", DESC)

b = pcbnew.LoadBoard("FCL.kicad_pcb")
j7 = b.FindFootprintByReference("J7")
j7.SetField("FT Rotation Offset", "180")
j7.SetField("FT Position Offset", "")
for r in ("BT12", "BT22", "BT32"):
    fp = b.FindFootprintByReference(r)
    fp.SetField("Description", DESC)
    for f in fp.GetFields():
        if f.GetName() == "Description":
            f.SetVisible(False)
b.Save("FCL.kicad_pcb")

p = "tools/jlc_cache/index.csv"
s = open(p).read()
old = "Hirose_FH12-40S-0.5SV_1x40-1MP_P0.50mm_Vertical,0 (unverified),"
assert s.count(old) == 1
open(p, "w").write(s.replace(old, "Hirose_FH12-40S-0.5SV_1x40-1MP_P0.50mm_Vertical,180 (matched 2026-11-26),"))
print("ok")
