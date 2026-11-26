"""Build a parametric FreeCAD model of the MS3181 battery end block (variants A and B).

Every dimension lives in the spreadsheet "Params" (alias per cell); the solids are Part primitives whose sizes and
placements are expressions on those aliases, combined with Fuse / Cut.  Change a value in Params, press Recompute.
Frame = the machining drawing: origin at datums A (mounting face, Z = 0), B (plate inner face, X = 0), C (bore
centre plane, Y = 0); +X into the board, block at negative Z.

    freecadcmd freecad_battery_block.py <outdir>
"""
import os
import sys

import FreeCAD as App
import Part  # noqa: F401  (registers Part feature types)

OUT = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].endswith(".py") else "."

PARAMS = [  # alias, value, unit, note
    ("cz", -11.8, "mm", "cell axis Z below face A"),
    ("plate_t", 2.8, "mm", "shoulder plate thickness (X)"),
    ("plate_half", 14.0, "mm", "plate half width (Y)"),
    ("z_bot", -25.8, "mm", "block bottom Z"),
    ("z_top", 2.2, "mm", "plate top Z (beside the PCB edge)"),
    ("flange_len", 7.2, "mm", "flange on the PCB (X)"),
    ("flange_half", 12.5, "mm", "flange half width (Y)"),
    ("relief", 0.6, "mm", "face A relief except the bosses"),
    ("boss_d", 24.0, "mm", "bayonet boss OD  * PROVISIONAL"),
    ("boss_len", 10.5, "mm", "bayonet boss length outboard of the plate"),
    ("bore_d", 19.2, "mm", "cell bore"),
    ("groove_id", 20.2, "mm", "O-ring groove ID (end face)"),
    ("groove_od", 23.0, "mm", "O-ring groove OD"),
    ("groove_depth", 0.75, "mm", "O-ring groove depth (O-ring 20 x 1)"),
    ("pin_d", 2.4, "mm", "bayonet pin hole  * PROVISIONAL"),
    ("pin_from_tip", 6.5, "mm", "pin axis from boss end face  * PROVISIONAL"),
    ("pin_a1", 90.0, "", "first pin angle, deg (90 = toward face A)  * PROVISIONAL"),
    ("pin_step", 120.0, "", "angle between pins, deg"),
    ("screw_x", 4.6, "mm", "M2.5 tapped hole X from B"),
    ("screw_y", -9.7, "mm", "M2.5 tapped hole Y from C"),
    ("screw_drill", 2.05, "mm", "M2.5x0.45 tap drill (thread 5.0 min)"),
    ("screw_depth", 5.5, "mm", "drill depth from A"),
    ("screw_boss_d", 4.6, "mm", "screw boss on face A"),
    ("dowel_x", 3.2, "mm", "dowel hole X from B"),
    ("dowel_y", 9.3, "mm", "dowel hole Y from C: A = 9.3, B = 7.5"),
    ("dowel_d", 2.0, "mm", "dowel hole (H7, 2 mm press dowel)"),
    ("dowel_depth", 3.5, "mm", "dowel hole depth"),
    ("dowel_boss_d", 3.2, "mm", "dowel boss on face A"),
    ("pocket_x0", 4.2, "mm", "header-tail pocket start X"),
    ("pocket_y0", 9.9, "mm", "header-tail pocket start Y"),
    ("pocket_depth", 4.0, "mm", "pocket depth from A"),
]


def build(variant):
    doc = App.newDocument(f"FCL_BatteryBlock_MS3181_{variant}")
    sh = doc.addObject("Spreadsheet::Sheet", "Params")
    sh.set("A1", "alias")
    sh.set("B1", "value")
    sh.set("C1", "note")
    for i, (alias, val, unit, note) in enumerate(PARAMS, start=2):
        if alias == "dowel_y" and variant == "B":
            val = 7.5
        sh.set(f"A{i}", alias)
        sh.set(f"B{i}", f"={val} {unit}".strip() if unit else f"={val}")
        sh.setAlias(f"B{i}", alias)
        sh.set(f"C{i}", note)
    sh.set(f"A{len(PARAMS) + 3}", "variant")
    sh.set(f"B{len(PARAMS) + 3}", variant)
    doc.recompute()

    def box(name, L, W, H, x, y, z):
        o = doc.addObject("Part::Box", name)
        for prop, ex in (("Length", L), ("Width", W), ("Height", H), (".Placement.Base.x", x), (".Placement.Base.y", y),
                         (".Placement.Base.z", z)):
            o.setExpression(prop, ex)
        return o

    def cyl(name, r, h, x, y, z, axis=(0, 0, 1), angle=None, angle_expr=None):
        o = doc.addObject("Part::Cylinder", name)
        o.setExpression("Radius", r)
        o.setExpression("Height", h)
        if angle is not None:
            o.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(*axis), angle))
        for prop, ex in ((".Placement.Base.x", x), (".Placement.Base.y", y), (".Placement.Base.z", z)):
            o.setExpression(prop, ex)
        if angle_expr:
            o.setExpression(".Placement.Rotation.Angle", angle_expr)
        return o

    # ---- solids
    plate = box("Plate", "Params.plate_t", "2 * Params.plate_half", "Params.z_top - Params.z_bot",
                "-Params.plate_t", "-Params.plate_half", "Params.z_bot")
    flange = box("Flange", "Params.flange_len", "2 * Params.flange_half", "-Params.relief - Params.z_bot",
                 "0 mm", "-Params.flange_half", "Params.z_bot")
    sboss = cyl("ScrewBoss", "Params.screw_boss_d / 2", "Params.relief", "Params.screw_x", "Params.screw_y", "-Params.relief")
    dboss = cyl("DowelBoss", "Params.dowel_boss_d / 2", "Params.relief", "Params.dowel_x", "Params.dowel_y", "-Params.relief")
    boss = cyl("BayonetBoss", "Params.boss_d / 2", "Params.boss_len + 0.01 mm", "-Params.plate_t + 0.01 mm", "0 mm", "Params.cz",
               axis=(0, 1, 0), angle=-90)                                   # +Z -> -X
    body = doc.addObject("Part::MultiFuse", "BlockBody")
    body.Shapes = [plate, flange, sboss, dboss, boss]

    # ---- cutters
    tip = "(-Params.plate_t - Params.boss_len)"
    bore = cyl("Bore", "Params.bore_d / 2", "Params.boss_len + Params.plate_t + Params.flange_len + 2 mm",
               f"{tip} - 1 mm", "0 mm", "Params.cz", axis=(0, 1, 0), angle=90)   # +Z -> +X
    g_out = cyl("GrooveOD", "Params.groove_od / 2", "Params.groove_depth + 0.01 mm", f"{tip} - 0.01 mm", "0 mm",
                "Params.cz", axis=(0, 1, 0), angle=90)
    g_in = cyl("GrooveID", "Params.groove_id / 2", "Params.groove_depth + 0.5 mm", f"{tip} - 0.2 mm", "0 mm",
               "Params.cz", axis=(0, 1, 0), angle=90)
    groove = doc.addObject("Part::Cut", "ORingGroove")
    groove.Base = g_out
    groove.Tool = g_in
    pins = []
    for k in range(3):
        a = f"(Params.pin_a1 + {k} * Params.pin_step)"
        r0 = "(Params.bore_d / 2 - 0.5 mm)"
        p = doc.addObject("Part::Cylinder", f"PinHole{k + 1}")
        p.setExpression("Radius", "Params.pin_d / 2")
        p.setExpression("Height", "(Params.boss_d - Params.bore_d) / 2 + 1 mm")
        p.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 0))
        p.setExpression(".Placement.Rotation.Angle", f"({a} - 90) * 1 deg")      # Z axis -> (0, cos a, sin a)
        p.setExpression(".Placement.Base.x", f"{tip} + Params.pin_from_tip")
        p.setExpression(".Placement.Base.y", f"cos({a} * 1 deg) * {r0}")
        p.setExpression(".Placement.Base.z", f"Params.cz + sin({a} * 1 deg) * {r0}")
        pins.append(p)
    shole = cyl("ScrewTapDrill_M2_5", "Params.screw_drill / 2", "Params.screw_depth + 0.5 mm", "Params.screw_x",
                "Params.screw_y", "-Params.screw_depth")
    dhole = cyl("DowelHole", "Params.dowel_d / 2", "Params.dowel_depth + 0.5 mm", "Params.dowel_x", "Params.dowel_y",
                "-Params.dowel_depth")
    pocket = box("HeaderPocket", "Params.flange_len - Params.pocket_x0 + 1 mm", "Params.flange_half - Params.pocket_y0 + 1 mm",
                 "Params.pocket_depth + 1 mm", "Params.pocket_x0", "Params.pocket_y0", "-Params.pocket_depth")
    tools = doc.addObject("Part::MultiFuse", "Cutters")
    tools.Shapes = [bore, groove] + pins + [shole, dhole, pocket]
    blk = doc.addObject("Part::Cut", f"BatteryBlock_{variant}")
    blk.Base = body
    blk.Tool = tools
    doc.recompute()
    bad = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
    s = blk.Shape
    print(f"variant {variant}: valid {s.isValid()}, solids {len(s.Solids)}, volume {s.Volume / 1000:.3f} cm3, "
          f"mass {s.Volume / 1000 * 2.70:.1f} g, bbox {[round(v, 2) for v in (s.BoundBox.XMin, s.BoundBox.XMax, s.BoundBox.YMin, s.BoundBox.YMax, s.BoundBox.ZMin, s.BoundBox.ZMax)]}, errors {bad}")
    fn = os.path.join(OUT, f"FCL_BatteryBlock_MS3181_{variant}.FCStd")
    doc.saveAs(fn)
    import Import
    Import.export([blk], os.path.join(OUT, f"FCL_BatteryBlock_MS3181_{variant}_from_freecad.step"))
    # parametric test: change the boss OD and check the volume reacts, then restore (not saved)
    v0 = s.Volume
    sh.set("B10", "=25 mm")
    doc.recompute()
    print(f"  param test: boss_d 24 -> 25 changes volume by {(blk.Shape.Volume - v0):.1f} mm3")
    App.closeDocument(doc.Name)
    return fn


os.makedirs(OUT, exist_ok=True)
for v in ("A", "B"):
    print("saved", build(v))
