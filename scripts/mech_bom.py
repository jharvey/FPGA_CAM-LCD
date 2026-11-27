#!/usr/bin/env python3
"""Mechanical BOM (everything JLC does not supply) for one battery variant.

    python3 scripts/mech_bom.py removable production/removable/FCL_mech_bom.csv
    python3 scripts/mech_bom.py fixed     production/fixed/FCL_mech_bom.csv

Source: the PARTS list in scripts/make_mech_sheet.py (the MP symbols of mechanical.kicad_sch), plus the three
battery end blocks (BT12 / BT22 / BT32 in the schematic) and the button caps.
    removable: blocks, bayonet caps and their contact stack, block screws and spacers, standard printed parts
    fixed:     no blocks / caps; shells and PCB-side cradle are the *_fixed prints; cells held by the soldered springs
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_mech_sheet as M  # noqa: E402

variant, out = sys.argv[1], sys.argv[2]
assert variant in ("removable", "fixed"), variant
REMOVABLE_ONLY = {"MP2", "MP3", "MP4", "MP5", "MP6", "MP7", "MP8", "MP10", "MP25", "MP17", "MP18"}
NOT_USED = {"MP9", "MP11"}
PRINT = {"MP13": "case/print/FCL_case_rear", "MP14": "case/print/FCL_case_front", "MP15": "case/print/FCL_cell_cradle",
         "MP19": "case/print/FCL_button_actuators", "MP23": "case/print/FCL_cell_cradle_top", "MP26": "case/print/FCL_button_caps"}
FIXED_PRINT = {"MP13", "MP14", "MP15"}

rows = []
if variant == "removable":
    rows.append(["BT12,BT22,BT32", "Aluminium battery end block, MS3181-16 bayonet boss", "Machined", "3", "", "",
                 "footprints/fcl_local.3dshapes/FCL_BatteryBlock_MS3181_A.step",
                 "6061-T6. 7 x 25 mm flange, two M1.6 tapped holes S1 (3.2, -10.3) / S2 (3.5, +9.3), 19.2 bore. "
                 "Machining drawing still shows the earlier block: redraw before ordering."])
parts = list(M.PARTS) + [("MP26", "Button cap (x2 in one print)", dict(
    Category="Printed", Qty="2", Notes="Pressed onto the plunger from outside; its tongue fills the plunger's split and locks it."))]
for ref, value, d in parts:
    if ref in NOT_USED or (variant == "fixed" and ref in REMOVABLE_ONLY):
        continue
    f = PRINT.get(ref, "")
    if f:
        f += ("_fixed" if variant == "fixed" and ref in FIXED_PRINT else "") + ".step / .stl"
    else:
        f = d.get("Source_File", "")
    notes = d.get("Notes", "")
    if ref == "MP19":
        notes = "B1/B2 PTS645 plungers, snap in from inside the rear shell; the button cap (MP26) goes on from outside."
    if variant == "fixed" and ref == "MP12":
        notes = "Held between the soldered + contact and spring (BT13 / BT23 / BT33). Changing a cell needs the case opened (screwdriver). " + notes
    rows.append([ref, value, d.get("Category", ""), d.get("Qty", ""), d.get("Manufacturer", ""), d.get("MPN", ""), f, notes])
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Ref", "Item", "Category", "Qty", "Manufacturer", "MPN", "File", "Notes"])
    w.writerows(rows)
print(f"{variant}: {len(rows)} mechanical lines -> {out}")
