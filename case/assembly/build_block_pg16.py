#!/usr/bin/env python3
"""Battery end block for purchased PG16 brass blanking plugs (study, cells at 27 mm pitch).

PG16: thread OD 22.5 mm, 18 TPI (pitch 1.41), tap drill ~21.0; brass plug head 26 mm (Lapp SKINDICHT BL
PG16 / Phoenix 1674516). Threads are drawn as plain bores at the tap-drill size (cut them with a PG16 tap).
The current PCB has the cells at 20.5 mm pitch, so this needs the board to grow from 79 to about 92 mm.

    python case/assembly/build_block_pg16.py    # -> case/print/FCL_battery_block_PG16.step/.stl + renders
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_assembly as A  # noqa: E402
import cadquery as cq  # noqa: E402
from build_case import box, zcyl, xcyl  # noqa: E402

PRINT = os.path.join(A.REPO, "case", "print")
PARTS = os.path.join(A.BUILD, "pg16_parts")
RENDERS = os.path.join(A.REPO, "case", "renders")

PITCH = 27.0                 # 26 mm plug head + 1 mm
ROWS = (36.0 - PITCH, 36.0, 36.0 + PITCH)      # middle cell stays where it is
CZ = A.CELL_AXIS_Z           # -11.8 (unchanged, so the TFT and ribbon depth do not move)
THREAD_OD = 22.5
TAP_DRILL = 21.0
HEAD_D, HEAD_T = 26.0, 3.0
THREAD_LEN = 6.0
BLK_X = (-3.0, 5.5)
BLK_Y = (ROWS[0] - HEAD_D / 2 - 1.5, ROWS[2] + HEAD_D / 2 + 1.5)
BLK_Z = (CZ - THREAD_OD / 2 - 2.0, 0.0)        # 2 mm of brass past the thread on the eye side
BOARD_Y = (BLK_Y[0] - 1.0, BLK_Y[1] + 1.0)     # board edge needed (current board is 0 .. 79)


def make_block():
    b = box(BLK_X[0], BLK_Y[0], BLK_X[1], BLK_Y[1], BLK_Z[0], BLK_Z[1])
    # outboard of the board edge the block wraps the PCB thickness (more metal around the thread)
    b = b.union(box(BLK_X[0], BLK_Y[0], -0.2, BLK_Y[1], -0.1, A.PCB_T))
    for row in ROWS:
        b = b.cut(xcyl(BLK_X[0] - 1, BLK_X[1] + 1, row, CZ, TAP_DRILL / 2))
        # O-ring seat / thread lead-in
        b = b.cut(cq.Workplane("YZ").circle(THREAD_OD / 2 + 0.4).extrude(0.8)
                  .translate((A.P(BLK_X[0] - 0.01, row)[0], A.P(0, row)[1], CZ)))
    for y in (ROWS[0] + PITCH / 2, ROWS[1] + PITCH / 2):       # two M3 tapped fixing holes from the PCB side
        b = b.cut(zcyl(2.6, y, 1.25, -6.0, 0.1))
    return b


def make_plug(row):
    X, Y = A.P(BLK_X[0], row)
    head = cq.Workplane("YZ").circle(HEAD_D / 2).extrude(-HEAD_T).edges().chamfer(0.4)
    head = head.cut(cq.Workplane("XY").box(1.6, 2.0, HEAD_D + 1).rotate((0, 0, 0), (1, 0, 0), 35)
                    .translate((-HEAD_T, 0, 0)))                # coin slot
    stem = cq.Workplane("YZ").circle(THREAD_OD / 2 - 0.1).extrude(THREAD_LEN)
    return head.union(stem).translate((X, Y, CZ))


def main():
    os.makedirs(PARTS, exist_ok=True)
    blk = make_block()
    s = blk.val()
    print("block solids", len(s.Solids()), "volume cm3", round(s.Volume() / 1000, 1),
          "mass brass g", round(s.Volume() / 1000 * 8.5), "mass aluminium g", round(s.Volume() / 1000 * 2.7))
    print("block y", BLK_Y, "z", BLK_Z, "board needs y", BOARD_Y, "height", BOARD_Y[1] - BOARD_Y[0])
    print("wall thread->PCB face", round(-CZ - THREAD_OD / 2, 2), " web between threads", PITCH - THREAD_OD)
    cq.exporters.export(blk, os.path.join(PRINT, "FCL_battery_block_PG16.step"))
    cq.exporters.export(blk, os.path.join(PRINT, "FCL_battery_block_PG16.stl"), tolerance=0.05, angularTolerance=0.2)
    plugs = [make_plug(r) for r in ROWS]
    pulled = plugs[2].translate((-14, 0, 0))
    cells = None
    for row in ROWS:
        c = xcyl(A.CELL_PLUS_X - A.CELL_L, A.CELL_PLUS_X, row, CZ, A.CELL_D / 2)
        cells = c if cells is None else cells.union(c)
    out = {"block": blk, "plugs": plugs[0].union(plugs[1]).union(pulled), "cells": cells,
           "pcb_now": box(0, 0, 85, 79, 0, A.PCB_T),
           "pcb_growth": box(0, BOARD_Y[0], 85, 0, 0, A.PCB_T).union(box(0, 79, 85, BOARD_Y[1], 0, A.PCB_T))}
    for n, w in out.items():
        cq.exporters.export(w, os.path.join(PARTS, n + ".stl"), tolerance=0.05, angularTolerance=0.2)
    render()


def render():
    import vtk
    col = {"block": (0.80, 0.70, 0.35), "plugs": (0.88, 0.88, 0.90), "cells": (0.90, 0.50, 0.78),
           "pcb_now": (0.20, 0.55, 0.28), "pcb_growth": (0.95, 0.45, 0.35)}

    def shot(fname, view):
        ren = vtk.vtkRenderer()
        ren.SetBackground(1, 1, 1)
        for n, c in col.items():
            r = vtk.vtkSTLReader()
            r.SetFileName(os.path.join(PARTS, n + ".stl"))
            nm = vtk.vtkPolyDataNormals()
            nm.SetInputConnection(r.GetOutputPort())
            nm.SetFeatureAngle(40)
            m = vtk.vtkPolyDataMapper()
            m.SetInputConnection(nm.GetOutputPort())
            a = vtk.vtkActor()
            a.SetMapper(m)
            a.GetProperty().SetColor(*c)
            a.GetProperty().SetAmbient(0.35)
            a.GetProperty().SetDiffuse(0.75)
            ren.AddActor(a)
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
            ea = vtk.vtkActor()
            ea.SetMapper(em)
            ea.GetProperty().SetColor(0.08, 0.08, 0.1)
            ea.GetProperty().SetLineWidth(1.2)
            ren.AddActor(ea)
        win = vtk.vtkRenderWindow()
        win.SetOffScreenRendering(1)
        win.SetSize(1700, 1300)
        win.AddRenderer(ren)
        cam = ren.GetActiveCamera()
        cam.ParallelProjectionOn()
        cam.SetFocalPoint(0, 0, 0)
        cam.SetPosition(*view)
        cam.SetViewUp(0, 1, 0)
        ren.ResetCamera()
        cam.Zoom(1.2)
        ren.RemoveAllLights()
        for d, i in (((1, 1, 1), 0.75), ((-1, 0.5, 0.3), 0.45), ((0, -1, -1), 0.45), ((0.3, -0.3, 1), 0.35)):
            lt = vtk.vtkLight()
            lt.SetLightTypeToCameraLight()
            lt.SetPosition(*d)
            lt.SetIntensity(i)
            ren.AddLight(lt)
        win.Render()
        w2i = vtk.vtkWindowToImageFilter()
        w2i.SetInput(win)
        w2i.Update()
        wr = vtk.vtkPNGWriter()
        wr.SetFileName(os.path.join(RENDERS, fname))
        wr.SetInputConnection(w2i.GetOutputPort())
        wr.Write()
        print("wrote", fname)

    shot("pg16_1_block_plugs.png", (-1.0, 0.45, -0.9))
    shot("pg16_2_end_view.png", (-1.0, 0.0, -0.02))


if __name__ == "__main__":
    main()
