#!/usr/bin/env python3
"""Mechanical BOM sheet: writes symbols/fcl_mech.kicad_sym (one pinless "MechPart" symbol), mechanical.kicad_sch
(one symbol per mechanical line item, on_board no, in_bom yes) and hooks the sheet into FCL.kicad_sch + sym-lib-table.
Re-run after editing PARTS; the sheet file is regenerated, the root-sheet hook is added once.

    python3 scripts/make_mech_sheet.py          (repo root)
"""
import os
import re
import uuid

ROOT_UUID = "4fa0b2cb-19ee-4a85-acaa-86cc12a69b3d"
SHEET_UUID = "6d3c1f0e-8a52-4c1b-9e7a-3b2f5a0c4d17"      # fixed so re-runs keep the same path
LIB, SYM = "fcl_mech", "MechPart"
FIELDS = ("Category", "Qty", "Manufacturer", "MPN", "Supplier", "Supplier_Link", "Material", "Source_File", "Notes")

# (ref, value, fields...)  Qty is per finished unit.  Machined/printed parts point at their STEP / STL.
PARTS = [
    ("MP2", "Brass slug, left, 17.5 OD x 19.7", dict(
        Category="Machined", Qty="2", Material="C360 brass tube 17.5 x 0.8 wall, ends closed with 0.8 brass discs (soldered)",
        Source_File="case/battery_blocks/ms3181/ms3181_slug_L.step", Notes="Cells 1 and 3. Spring end soldered to it.")),
    ("MP3", "Brass slug, right, 17.5 OD x 15.3", dict(
        Category="Machined", Qty="1", Material="C360 brass tube 17.5 x 0.8 wall, ends closed",
        Source_File="case/battery_blocks/ms3181/ms3181_slug_R.step", Notes="Cell 2.")),
    ("MP4", "Brass contact disc 24 x 0.8", dict(
        Category="Machined", Qty="3", Material="C260 brass sheet 0.8",
        Source_File="case/battery_blocks/ms3181/ms3181_disc.step",
        Notes="Spring lug soldered to it; RTV dot to the cap gasket. Clamped onto the bare boss face = GND path.")),
    ("MP5", "Dust cap MS3181-16, bayonet, rope lanyard", dict(
        Category="Purchased", Qty="3", Manufacturer="Amphenol", MPN="MS3181-16RA",
        Supplier="OEMsTrade / Octopart", Supplier_Link="https://www.oemstrade.com/search/ms3181-16ra",
        Notes="Alt: MS3181-16CA (chain), Glenair MS3181-16C. Measure one before machining the boss (provisional dims).")),
    ("MP6", "Battery coil spring, 17-19 mm cells, solder lug", dict(
        Category="Purchased", Qty="3", Manufacturer="Keystone", MPN="5220", Supplier="Digi-Key",
        Supplier_Link="https://www.digikey.com/en/products/detail/keystone-electronics/5220/2745879",
        Notes="Working height 6.0 mm assumed (provisional).")),
    ("MP7", "O-ring 20 x 1 mm", dict(
        Category="Purchased", Qty="3", Material="NBR 70 or FKM", Notes="Face seal in the boss end face, groove 1.4 x 0.75.")),
    ("MP8", "Bayonet pin, dowel 2.4 x 3.8", dict(
        Category="Purchased", Qty="9", Material="Stainless dowel, 3/32 in (2.38) or ISO 8734 2.5 cut to length",
        Notes="3 per block, pressed through the boss wall, flush with the cell bore. Match to the cap slots.")),
    ("MP9", "Dowel pin ISO 8734 2 x 5", dict(
        Category="Purchased", Qty="2", Material="Stainless", Notes="Block locating pin at cell 3 and at the right block (NPTH 2.1); slip fit + retaining compound in the block.")),
    ("MP10", "Screw M2.5 x 6, socket head", dict(
        Category="Purchased", Qty="4", MPN="ISO 4762 M2.5x6 A2", Notes="Block screws from the camera side: 2 at cell 1, 1 at cell 3, 1 at the right block. 3.9 mm thread engagement.")),
    ("MP25", "Washer M2.5 small, 4.5 OD x 0.5 (spacer)", dict(
        Category="Purchased", Qty="4", MPN="ISO 7092 M2.5 A2", Notes="Between block and PCB at every block screw: sets the 0.5 mm gap and makes the GND contact.")),
    ("MP11", "Washer M2.5", dict(
        Category="Purchased", Qty="4", MPN="ISO 7092 M2.5 A2", Notes="Under the head of each block screw.")),
    ("MP12", "Li-ion cell 18650", dict(
        Category="Purchased", Qty="3", Notes="Flat-top or button-top; length 65.0-65.3 (unprotected). Longer protected cells need shorter slugs.")),
    ("MP13", "Case rear shell", dict(
        Category="Printed", Qty="1", Material="PETG or ASA", Source_File="case/print/FCL_case_rear.stl")),
    ("MP14", "Case front shell", dict(
        Category="Printed", Qty="1", Material="PETG or ASA", Source_File="case/print/FCL_case_front.stl")),
    ("MP15", "Cell cradle", dict(
        Category="Printed", Qty="1", Material="PETG or ASA", Source_File="case/print/FCL_cell_cradle.stl")),
    ("MP19", "Button actuator (x2 in one print)", dict(
        Category="Printed", Qty="2", Material="PETG or ASA", Source_File="case/print/FCL_button_actuators.stl",
        Notes="B1/B2 PTS645 plungers, snap in from inside the rear shell (barb + flange), guided by tubes.")),
    ("MP20", "Heat-set insert 1/4-20 UNC (tripod)", dict(
        Category="Purchased", Qty="1", Material="Brass", Notes="Bottom face, rear shell. Hole 8.2 x 10.5 deep: check against the insert datasheet. Picatinny adapter later.")),
    ("MP21", "Heat-set insert M2.5", dict(
        Category="Purchased", Qty="8", Material="Brass", Notes="4 x case corners (rear shell) + 4 x camera posts (front shell); hole 3.6, insert 4 mm long.")),
    ("MP22", "Screw M2.5 x 10, socket head (case)", dict(
        Category="Purchased", Qty="4", MPN="ISO 4762 M2.5x10 A2", Notes="Head seats 3 mm above the PCB in the front-shell counterbore, about 10 mm to the rear insert.")),
    ("MP23", "Cell cradle, LCD side", dict(
        Category="Printed", Qty="1", Material="PETG or ASA", Source_File="case/print/FCL_cell_cradle_top.stl",
        Notes="Sits on the PCB-side cradle; encloses the cells and carries the TFT back face.")),
    ("MP24", "Screw M2.5 x 6, socket head (camera)", dict(
        Category="Purchased", Qty="4", MPN="ISO 4762 M2.5x6 A2", Notes="OV7670 board to the front-shell posts (3.0 mm holes in the module).")),
    ("MP17", "Thread locker, medium strength", dict(
        Category="Consumable", Qty="-", MPN="Loctite 243", Notes="Block screws and bayonet pins.")),
    ("MP18", "RTV silicone", dict(
        Category="Consumable", Qty="-", Notes="Dot to hold the contact disc on the cap gasket.")),
]


def U():
    return str(uuid.uuid4())


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def prop(name, val, x, y, hide=True, size=1.27, justify="left"):
    h = "\n\t\t\t(hide yes)" if hide else ""
    return (f'\t\t(property {q(name)} {q(val)}\n\t\t\t(at {x:.2f} {y:.2f} 0){h}\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
            f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size {size} {size})\n\t\t\t\t)\n\t\t\t\t(justify {justify})\n\t\t\t)\n\t\t)\n')


SYMBOL_BODY = f'''		(symbol "{SYM}_0_1"
			(rectangle
				(start -2.54 1.27)
				(end 2.54 -1.27)
				(stroke
					(width 0.254)
					(type default)
				)
				(fill
					(type background)
				)
			)
			(polyline
				(pts
					(xy -1.27 0) (xy 1.27 0)
				)
				(stroke
					(width 0.254)
					(type default)
				)
				(fill
					(type none)
				)
			)
		)
'''


def lib_symbol(name):
    s = f'\t(symbol {q(name)}\n\t\t(exclude_from_sim yes)\n\t\t(in_bom yes)\n\t\t(on_board no)\n'
    s += prop("Reference", "MP", 0, 2.54, hide=False, justify="left")
    s += prop("Value", "MechPart", 0, -2.54, hide=False, justify="left")
    s += prop("Footprint", "", 0, 0)
    s += prop("Datasheet", "", 0, 0)
    s += prop("Description", "Mechanical part (no footprint): BOM line only. Qty field = per unit.", 0, 0)
    for f in FIELDS:
        s += prop(f, "", 0, 0)
    s += SYMBOL_BODY.replace(f'"{SYM}_0_1"', f'"{name.split(":")[-1]}_0_1"')
    s += '\t\t(embedded_fonts no)\n\t)\n'
    return s


def write_lib():
    os.makedirs("symbols", exist_ok=True)
    body = lib_symbol(SYM)
    open(f"symbols/{LIB}.kicad_sym", "w").write(
        '(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "fcl_make_mech_sheet")\n\t(generator_version "10.0")\n'
        + body + ')\n')


def write_sheet():
    out = ['(kicad_sch\n\t(version 20260306)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n'
           f'\t(uuid "{SHEET_UUID}")\n\t(paper "A3")\n\t(title_block\n\t\t(title "FPGA CAM LCD - mechanical BOM (no footprints)")\n'
           '\t\t(rev "0.1")\n\t\t(comment 1 "One symbol per mechanical line item; Qty field = quantity per finished unit.")\n'
           '\t\t(comment 2 "Generated by scripts/make_mech_sheet.py - edit PARTS there and re-run.")\n\t)\n'
           '\t(lib_symbols\n' + "\n".join("\t" + l if l else l for l in lib_symbol(f"{LIB}:{SYM}").split("\n")).rstrip("\t") + '\t)\n']
    x0, y0, dy = 30.48, 38.1, 12.7
    cat = None
    row = 0
    col_x = [x0, x0 + 190.5]
    per_col = 11
    for i, (ref, val, f) in enumerate(PARTS):
        cx = col_x[0] if i < per_col else col_x[1]
        cy = y0 + (i if i < per_col else i - per_col) * dy
        s = (f'\t(symbol\n\t\t(lib_id "{LIB}:{SYM}")\n\t\t(at {cx:.2f} {cy:.2f} 0)\n\t\t(unit 1)\n\t\t(body_style 1)\n'
             '\t\t(exclude_from_sim yes)\n\t\t(in_bom yes)\n\t\t(on_board no)\n\t\t(in_pos_files no)\n\t\t(dnp no)\n'
             f'\t\t(uuid "{U()}")\n')
        s += prop("Reference", ref, cx + 3.81, cy - 1.27, hide=False)
        s += prop("Value", val, cx + 12.7, cy - 1.27, hide=False)
        s += prop("Footprint", "", cx, cy)
        s += prop("Datasheet", f.get("Supplier_Link", ""), cx, cy)
        s += prop("Description", f.get("Notes", ""), cx, cy)
        for k in FIELDS:
            vis = k in ("Category", "Qty", "MPN")
            xoff = {"Category": 3.81, "Qty": 30.48, "MPN": 45.72}.get(k, 0)
            s += prop(k, f.get(k, ""), cx + xoff, cy + 2.54, hide=not vis, size=1.0)
        s += (f'\t\t(instances\n\t\t\t(project "FCL"\n\t\t\t\t(path "/{ROOT_UUID}/{SHEET_UUID}"\n'
              f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
        out.append(s)
    out.append('\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')
    open("mechanical.kicad_sch", "w").write("".join(out))


def hook_root():
    r = open("FCL.kicad_sch").read()
    if SHEET_UUID in r:
        return False
    pages = [int(p) for p in re.findall(r'\(page "(\d+)"\)', r)]
    page = max(pages) + 1
    sheet = f'''	(sheet
		(at 242.57 193.04)
		(size 19.05 11.43)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(dnp no)
		(stroke
			(width 0)
			(type solid)
		)
		(fill
			(color 0 0 0 0)
		)
		(uuid "{SHEET_UUID}")
		(property "Sheetname" "mechanical"
			(at 242.57 192.201 0)
			(show_name no)
			(do_not_autoplace no)
			(effects
				(font
					(size 1.524 1.524)
				)
				(justify left bottom)
			)
		)
		(property "Sheetfile" "mechanical.kicad_sch"
			(at 242.824 204.978 0)
			(show_name no)
			(do_not_autoplace no)
			(effects
				(font
					(size 1.524 1.524)
				)
				(justify left top)
			)
		)
		(instances
			(project "FCL"
				(path "/{ROOT_UUID}"
					(page "{page}")
				)
			)
		)
	)
'''
    i = r.index("\t(sheet_instances")
    open("FCL.kicad_sch", "w").write(r[:i] + sheet + r[i:])
    t = open("sym-lib-table").read()
    if f'(name "{LIB}")' not in t:
        t = t.rstrip().rstrip(")") + f'\t(lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/symbols/{LIB}.kicad_sym") (options "") (descr "FCL mechanical BOM parts"))\n)\n'
        open("sym-lib-table", "w").write(t)
    return True


if __name__ == "__main__":
    write_lib()
    write_sheet()
    print("root sheet hooked" if hook_root() else "root sheet already hooked", "| parts:", len(PARTS))
