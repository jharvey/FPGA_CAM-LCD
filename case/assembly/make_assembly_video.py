#!/usr/bin/env python3
"""Assembly animation of the FCL monocular (reads case/build/case_parts/*.stl, writes case/renders/FCL_assembly.mp4).

    python case/assembly/make_assembly_video.py
"""
import math
import os
import shutil
import subprocess
import vtk

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PARTS = os.path.join(REPO, "case", "build", "case_parts")
OUT = os.path.join(REPO, "case", "renders")
FR = os.path.join(REPO, "case", "build", "video_frames")
W, H, FPS = 1280, 720, 24
MOVE, HOLD = 40, 14                          # frames per step: motion, then pause

OX, OY = 78.0, 55.5
CZ = -11.8
ROW_Y = {1: -(OY + 15.5), 2: -(OY + 36.0), 3: -(OY + 56.5)}
CENTRE = (OX + 42.5, -(OY + 39.5), -2.0)

COL = {"PCB": (0.20, 0.55, 0.28), "TFT": (0.30, 0.30, 0.36), "camera": (0.25, 0.35, 0.75), "ribbon": (0.95, 0.62, 0.20),
       "cell1": (0.90, 0.50, 0.78), "cell2": (0.90, 0.50, 0.78), "cell3": (0.90, 0.50, 0.78),
       "FCL_battery_block_right": (0.72, 0.74, 0.78), "left_blocks": (0.72, 0.74, 0.78),
       "caps_L": (0.33, 0.36, 0.28), "caps_R": (0.33, 0.36, 0.28), "slugs_L": (0.88, 0.72, 0.38), "slugs_R": (0.88, 0.72, 0.38),
       "FCL_cell_cradle": (0.98, 0.80, 0.30), "FCL_case_rear": (0.40, 0.60, 0.95), "FCL_case_front": (0.45, 0.82, 0.62),
       "FCL_button_actuators": (0.90, 0.28, 0.22)}

STEPS = [
    ("1  PCB: screw the two left aluminium end blocks on (M2.5 screw + dowel), seat the right block", (-0.8, 0.45, -1.0)),
    ("2  Cell cradle onto the back of the PCB", (-0.8, 0.45, -1.0)),
    ("3  LCD: ribbon into J7, then lay the TFT on the cradle (LCD goes on before the case)", (-0.6, 0.5, -1.0)),
    ("4  Camera module onto the J1 header (camera side)", (0.8, 0.45, 1.0)),
    ("5  Button plungers into the rear shell", (-0.7, 0.55, -1.0)),
    ("6  PCB + LCD assembly drops into the rear shell", (-0.9, 0.35, -0.6)),
    ("7  Front shell on (frame + posts clamp the camera); 4 x M2.5 into the heat-set inserts", (0.8, 0.45, 0.9)),
    ("8  Cells slide in through the blocks: cells 1 and 3 from the left, cell 2 from the right", (0.15, 0.55, 1.0)),
    ("9  Brass slug + spring, then MS3181 cap: push on and turn 1/4", (0.15, 0.55, 1.0)),
    ("Done  -  1/4-20 tripod insert on the bottom face", (-0.9, -0.55, 0.6)),
]
# part -> list of (step, start offset, end offset); hidden before its first step
MOTION = {
    "PCB": [(0, (0, 0, 0), (0, 0, 0))],
    "left_blocks": [(0, (-35, 0, -25), (0, 0, 0))],
    "FCL_battery_block_right": [(0, (35, 0, -25), (0, 0, 0))],
    "FCL_cell_cradle": [(1, (0, 0, -45), (0, 0, 0))],
    "ribbon": [(2, (0, 0, -40), (0, 0, 0))],
    "TFT": [(2, (0, 0, -60), (0, 0, 0))],
    "camera": [(3, (0, 0, 45), (0, 0, 0))],
    "FCL_case_rear": [(4, (0, 0, -75), (0, 0, -75)), (5, (0, 0, -75), (0, 0, 0))],
    "FCL_button_actuators": [(4, (0, 0, -120), (0, 0, -75)), (5, (0, 0, -75), (0, 0, 0))],
    "FCL_case_front": [(6, (0, 0, 70), (0, 0, 0))],
    "cell1": [(7, (-95, 0, 0), (0, 0, 0))],
    "cell3": [(7, (-95, 0, 0), (0, 0, 0))],
    "cell2": [(7, (95, 0, 0), (0, 0, 0))],
    "slugs_L": [(8, (-55, 0, 0), (0, 0, 0))],
    "slugs_R": [(8, (55, 0, 0), (0, 0, 0))],
    "caps_L": [(8, (-80, 0, 0), (0, 0, 0))],
    "caps_R": [(8, (80, 0, 0), (0, 0, 0))],
}


def read(name):
    r = vtk.vtkSTLReader()
    r.SetFileName(os.path.join(PARTS, name + ".stl"))
    r.Update()
    return r.GetOutput()


def split_cells():
    pd = read("cells")
    out = {}
    for i, y in ROW_Y.items():
        c = vtk.vtkPolyDataConnectivityFilter()
        c.SetInputData(pd)
        c.SetExtractionModeToClosestPointRegion()
        c.SetClosestPoint(OX + 45.0, y, CZ)
        c.Update()
        out[f"cell{i}"] = c.GetOutput()
    return out


def make_actor(pd, col, edges=True):
    n = vtk.vtkPolyDataNormals()
    n.SetInputData(pd)
    n.SetFeatureAngle(40)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*col)
    p.SetAmbient(0.35)
    p.SetDiffuse(0.75)
    acts = [a]
    if edges:
        fe = vtk.vtkFeatureEdges()
        fe.SetInputData(pd)
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
        ea.GetProperty().SetLineWidth(1.0)
        acts.append(ea)
    return acts


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def offset(segs, step, t):
    """position of a part at (step, t in 0..1); None = hidden"""
    if step < segs[0][0]:
        return None
    pos = segs[0][1]
    for (s, a, b) in segs:
        if step > s:
            pos = b
        elif step == s:
            e = ease(t)
            pos = tuple(a[k] + (b[k] - a[k]) * e for k in range(3))
    return pos


def main():
    if os.path.isdir(FR):
        shutil.rmtree(FR)
    os.makedirs(FR)
    data = split_cells()
    for nm in MOTION:
        if nm not in data:
            data[nm] = read(nm)
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    acts = {nm: make_actor(data[nm], COL[nm], edges=nm not in ("ribbon",)) for nm in MOTION}
    for a in acts.values():
        for x in a:
            ren.AddActor(x)
    txt = vtk.vtkTextActor()
    txt.GetTextProperty().SetFontSize(22)
    txt.GetTextProperty().SetColor(0.1, 0.1, 0.15)
    txt.GetTextProperty().BoldOn()
    txt.SetDisplayPosition(30, H - 50)
    ren.AddActor2D(txt)
    title = vtk.vtkTextActor()
    title.SetInput("FCL monocular - assembly")
    title.GetTextProperty().SetFontSize(15)
    title.GetTextProperty().SetColor(0.4, 0.4, 0.45)
    title.SetDisplayPosition(30, 22)
    ren.AddActor2D(title)
    ren.RemoveAllLights()
    for d, i in (((1, 1, 1), 0.75), ((-1, 0.5, 0.3), 0.45), ((0, -1, -1), 0.45), ((0.3, -0.3, 1), 0.35)):
        l = vtk.vtkLight()
        l.SetLightTypeToCameraLight()
        l.SetPosition(*d)
        l.SetIntensity(i)
        ren.AddLight(l)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(W, H)
    win.AddRenderer(ren)
    cam = ren.GetActiveCamera()
    cam.ParallelProjectionOn()
    cam.SetParallelScale(95)
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    wr = vtk.vtkPNGWriter()
    wr.SetInputConnection(w2i.GetOutputPort())
    frame = 0
    prev_view = STEPS[0][1]
    for si, (caption, view) in enumerate(STEPS):
        txt.SetInput(caption)
        n = MOVE + HOLD + (24 if si == len(STEPS) - 1 else 0)
        for k in range(n):
            t = k / MOVE
            # camera: blend to this step's view during the first half of the move; slow orbit on the last step
            vb = ease(min(1.0, k / (MOVE * 0.6)))
            v = [prev_view[i] + (view[i] - prev_view[i]) * vb for i in range(3)]
            if si == len(STEPS) - 1:
                a = math.radians(k * 2.0)
                v = [v[0] * math.cos(a) - v[2] * math.sin(a), v[1], v[0] * math.sin(a) + v[2] * math.cos(a)]
            L = math.sqrt(sum(c * c for c in v))
            cam.SetFocalPoint(*CENTRE)
            cam.SetPosition(*(CENTRE[i] + 400 * v[i] / L for i in range(3)))
            cam.SetViewUp(0, 1, 0)
            cam.OrthogonalizeViewUp()
            ren.ResetCameraClippingRange()
            for nm, segs in MOTION.items():
                o = offset(segs, si, t)
                for x in acts[nm]:
                    x.SetVisibility(o is not None)
                    if o is not None:
                        x.SetPosition(*o)
            win.Render()
            w2i.Modified()
            wr.SetFileName(os.path.join(FR, f"f_{frame:04d}.png"))
            wr.Write()
            frame += 1
        prev_view = view
    print("frames", frame, flush=True)
    out = os.path.join(OUT, "FCL_assembly.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(FR, "f_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out], check=True)
    print("wrote", out, os.path.getsize(out) // 1024, "kB")


if __name__ == "__main__":
    main()
