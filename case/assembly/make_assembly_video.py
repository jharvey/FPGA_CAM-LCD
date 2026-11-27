#!/usr/bin/env python3
"""Assembly animation of the FCL monocular, shown the way it is put together on a desk.

    python case/assembly/make_assembly_video.py                      # removable cells -> case/renders/FCL_assembly.mp4
    FCL_BATTERY=fixed python case/assembly/make_assembly_video.py    # fixed cells     -> case/renders/FCL_assembly_fixed.mp4

Reads case/build/case_parts[_fixed]/*.stl (written by build_case.py).  Three desk scenes:
  lid    rear shell lying eye-face down like a cup, parts go in from above
  pcb    PCB lying camera-side down, the battery / display stack is built on it
  front  front shell lying face down, the camera goes in
  feet   (removable cells) PCB camera side up, standing on its three blocks, block screws go in from above
Between them the part in hand is turned over (the view turns about the board's up axis).
"""
import math
import re
import os
import shutil
import subprocess
import vtk

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXED = os.environ.get("FCL_BATTERY", "") == "fixed"
PARTS = os.path.join(REPO, "case", "build", "case_parts_fixed" if FIXED else "case_parts")
OUT = os.path.join(REPO, "case", "renders")
FR = os.path.join(REPO, "case", "build", "video_frames_fixed" if FIXED else "video_frames")
OUTFILE = "FCL_assembly_fixed.mp4" if FIXED else "FCL_assembly.mp4"
W, H, FPS = 1280, 720, 24
MOVE, HOLD = 44, 22                          # frames per step: motion, then pause
SCALE = 100.0                                # half the picture height, mm

OX, OY = 78.0, 55.5
CZ = -11.8
ROW_Y = {1: -(OY + 15.5), 2: -(OY + 36.0), 3: -(OY + 56.5)}
CX, CY = OX + 42.5, -(OY + 39.5)
UP = (0, 0, 95)                              # held above the lid before it goes in
Z0 = (0, 0, 0)

# scene: view (from the centre toward the camera), up, desk surface z, focal z
SCENES = {"lid": ((0.35, -0.8, 0.75), (0, 0, 1), -26.5, 2.0),
          "pcb": ((-0.35, -0.8, -0.75), (0, 0, -1), 2.0, -10.0),
          "front": ((-0.35, -0.8, -0.75), (0, 0, -1), 44.6, 22.0),
          "feet": ((0.35, -0.8, 0.75), (0, 0, 1), -25.85, -8.0),
          "lidup": ((-0.35, -0.8, -0.75), (0, 0, -1), 1.6, -14.0)}

COL = {"PCB": (0.20, 0.55, 0.28), "TFT": (0.30, 0.30, 0.36), "camera": (0.25, 0.35, 0.75), "ribbon": (0.95, 0.62, 0.20),
       "cell1": (0.90, 0.50, 0.78), "cell2": (0.90, 0.50, 0.78), "cell3": (0.90, 0.50, 0.78),
       "springs": (0.82, 0.82, 0.86), "plus_contacts": (0.82, 0.82, 0.86),
       "FCL_battery_block_right": (0.72, 0.74, 0.78), "left_blocks": (0.72, 0.74, 0.78),
       "caps_L": (0.33, 0.36, 0.28), "caps_R": (0.33, 0.36, 0.28), "slugs_L": (0.88, 0.72, 0.38), "slugs_R": (0.88, 0.72, 0.38),
       "FCL_cell_cradle": (0.98, 0.80, 0.30), "FCL_case_rear": (0.40, 0.60, 0.95), "FCL_case_front": (0.45, 0.82, 0.62),
       "FCL_button_actuators": (0.90, 0.28, 0.22), "FCL_button_caps": (0.20, 0.20, 0.22), "FCL_cell_cradle_top": (0.98, 0.70, 0.20),
       "hw_case_screws": (0.15, 0.15, 0.17), "hw_cam_screws": (0.15, 0.15, 0.17), "hw_block_screws": (0.15, 0.15, 0.17), "hw_block_washers": (0.75, 0.75, 0.78),
       "hw_case_inserts": (0.80, 0.62, 0.25), "hw_cam_inserts": (0.80, 0.62, 0.25)}

LID = ["FCL_case_rear", "hw_case_inserts", "FCL_button_actuators", "FCL_button_caps"]
FRONT = ["FCL_case_front", "hw_cam_inserts", "camera", "hw_cam_screws"]
SCREWS = ["hw_case_screws"]

if FIXED:
    TITLE = "FCL monocular - assembly, fixed cells (spring contacts)"
    STACK = ["PCB", "springs", "plus_contacts", "FCL_cell_cradle", "cell1", "cell2", "cell3", "FCL_cell_cradle_top", "ribbon", "TFT"]
    LATE = []
    # caption, scene, mode ("" / "cut" / "flip"), groups shown
    STEPS = [
        ("1  Lid (rear shell) face down on the desk, like a cup: heat-set inserts in the four corners", "lid", "cut", (LID,)),
        ("2  Snap the two button plungers in from the inside", "lid", "", (LID,)),
        ("3  PCB face down on the desk. The springs and + plates are already soldered on", "pcb", "cut", (STACK,)),
        ("4  Battery spacer down over the contacts: it backs up every plate", "pcb", "", (STACK,)),
        ("5  Cells in: + end against its plate, press down against the spring", "pcb", "", (STACK,)),
        ("6  LCD-side battery support on top", "pcb", "", (STACK,)),
        ("7  LCD and its ribbon (one part): lay the display on the support, ribbon end into J7", "pcb", "", (STACK,)),
        ("8  Pick the stack up and turn it over", "lid", "flip", (STACK,)),
        ("9  Lower the stack into the lid, display first", "lid", "", (LID, STACK)),
        ("10  Front shell face down: camera in, 4 x M2.5 screws into the inserts in the posts", "front", "cut", (FRONT,)),
        ("11  Turn the front shell over", "lid", "flip", (FRONT,)),
        ("12  Front shell onto the lid: the camera header plugs into J1", "lid", "", (LID, STACK, FRONT)),
        ("13  4 x M2.5 x 10 case screws in the corners", "lid", "", (LID, STACK, FRONT, SCREWS)),
        ("Done.  To change a cell you need a screwdriver: 4 case screws out, lift the stack out of the lid", "lid", "", (LID, STACK, FRONT, SCREWS)),
    ]
    S_FLIP, S_IN, F_FLIP, F_ON = 7, 8, 10, 11

    def stack(*first):
        return list(first) + [(S_FLIP, Z0, UP), (S_IN, UP, Z0)]
    MOTION = {
        "FCL_case_rear": [(0, Z0, Z0)],
        "hw_case_inserts": [(0, (0, 0, 45), Z0)],
        "FCL_button_actuators": [(1, (0, 0, 45), Z0)],
        "PCB": stack((2, Z0, Z0)),
        "springs": stack((2, Z0, Z0)),
        "plus_contacts": stack((2, Z0, Z0)),
        "FCL_cell_cradle": stack((3, (0, 0, -60), Z0)),
        "cell1": stack((4, (0, 0, -55), Z0, 0.0, 0.5)),
        "cell2": stack((4, (0, 0, -55), Z0, 0.25, 0.75)),
        "cell3": stack((4, (0, 0, -55), Z0, 0.5, 1.0)),
        "FCL_cell_cradle_top": stack((5, (0, 0, -55), Z0)),
        "ribbon": stack((6, (0, 0, -60), Z0)),
        "TFT": stack((6, (0, 0, -60), Z0)),
    }
else:
    TITLE = "FCL monocular - assembly, removable cells (blocks + bayonet caps)"
    STACK = ["PCB", "hw_block_washers", "left_blocks", "FCL_battery_block_right", "hw_block_screws", "FCL_cell_cradle",
             "FCL_cell_cradle_top", "ribbon", "TFT"]
    LATE = ["cell1", "cell2", "cell3", "slugs_L", "slugs_R", "caps_L", "caps_R"]
    STEPS = [
        ("1  Lid (rear shell) face down on the desk, like a cup: heat-set inserts in the four corners", "lid", "cut", (LID,)),
        ("2  Snap the two button plungers in from the inside", "lid", "", (LID,)),
        ("3  PCB camera side down on the desk: a 0.5 mm washer on each block screw hole, then the three blocks", "pcb", "cut", (STACK,)),
        ("4  Hold the blocks and turn the board over: it stands on its three blocks", "feet", "turn", (STACK,)),
        ("5  Two M1.6 x 5 screws per block, from the camera side through the PCB into the block", "feet", "", (STACK,)),
        ("6  Turn it back over, camera side down", "pcb", "turn", (STACK,)),
        ("7  Battery spacer onto the back of the PCB, between the blocks", "pcb", "", (STACK,)),
        ("8  LCD-side battery support on top", "pcb", "", (STACK,)),
        ("9  LCD and its ribbon (one part): lay the display on the support, ribbon end into J7", "pcb", "", (STACK,)),
        ("10  Pick the stack up and turn it over", "lid", "flip", (STACK,)),
        ("11  Lower the stack into the lid, display first", "lid", "", (LID, STACK)),
        ("12  Front shell face down: camera in, 4 x M2.5 screws into the inserts in the posts", "front", "cut", (FRONT,)),
        ("13  Turn the front shell over", "lid", "flip", (FRONT,)),
        ("14  Front shell onto the lid: the camera header plugs into J1", "lid", "", (LID, STACK, FRONT)),
        ("15  4 x M2.5 x 10 case screws in the corners", "lid", "", (LID, STACK, FRONT, SCREWS)),
        ("16  Cells slide in through the blocks: cells 1 and 3 from the left, cell 2 from the right", "lid", "", (LID, STACK, FRONT, SCREWS, LATE)),
        ("17  Brass slug + spring, then the bayonet cap: push on and turn 1/4", "lid", "", (LID, STACK, FRONT, SCREWS, LATE)),
        ("Done.  Cells change from outside, no tools: 1/4 turn on a cap", "lid", "", (LID, STACK, FRONT, SCREWS, LATE)),
    ]
    S_FLIP, S_IN, F_FLIP, F_ON = 9, 10, 12, 13

    def stack(*first):
        return list(first) + [(S_FLIP, Z0, UP), (S_IN, UP, Z0)]
    MOTION = {
        "FCL_case_rear": [(0, Z0, Z0)],
        "hw_case_inserts": [(0, (0, 0, 45), Z0)],
        "FCL_button_actuators": [(1, (0, 0, 45), Z0)],
        "PCB": stack((2, Z0, Z0)),
        "hw_block_washers": stack((2, (0, 0, -30), Z0, 0.0, 0.35)),
        "left_blocks": stack((2, (0, 0, -65), Z0, 0.3, 1.0)),
        "FCL_battery_block_right": stack((2, (0, 0, -65), Z0, 0.3, 1.0)),
        "hw_block_screws": stack((4, (0, 0, 40), Z0)),
        "FCL_cell_cradle": stack((6, (0, 0, -70), Z0)),
        "FCL_cell_cradle_top": stack((7, (0, 0, -55), Z0)),
        "ribbon": stack((8, (0, 0, -60), Z0)),
        "TFT": stack((8, (0, 0, -60), Z0)),
        "cell1": [(15, (-95, 0, 0), Z0)],
        "cell3": [(15, (-95, 0, 0), Z0)],
        "cell2": [(15, (95, 0, 0), Z0)],
        "slugs_L": [(16, (-55, 0, 0), Z0, 0.0, 0.6)],
        "slugs_R": [(16, (55, 0, 0), Z0, 0.0, 0.6)],
        "caps_L": [(16, (-80, 0, 0), Z0, 0.3, 1.0)],
        "caps_R": [(16, (80, 0, 0), Z0, 0.3, 1.0)],
    }

STEPS[2:2] = [("Turn the lid face up: it rests on its rim", "lidup", "turn", (LID,)),
              ("Press the two button caps on from outside: their tongue locks the plunger", "lidup", "", (LID,)),
              ("Turn the lid back over", "lid", "turn", (LID,))]


def _shift(seg):
    return (seg[0] + 3 if seg[0] >= 2 else seg[0],) + tuple(seg[1:])


MOTION = {k: [_shift(g) for g in v] for k, v in MOTION.items()}
MOTION["FCL_button_caps"] = [(3, (0, 0, -30), Z0)]
S_FLIP, S_IN, F_FLIP, F_ON = S_FLIP + 3, S_IN + 3, F_FLIP + 3, F_ON + 3
STEPS = [((f"{i + 1}  " + re.sub(r"^\d+\s+", "", c)) if not c.startswith("Done") else c,) + tuple(r) for i, (c, *r) in enumerate(STEPS)]

ZOOM_NEAR, ZOOM_FAR = 76.0, 100.0            # half picture height: close for desk work, wide while a part is held above
HOVER_FOCAL = 42.0                           # look higher while the part is held above the lid
# exploded view (dx, dz) per part for the opening shot
EXPLODE = {"FCL_case_front": (0, 62), "hw_cam_inserts": (0, 62), "camera": (0, 28), "hw_cam_screws": (0, 14),
           "hw_case_screws": (0, 92), "hw_block_screws": (0, 12), "hw_block_washers": (0, -6), "left_blocks": (-16, 0), "FCL_battery_block_right": (16, 0),
           "slugs_L": (-34, 0), "slugs_R": (34, 0), "caps_L": (-52, 0), "caps_R": (52, 0),
           "FCL_cell_cradle": (0, -30), "cell1": (0, -30), "cell2": (0, -30), "cell3": (0, -30),
           "FCL_cell_cradle_top": (0, -48), "ribbon": (0, -74), "TFT": (0, -74), "FCL_button_actuators": (0, -98), "FCL_button_caps": (0, -124),
           "hw_case_inserts": (0, -116), "FCL_case_rear": (0, -116)}
F_SCENE = F_FLIP - 1
MOTION.update({
    "FCL_case_front": [(F_SCENE, Z0, Z0), (F_FLIP, Z0, UP), (F_ON, UP, Z0)],
    "hw_cam_inserts": [(F_SCENE, (0, 0, -40), Z0, 0.0, 0.35), (F_FLIP, Z0, UP), (F_ON, UP, Z0)],
    "camera": [(F_SCENE, (0, 0, -60), Z0, 0.2, 0.75), (F_FLIP, Z0, UP), (F_ON, UP, Z0)],
    "hw_cam_screws": [(F_SCENE, (0, 0, -85), Z0, 0.55, 1.0), (F_FLIP, Z0, UP), (F_ON, UP, Z0)],
    "hw_case_screws": [(F_ON + 1, (0, 0, 45), Z0)],
})


def read(name):
    r = vtk.vtkSTLReader()
    r.SetFileName(os.path.join(PARTS, name + ".stl"))
    r.Update()
    return r.GetOutput()


def split_cells():
    pd = read("cells")
    c = vtk.vtkPolyDataConnectivityFilter()
    c.SetInputData(pd)
    c.SetExtractionModeToAllRegions()
    c.Update()
    n = c.GetNumberOfExtractedRegions()
    out = {}
    for rid in range(n):
        c2 = vtk.vtkPolyDataConnectivityFilter()
        c2.SetInputData(pd)
        c2.SetExtractionModeToSpecifiedRegions()
        c2.AddSpecifiedRegion(rid)
        cl = vtk.vtkCleanPolyData()
        cl.SetInputConnection(c2.GetOutputPort())
        cl.Update()
        part = vtk.vtkPolyData()
        part.DeepCopy(cl.GetOutput())
        b = part.GetBounds()
        yc = (b[2] + b[3]) / 2
        i = min(ROW_Y, key=lambda k: abs(ROW_Y[k] - yc))
        out[f"cell{i}"] = part
    assert sorted(out) == ["cell1", "cell2", "cell3"], sorted(out)
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


def make_desk():
    c = vtk.vtkCubeSource()
    c.SetXLength(1400)
    c.SetYLength(1400)
    c.SetZLength(4)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(c.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(0.86, 0.78, 0.64)
    a.GetProperty().SetAmbient(0.55)
    a.GetProperty().SetDiffuse(0.5)
    return a


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def offset(segs, step, t):
    """position of a part at (step, t in 0..1); None = not there yet"""
    if step < segs[0][0]:
        return None
    pos = segs[0][1]
    for seg in segs:
        s, a, b = seg[:3]
        t0, t1 = (seg[3], seg[4]) if len(seg) > 3 else (0.0, 1.0)
        if step > s:
            pos = b
        elif step == s:
            e = ease((t - t0) / (t1 - t0))
            pos = tuple(a[k] + (b[k] - a[k]) * e for k in range(3))
    return pos


def rot_y(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)


def rot_z(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


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
    acts = {nm: make_actor(data[nm], COL[nm], edges=nm not in ("ribbon", "springs")) for nm in MOTION}
    for a in acts.values():
        for x in a:
            ren.AddActor(x)
    desk = make_desk()
    ren.AddActor(desk)
    txt = vtk.vtkTextActor()
    txt.GetTextProperty().SetFontSize(22)
    txt.GetTextProperty().SetColor(0.1, 0.1, 0.15)
    txt.GetTextProperty().BoldOn()
    txt.GetTextProperty().SetBackgroundColor(1, 1, 1)
    txt.GetTextProperty().SetBackgroundOpacity(0.85)
    txt.SetDisplayPosition(30, H - 50)
    ren.AddActor2D(txt)
    title = vtk.vtkTextActor()
    title.SetInput(TITLE)
    title.GetTextProperty().SetFontSize(15)
    title.GetTextProperty().SetColor(0.25, 0.25, 0.3)
    title.GetTextProperty().SetBackgroundColor(1, 1, 1)
    title.GetTextProperty().SetBackgroundOpacity(0.85)
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
    cam.SetParallelScale(SCALE)
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    wr = vtk.vtkPNGWriter()
    wr.SetInputConnection(w2i.GetOutputPort())
    frame = 0

    def snap():
        nonlocal frame
        ren.ResetCameraClippingRange()
        win.Render()
        w2i.Modified()
        wr.SetFileName(os.path.join(FR, f"f_{frame:04d}.png"))
        wr.Write()
        frame += 1

    # ---- opening: exploded view of every part, turning slowly, then the parts close up
    desk.SetVisibility(0)
    txt.SetInput("Exploded view: every part, in the order it stacks")
    n_turn, n_close = 130, 40
    for k in range(n_turn + n_close):
        e = 1.0 - ease((k - n_turn) / n_close) if k >= n_turn else 1.0
        for nm in MOTION:
            dx, dz = EXPLODE.get(nm, (0, 0))
            for x in acts[nm]:
                x.SetVisibility(1)
                x.SetPosition(dx * e, 0, dz * e)
        v = rot_y((-0.75, 0.5, -0.9), math.radians(-40 + k * 0.6))
        L = math.sqrt(sum(c * c for c in v))
        foc = (CX, CY, -22.0 * e)
        cam.SetFocalPoint(*foc)
        cam.SetPosition(*(foc[i] + 600 * v[i] / L for i in range(3)))
        cam.SetViewUp(0, 1, 0)
        cam.OrthogonalizeViewUp()
        cam.SetParallelScale(150 - 60 * (1 - e))
        snap()

    pv, pu, _, pf = SCENES[STEPS[0][1]]
    ps = ZOOM_NEAR
    for si, (caption, scene, mode, show) in enumerate(STEPS):
        txt.SetInput(caption)
        tv, tu, desk_z, tf = SCENES[scene]
        shown = {n for g in show for n in g}
        last = si == len(STEPS) - 1
        hover_in = si > 0 and STEPS[si - 1][2] == "flip"     # the step that lowers the part held above the lid
        if mode == "turn":
            ts = ZOOM_NEAR
        elif mode == "flip":
            tf, ts = HOVER_FOCAL, ZOOM_FAR
        else:
            ts = ZOOM_NEAR
        n = MOVE + HOLD + (72 if last else 0)
        for k in range(n):
            t = k / MOVE
            if mode == "cut":
                v, u, f, sc = tv, tu, tf, ts
            elif mode in ("flip", "turn"):           # the part in hand turns over: the view turns about the board's up axis
                ang = math.pi * ease(t)
                v, u = rot_y(pv, ang), rot_y(pu, ang)
                f = pf + (tf - pf) * ease(t)
                sc = ps + (ts - ps) * ease(t)
            else:
                e = ease(t) if hover_in else ease(min(1.0, k / (MOVE * 0.6)))
                v = tuple(pv[i] + (tv[i] - pv[i]) * e for i in range(3))
                u, f = tu, pf + (tf - pf) * e
                sc = ps + (ts - ps) * e
            if last:                                  # slow turn round the finished unit on the desk
                v = rot_z(v, math.radians(k * 1.6))
            L = math.sqrt(sum(c * c for c in v))
            foc = (CX, CY, f)
            cam.SetFocalPoint(*foc)
            cam.SetPosition(*(foc[i] + 600 * v[i] / L for i in range(3)))
            cam.SetViewUp(*u)
            cam.OrthogonalizeViewUp()
            cam.SetParallelScale(sc)
            desk.SetVisibility(not (mode == "flip" or (mode == "turn" and t < 1.0)))   # turned on the desk: desk back once it lies
            desk.SetPosition(CX, CY, desk_z - 2.0 * tu[2])
            for nm, segs in MOTION.items():
                o = offset(segs, si, t) if nm in shown else None
                for x in acts[nm]:
                    x.SetVisibility(o is not None)
                    if o is not None:
                        x.SetPosition(*o)
            snap()
        pv, pu, pf, ps = tv, tu, tf, ts
    print("frames", frame, flush=True)
    out = os.path.join(OUT, OUTFILE)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(FR, "f_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out], check=True)
    print("wrote", out, os.path.getsize(out) // 1024, "kB")


if __name__ == "__main__":
    main()
