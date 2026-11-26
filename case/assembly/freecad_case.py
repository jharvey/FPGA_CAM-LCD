"""Collect the case into one FreeCAD document: printed parts as editable solids (from STEP), everything else as
light reference meshes.  freecadcmd freecad_case.py <repo>/case <outfile.FCStd>"""
import os
import sys

import FreeCAD as App
import Part
import Mesh

case, out = sys.argv[-2], sys.argv[-1]
doc = App.newDocument("FCL_case")
PRINT = os.path.join(case, "print")
PARTS = os.path.join(case, "build", "case_parts")
grp_p = doc.addObject("App::DocumentObjectGroup", "Printed_parts_edit_these")
grp_m = doc.addObject("App::DocumentObjectGroup", "Machined_parts")
grp_r = doc.addObject("App::DocumentObjectGroup", "Reference_meshes_do_not_edit")
COL = {"FCL_case_rear": (0.40, 0.60, 0.95), "FCL_case_front": (0.45, 0.82, 0.62), "FCL_cell_cradle": (0.98, 0.80, 0.30),
       "FCL_button_actuators": (0.90, 0.28, 0.22), "FCL_battery_block_right": (0.72, 0.74, 0.78)}
for name, grp in (("FCL_case_rear", grp_p), ("FCL_case_front", grp_p), ("FCL_cell_cradle", grp_p),
                  ("FCL_button_actuators", grp_p), ("FCL_battery_block_right", grp_m)):
    s = Part.Shape()
    s.read(os.path.join(PRINT, name + ".step"))
    o = doc.addObject("Part::Feature", name)
    o.Shape = s
    grp.addObject(o)
    print(name, "solids", len(s.Solids), "volume cm3", round(s.Volume / 1000, 1))
for name in ("left_blocks", "PCB", "cells", "TFT", "camera", "ribbon", "caps", "slugs"):
    fn = os.path.join(PARTS, name + ".stl")
    if not os.path.exists(fn):
        continue
    m = doc.addObject("Mesh::Feature", name)
    m.Mesh = Mesh.Mesh(fn)
    (grp_m if name == "left_blocks" else grp_r).addObject(m)
doc.recompute()
doc.saveAs(out)
print("saved", out)
