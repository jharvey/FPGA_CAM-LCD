"""Collect the case into one FreeCAD document: printed parts as editable solids (from STEP), everything else as
light reference meshes.

    freecadcmd freecad_case.py <repo>/case <outfile.FCStd>            removable cells (blocks + caps)
    freecadcmd freecad_case.py <repo>/case <outfile.FCStd> fixed      fixed cells (spring contacts)
"""
import os
import sys

import FreeCAD as App
import Part
import Mesh

fixed = sys.argv[-1] == "fixed"
case, out = (sys.argv[-3], sys.argv[-2]) if fixed else (sys.argv[-2], sys.argv[-1])
doc = App.newDocument("FCL_case_fixed" if fixed else "FCL_case")
PRINT = os.path.join(case, "print")
PARTS = os.path.join(case, "build", "case_parts_fixed" if fixed else "case_parts")
grp_p = doc.addObject("App::DocumentObjectGroup", "Printed_parts_edit_these")
grp_m = doc.addObject("App::DocumentObjectGroup", "Machined_parts")
grp_r = doc.addObject("App::DocumentObjectGroup", "Reference_meshes_do_not_edit")
sfx = "_fixed" if fixed else ""
# object name, file in case/print, group
solids = [("FCL_case_rear", "FCL_case_rear" + sfx, grp_p), ("FCL_case_front", "FCL_case_front" + sfx, grp_p),
          ("FCL_cell_cradle", "FCL_cell_cradle" + sfx, grp_p), ("FCL_button_actuators", "FCL_button_actuators", grp_p), ("FCL_button_caps", "FCL_button_caps", grp_p),
          ("FCL_cell_cradle_top", "FCL_cell_cradle_top", grp_p)]
if not fixed:
    solids.append(("FCL_battery_block_right", "FCL_battery_block_right", grp_m))
for name, fn, grp in solids:
    s = Part.Shape()
    s.read(os.path.join(PRINT, fn + ".step"))
    o = doc.addObject("Part::Feature", name)
    o.Shape = s
    grp.addObject(o)
    print(name, "solids", len(s.Solids), "volume cm3", round(s.Volume / 1000, 1))
for name in ("left_blocks", "PCB", "cells", "TFT", "camera", "ribbon", "caps", "slugs", "springs", "plus_contacts",
             "hw_case_screws", "hw_case_inserts", "hw_cam_screws", "hw_cam_inserts", "hw_block_screws", "hw_block_washers"):
    fn = os.path.join(PARTS, name + ".stl")
    if not os.path.exists(fn):
        continue
    m = doc.addObject("Mesh::Feature", name)
    m.Mesh = Mesh.Mesh(fn)
    (grp_m if name == "left_blocks" else grp_r).addObject(m)
doc.recompute()
doc.saveAs(out)
print("saved", out)
