#!/usr/bin/env python3
"""Shaded orthographic renders of the case parts (reads case/build/case_parts/*.stl).

    python case/assembly/render_case.py        # writes case/renders/case_*.png
    FCL_BATTERY=fixed python case/assembly/render_case.py     # fixed-cell variant: case/renders/fixed_*.png
"""
import os
import vtk

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXED = os.environ.get("FCL_BATTERY", "") == "fixed"
PARTS = os.path.join(REPO, "case", "build", "case_parts_fixed" if FIXED else "case_parts")
OUT = os.path.join(REPO, "case", "renders")

COL = {"PCB": (0.20, 0.55, 0.28), "TFT": (0.30, 0.30, 0.36), "camera": (0.40, 0.40, 0.48),
       "cells": (0.90, 0.50, 0.78), "ribbon": (0.95, 0.62, 0.20),
       "FCL_battery_block_right": (0.70, 0.72, 0.76), "left_blocks": (0.70, 0.72, 0.76), "caps": (0.33, 0.36, 0.28), "slugs": (0.88, 0.72, 0.38), "FCL_cell_cradle": (0.98, 0.80, 0.30),
       "FCL_case_rear": (0.40, 0.60, 0.95), "FCL_case_front": (0.45, 0.82, 0.62), "FCL_button_actuators": (0.90, 0.28, 0.22), "FCL_cell_cradle_top": (0.98, 0.70, 0.20),
       "hw_case_screws": (0.15, 0.15, 0.17), "hw_cam_screws": (0.15, 0.15, 0.17), "hw_block_screws": (0.15, 0.15, 0.17),
       "hw_case_inserts": (0.80, 0.62, 0.25), "hw_cam_inserts": (0.80, 0.62, 0.25),
       "caps_L": (0.33, 0.36, 0.28), "caps_R": (0.33, 0.36, 0.28), "slugs_L": (0.88, 0.72, 0.38), "slugs_R": (0.88, 0.72, 0.38)}
COL["springs"] = (0.80, 0.80, 0.84)
COL["plus_contacts"] = (0.80, 0.80, 0.84)
# exploded offsets along Z (eye side is -Z)
EXPLODE = {"FCL_case_front": 45, "camera": 18, "PCB": 0, "FCL_battery_block_right": -6, "left_blocks": -6, "caps": -6, "slugs": -6, "FCL_cell_cradle": -22,
           "cells": -22, "ribbon": -40, "TFT": -55, "FCL_button_actuators": -70, "FCL_cell_cradle_top": -30, "hw_case_screws": 60, "hw_cam_screws": 30,
           "hw_block_screws": 10, "hw_case_inserts": -85, "hw_cam_inserts": 45, "FCL_case_rear": -85}
# full exploded layout: (dx, dz) per part - caps and slugs pulled out sideways along the cell axes
EXPLODE2 = {"FCL_case_front": (0, 60), "camera": (0, 26), "PCB": (0, 0), "FCL_battery_block_right": (14, 0),
            "left_blocks": (-14, 0), "caps_L": (-48, 0), "caps_R": (48, 0), "slugs_L": (-30, 0), "slugs_R": (30, 0),
            "FCL_cell_cradle": (0, -30), "cells": (0, -30), "FCL_cell_cradle_top": (0, -44),
            "hw_case_screws": (0, 85), "hw_cam_screws": (0, 18), "hw_block_screws": (0, 12), "hw_case_inserts": (0, -112),
            "hw_cam_inserts": (0, 60), "ribbon": (0, -52), "TFT": (0, -70),
            "FCL_button_actuators": (0, -92), "FCL_case_rear": (0, -112)}


def actor(name, dz=0.0, opacity=1.0, dx=0.0):
    r = vtk.vtkSTLReader()
    r.SetFileName(os.path.join(PARTS, name + ".stl"))
    n = vtk.vtkPolyDataNormals()
    n.SetInputConnection(r.GetOutputPort())
    n.SetFeatureAngle(40)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*COL[name])
    p.SetAmbient(0.35)
    p.SetDiffuse(0.75)
    p.SetSpecular(0.05)
    p.SetOpacity(opacity)
    a.SetPosition(dx, 0, dz)
    # silhouette / feature edges so shapes read clearly
    fe = vtk.vtkFeatureEdges()
    fe.SetInputConnection(r.GetOutputPort())
    fe.BoundaryEdgesOff()
    fe.NonManifoldEdgesOff()
    fe.ManifoldEdgesOff()
    fe.FeatureEdgesOn()
    fe.SetFeatureAngle(35)
    fe.ColoringOff()
    em = vtk.vtkPolyDataMapper()
    em.SetInputConnection(fe.GetOutputPort())
    em.SetResolveCoincidentTopologyToPolygonOffset()
    ea = vtk.vtkActor()
    ea.SetMapper(em)
    ea.GetProperty().SetColor(0.08, 0.08, 0.10)
    ea.GetProperty().SetLineWidth(1.2)
    ea.SetPosition(dx, 0, dz)
    return a, ea


def shot(fname, names, view, up, explode=False, size=(1700, 1300), hide_edges=(), zoom=1.25):
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    for nm in names:
        if explode == 2:
            dx, dz = EXPLODE2[nm]
        else:
            dx, dz = 0.0, (EXPLODE[nm] if explode else 0.0)
        a, e = actor(nm, dz, dx=dx)
        ren.AddActor(a)
        if nm not in hide_edges:
            ren.AddActor(e)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*size)
    win.AddRenderer(ren)
    cam = ren.GetActiveCamera()
    cam.ParallelProjectionOn()
    cam.SetFocalPoint(0, 0, 0)
    cam.SetPosition(*view)
    cam.SetViewUp(*up)
    ren.ResetCamera()
    cam.Zoom(zoom)
    ren.RemoveAllLights()
    for d, i in (((1, 1, 1), 0.75), ((-1, 0.5, 0.3), 0.45), ((0, -1, -1), 0.45), ((0.3, -0.3, 1), 0.35)):
        l = vtk.vtkLight()
        l.SetLightTypeToCameraLight()
        l.SetPosition(*d)
        l.SetIntensity(i)
        ren.AddLight(l)
    win.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(os.path.join(OUT, fname))
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    print("wrote", fname, flush=True)


ALL = ["FCL_cell_cradle_top", "hw_case_screws", "hw_cam_screws", "hw_block_screws", "hw_case_inserts", "hw_cam_inserts", "caps", "FCL_button_actuators", "PCB", "camera", "cells", "ribbon", "TFT", "FCL_battery_block_right", "left_blocks", "FCL_cell_cradle", "FCL_case_rear", "FCL_case_front"]
INNER = ["FCL_cell_cradle_top", "hw_case_screws", "hw_cam_screws", "hw_block_screws", "hw_case_inserts", "hw_cam_inserts", "caps", "slugs", "PCB", "camera", "cells", "ribbon", "TFT", "FCL_battery_block_right", "left_blocks", "FCL_cell_cradle"]
# STEP frame: +X = board x, +Y = board up (toward SD card edge), +Z = camera side, -Z = eye side
os.makedirs(OUT, exist_ok=True)
if FIXED:
    EXPLODE2["springs"] = (0, 0)
    EXPLODE2["plus_contacts"] = (0, 0)
    F_INNER = ["FCL_cell_cradle_top", "hw_case_screws", "hw_cam_screws", "hw_case_inserts", "hw_cam_inserts", "PCB", "camera",
               "cells", "ribbon", "TFT", "springs", "plus_contacts", "FCL_cell_cradle"]
    F_ALL = F_INNER + ["FCL_button_actuators", "FCL_case_rear", "FCL_case_front"]
    shot("fixed_1_springs_and_cells.png", ["PCB", "cells", "springs", "plus_contacts"], (-1.0, 0.45, -0.9), (0, 1, 0))
    shot("fixed_8_contacts_top_view.png", ["PCB", "cells", "springs", "plus_contacts"], (0.0, 0.0, -1.0), (0, 1, 0))
    shot("fixed_9_cradle_over_contacts.png", ["PCB", "FCL_cell_cradle", "springs", "plus_contacts"], (-0.9, 0.5, -1.0), (0, 1, 0))
    shot("fixed_10_cradle_top_view.png", ["PCB", "FCL_cell_cradle", "springs", "plus_contacts"], (0.0, 0.0, -1.0), (0, 1, 0))
    shot("fixed_11_cradle_with_cells.png", ["PCB", "FCL_cell_cradle", "springs", "plus_contacts", "cells"], (-0.9, 0.5, -1.0), (0, 1, 0))
    shot("fixed_12_cradle_alone_pcb_side.png", ["FCL_cell_cradle"], (0.6, 0.5, 1.0), (0, 1, 0))
    shot("fixed_13_stack_before_shell.png", ["PCB", "FCL_cell_cradle", "springs", "plus_contacts", "cells", "FCL_cell_cradle_top", "TFT", "ribbon"], (-0.9, 0.5, -1.0), (0, 1, 0))
    shot("fixed_2_inner_assembly_eye_side.png", F_INNER, (-0.9, 0.5, -1.0), (0, 1, 0))
    shot("fixed_3_closed_eye_side.png", F_ALL, (-0.9, 0.5, -1.0), (0, 1, 0))
    shot("fixed_4_closed_camera_side.png", F_ALL, (0.9, 0.5, 1.0), (0, 1, 0))
    shot("fixed_5_exploded_eye_side.png", F_ALL, (-0.75, 0.55, -0.9), (0, 1, 0), explode=2, size=(2200, 1700), zoom=1.1)
    shot("fixed_6_rear_shell_inside.png", ["FCL_case_rear"], (-0.5, 0.6, 1.0), (0, 1, 0))
    shot("fixed_7_closed_left_side.png", F_ALL, (-1.0, 0.2, -0.35), (0, 1, 0))
    raise SystemExit
shot("case_1_blocks_and_cells.png", ["PCB", "cells", "caps", "slugs", "FCL_battery_block_right", "left_blocks", "FCL_cell_cradle"], (-1.0, 0.45, -0.9), (0, 1, 0))
shot("case_2_inner_assembly_eye_side.png", INNER, (-0.9, 0.5, -1.0), (0, 1, 0))
shot("case_3_closed_eye_side.png", ALL, (-0.9, 0.5, -1.0), (0, 1, 0))
shot("case_4_closed_camera_side.png", ALL, (0.9, 0.5, 1.0), (0, 1, 0))
shot("case_5_exploded.png", ALL, (-1.0, 0.25, -0.35), (0, 1, 0), explode=True, size=(2000, 1300))
shot("case_6_rear_shell_inside.png", ["FCL_case_rear"], (-0.5, 0.6, 1.0), (0, 1, 0))
shot("case_7_front_shell_inside.png", ["FCL_case_front"], (0.5, 0.6, -1.0), (0, 1, 0))

EXPL = ["FCL_cell_cradle_top", "hw_case_screws", "hw_cam_screws", "hw_block_screws", "hw_case_inserts", "hw_cam_inserts", "caps_L", "caps_R", "slugs_L", "slugs_R", "FCL_button_actuators", "PCB", "camera", "cells", "ribbon", "TFT",
        "FCL_battery_block_right", "left_blocks", "FCL_cell_cradle", "FCL_case_rear", "FCL_case_front"]
shot("case_8_exploded_camera_side.png", EXPL, (0.75, 0.55, 0.9), (0, 1, 0), explode=2, size=(2200, 1700), zoom=1.1)
shot("case_9_exploded_eye_side.png", EXPL, (-0.75, 0.55, -0.9), (0, 1, 0), explode=2, size=(2200, 1700), zoom=1.1)
shot("case_10_exploded_side.png", EXPL, (0.15, 1.0, 0.05), (0, 0, 1), explode=2, size=(2200, 1700), zoom=1.1)
shot("case_11_exploded_low.png", EXPL, (-0.6, -0.8, 0.5), (0, 0, 1), explode=2, size=(2200, 1700), zoom=1.1)
shot("case_12_bottom_tripod.png", ALL, (-0.4, -1.0, -0.5), (0, 0, -1))
shot("case_13_front_shell_camera_frame.png", ["FCL_case_front", "camera"], (0.4, 0.5, -1.0), (0, 1, 0))
shot("case_14_rear_shell_guides_retainer.png", ["FCL_case_rear", "FCL_button_actuators"], (-0.4, 0.6, 1.0), (0, 1, 0))
shot("case_15_camera_screwed_to_front.png", ["FCL_case_front", "camera", "hw_cam_screws", "hw_cam_inserts"], (0.4, 0.5, -1.0), (0, 1, 0))
shot("case_16_cradles_and_lcd.png", ["PCB", "cells", "FCL_cell_cradle", "FCL_cell_cradle_top", "TFT", "ribbon", "left_blocks", "FCL_battery_block_right"], (-0.9, 0.5, -1.0), (0, 1, 0))
shot("case_17_buttons_snap_in.png", ["FCL_case_rear", "FCL_button_actuators", "hw_case_inserts"], (-0.5, 0.7, 1.0), (0, 1, 0))
