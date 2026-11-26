#!/usr/bin/env python3
"""Footprints + schematic for the common battery block (two tapped holes T1/T2 + one pin hole D).

Writes fcl_local.pretty/FCL_BatteryBlock_Mount_MS3181_C1 / _C3 / _R from the old _A footprint and points the
BT12 / BT32 / BT22 symbols at them.     python3 scripts/common_block_fp.py   (repo root)
Block-local frame: x into the board from the edge, y along the edge (+ = board y down), origin on the cell axis.
Footprint file y = -local y (the footprint is flipped onto the back).  T1 (4.4, -9.7), T2 (2.6, 9.3), D (3.2, 6.25).
"""
import re

LIB = "footprints/fcl_local.pretty/"
base = open(LIB + "FCL_BatteryBlock_Mount_M2.5_Pin2_A.kicad_mod").read()
T1 = '(pad "1" thru_hole circle (at 4.4 9.7) (size 4.6 4.6) (drill 2.7) (layers "*.Cu" "*.Mask") (remove_unused_layers no))'
T2 = '(pad "1" thru_hole circle (at 2.6 -9.3) (size 4.2 4.2) (drill 2.7) (layers "*.Cu" "*.Mask") (remove_unused_layers no))'
D = '(pad "" np_thru_hole circle (at 3.2 -6.25) (size 2.1 2.1) (drill 2.1) (layers "*.Cu" "*.Mask"))'
T2MARK = ('(fp_circle (center 2.6 -9.3) (end 5.1 -9.3) (stroke (width 0.1) (type solid)) (fill no) (layer "B.Fab"))\n'
          '\t(fp_text user "M2.5" (at 2.6 -9.3 0) (layer "B.Fab")\n\t\t(effects (font (size 1 1) (thickness 0.15)) (justify mirror))\n\t)')
USE = {"C1": ("cell 1: two screws (T1 + T2)", [T1, T2], True, True),
       "C3": ("cell 3: screw T1 + 2 mm pin", [T1, D], True, False),
       "R": ("right side, cell 2 (placed turned 180 deg): screw T2 (3.6 mm pad, so the copper clears the pin hole) + 2 mm pin", [T2.replace("(size 4.2 4.2)", "(size 3.6 3.6)"), D], False, True)}
pads = re.findall(r'\t\(pad .*\n', base)
assert len(pads) == 2, len(pads)
for k, (what, plist, t1, t2) in USE.items():
    name = "FCL_BatteryBlock_Mount_MS3181_" + k
    s = base.replace('"FCL_BatteryBlock_Mount_M2.5_Pin2_A"', f'"{name}"', 1)
    s = re.sub(r'\(descr "[^"]*"\)',
               '(descr "Mount for the common FCL aluminium battery end block (MS3181-16 bayonet boss, 19.2 mm cell bore). The block has '
               'two M2.5 tapped holes, T1 (4.4, -9.7) and T2 (2.6, +9.3), and one 2 mm pin hole D (3.2, +6.25), from the cell axis at '
               f'the board edge. This footprint, {what}. Flat block face 0.5 mm off the PCB: one M2.5 washer (5 mm OD x 0.5) between '
               'block and PCB at each screw. Drawn mirrored in y for the back side.")', s, count=1)
    s = s.replace(pads[0] + pads[1], "".join("\t" + p + "\n" for p in plist), 1)
    if not t1:    # drop the T1 screw-head marks
        s = re.sub(r'\t\(fp_circle \(center 4\.4 9\.7\)[^\n]*\n', "", s)
        s = re.sub(r'\t\(fp_text user "M2\.5" \(at 4\.4 9\.7 0\) \(layer "B\.Fab"\)\n[^\n]*\n\t\)\n', "", s)
    if t2:
        i = s.index("\t(pad ")
        s = s[:i] + "\t" + T2MARK + "\n" + s[i:]
    assert s.count("(pad ") == 2
    open(LIB + name + ".kicad_mod", "w").write(s)
    print("wrote", name)

# ---- schematic
p = "power.kicad_sch"
t = open(p).read()
for old, new in (("FCL_BatteryBlock_Mount_M2.5_Pin2_A", "FCL_BatteryBlock_Mount_MS3181_C1"),
                 ("FCL_BatteryBlock_Mount_M2.5_Pin2_B", "FCL_BatteryBlock_Mount_MS3181_C3")):
    assert t.count(f'"fcl_local:{old}"') == 1
    t = t.replace(f'"fcl_local:{old}"', f'"fcl_local:{new}"')
for v in ("A", "B"):
    t = t.replace(f'(property "Value" "Battery block MS3181 {v}"', '(property "Value" "Battery block MS3181"')
k = t.index('(property "Reference" "BT22"')
a = t.rindex("\n\t(symbol\n", 0, k)
b = t.index("\n\t(symbol\n", k)
blk = t[a:b]
assert '"fcl_local:BAT-TH_MY-18650-05-J"' in blk
blk = blk.replace('"fcl_local:BAT-TH_MY-18650-05-J"', '"fcl_local:FCL_BatteryBlock_Mount_MS3181_R"', 1)
blk = blk.replace('(property "Value" "MY-18650-05-J"', '(property "Value" "Battery block MS3181"', 1)
for f in ("LCSC", "LCSC Part", "MPN"):
    blk = re.sub(r'\(property "%s" "[^"]*"' % re.escape(f), f'(property "{f}" ""', blk)
blk = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "Aluminium battery end block mount (common block, right side): M2.5 screw + 2 mm pin"', blk, count=1)
t = t[:a] + blk + t[b:]
open(p, "w").write(t)
print("schematic updated")
