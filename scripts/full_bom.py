#!/usr/bin/env python3
"""Complete build BOM for one battery variant: every part of a finished unit, with who supplies it.

    python3 scripts/full_bom.py removable production/removable
    python3 scripts/full_bom.py fixed     production/fixed

Reads FCL_bom_jlc.csv and FCL_mech_bom.csv in that folder (written by make_production.sh) and writes
FCL_full_bom.csv with a Supplier column:
    JLC PCB assembly       fitted by JLCPCB from the BOM / CPL files (LCSC number given)
    JLC assembly, check    same, but not in stock at JLC on 2026-11-22: pre-order into the JLC parts library or supply
    You supply to JLC      fitted by JLCPCB, part consigned by you (no LCSC number in the BOM)
    JLC 3D printing        order from JLC3DP with the STEP / STL file
    JLC CNC                order from JLC CNC with the STEP file and drawing
    Buy: electronics       modules and parts that plug in after assembly
    Buy: hardware          screws, washers, inserts, cells
    Consumable             glue, thread locker
"""
import csv
import os
import sys

variant, folder = sys.argv[1], sys.argv[2]
assert variant in ("removable", "fixed"), variant

# not in stock at JLC in the check of 2026-11-22 (doc/jlc_check_2026-11-22.md); matched on the BOM comment
CHECK_STOCK = ("ICM-42688-P", "M12L2561616A", "ICS-43434", "LIS2MDL", "LPS22DF", "CH224K", "PTS645", "REF3025")
THROUGH_HOLE = ("MY-18650-04-J", "MY-18650-05-J", "OV7670_2x9")

rows = []
with open(os.path.join(folder, "FCL_bom_jlc.csv"), newline="") as fh:
    for r in csv.DictReader(fh):
        refs = r["Designator"]
        qty = len([x for x in refs.split(",") if x.strip()])
        sup = "JLC assembly, check" if any(k in r["Comment"] for k in CHECK_STOCK) else "JLC PCB assembly"
        note = "Not in stock at JLC on 2026-11-22: pre-order or supply." if sup.endswith("check") else ""
        if any(k in r["Comment"] for k in THROUGH_HOLE):
            note = (note + " Through-hole: JLC through-hole service or hand solder.").strip()
        rows.append([sup, refs, r["Comment"], qty, "LCSC", r["LCSC"], "", note])

rows.append(["You supply to JLC", "U1", "FPGA LFE5U-85F-6BG381C (caBGA-381)", 1, "Lattice", "LFE5U-85F-6BG381C", "",
             "Not in the JLC BOM / CPL (no LCSC number). Consign it to JLC for BGA placement, or add an LCSC number "
             "to the schematic and regenerate. -6 or faster; a 45F / 25F also fits the footprint."])

BUY_E = [
    ("DS1", "Round TFT 2.1 in 480x480, 40-pin FFC", 1, "Newhaven", "NHD-2.1-480480AF-ASXP", "Plugs into J7."),
    ("CAM1", "OV7670 camera module, 2x9 pin header, no FIFO", 1, "", "OV7670 (18-pin)", "Plugs into J1; four M2.5 x 6 screws (MP24)."),
    ("LS1", "Speaker 8 ohm, 1 W or more, with JST-SH 1.0 mm 2-pin lead", 1, "", "",
     "Plugs into J8. Size not fixed yet: the case has no speaker pocket."),
    ("BAT1 cell", "Coin cell CR1225 3 V", 1, "", "CR1225", "RTC backup; the holder BAT1 is fitted by JLC."),
    ("SD card", "microSD card, 32 GB or less (FAT32)", 1, "", "", "In SD1."),
    ("USB cable", "USB-C cable + 5 V supply / PC port", 1, "", "", "Charging, programming, data."),
]
for ref, item, q, mfr, mpn, note in BUY_E:
    rows.append(["Buy: electronics", ref, item, q, mfr, mpn, "", note])

SUP = {"Printed": "JLC 3D printing", "Machined": "JLC CNC", "Purchased": "Buy: hardware", "Consumable": "Consumable"}
with open(os.path.join(folder, "FCL_mech_bom.csv"), newline="") as fh:
    for r in csv.DictReader(fh):
        sup = SUP.get(r["Category"], "Buy: hardware")
        if "Dust cap" in r["Item"] or "coil spring" in r["Item"]:
            sup = "Buy: electronics"       # distributor parts (Amphenol / Keystone), not hardware-store items
        rows.append([sup, r["Ref"], r["Item"], r["Qty"], r["Manufacturer"], r["MPN"], r["File"], r["Notes"]])

ORDER = ["JLC PCB assembly", "JLC assembly, check", "You supply to JLC", "JLC 3D printing", "JLC CNC",
         "Buy: electronics", "Buy: hardware", "Consumable"]
rows.sort(key=lambda r: ORDER.index(r[0]))
out = os.path.join(folder, "FCL_full_bom.csv")
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Supplier", "Ref", "Item", "Qty", "Manufacturer / source", "Part number", "File", "Notes"])
    w.writerow(["JLC PCB (bare board)", "PCB", "FCL V0.1 4-layer board", 1, "JLCPCB", "FCL_gerbers_V0.1.zip",
                "production/FCL_gerbers_V0.1.zip", "Same board for both battery variants."])
    w.writerows(rows)
count = {}
for r in rows:
    count[r[0]] = count.get(r[0], 0) + 1
print(variant, "full BOM:", len(rows) + 1, "lines ->", out, "|", ", ".join("%s %d" % (k, count[k]) for k in ORDER if k in count))
