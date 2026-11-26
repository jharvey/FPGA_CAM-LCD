"""Replace J7 (flat FH12-40S-0.5SH) with the vertical FH12-40S-0.5SV and re-attach its tracks.

Run with KiCad's Python:
  "C:/Program Files/KiCad/10.0/bin/python.exe" scripts/swap_j7_vertical.py

Why: the NHD TFT ribbon is 27.0 mm long and the TFT sits 20.5 mm above the board on the
cells, so a flat connector leaves a 0.84 mm fold radius. A vertical connector takes the
ribbon straight down (see case/renders/fpc_options.png).

Placement (board mm, origin = top-left corner): centre (34.88, 67.80), back side.
  odd pads  (1,3,..39): y 69.30  - the side the ribbon contacts face (toward the bottom edge)
  even pads (2,4,..40): y 66.30  - lock-lever side (toward cell 3)
Pad n stays at the x of the old pad n, so every track is moved straight up or down.
"""
import os
import pcbnew

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PCB = os.path.join(REPO, "FCL.kicad_pcb")
LIB = os.path.join(REPO, "footprints", "fcl_local.pretty")
NAME = "Hirose_FH12-40S-0.5SV_1x40-1MP_P0.50mm_Vertical"
OX, OY = 78.0, 55.5
X0, Y0 = 34.88, 67.80
ROW = 1.5

mm = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
P = lambda pt: (round(pcbnew.ToMM(pt.x) - OX, 3), round(pcbnew.ToMM(pt.y) - OY, 3))

b = pcbnew.LoadBoard(PCB)
old = b.FindFootprintByReference("J7")
assert "0.5SH" in old.GetFPIDAsString(), "J7 is not the flat FH12 any more - already swapped?"

# ---- remember the old pads -------------------------------------------------------
oldpads = {}
for p in old.Pads():
    if p.GetNumber() != "MP":
        oldpads[int(p.GetNumber())] = (p.GetNetCode(), p.GetNetname(), p.GetBoundingBox(), P(p.GetPosition()))
gnd = b.FindNet("GND")
fields = {f.GetName(): f.GetText() for f in old.GetFields()}

# ---- move the track ends that sat on the old pads ----------------------------------
moved = 0
for n, (code, net, bb, (px, py)) in oldpads.items():
    target = V(px, Y0 + ROW if n % 2 else Y0 - ROW)
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayerName() != "B.Cu" or t.GetNetCode() != code:
            continue
        s_in, e_in = bb.Contains(t.GetStart()), bb.Contains(t.GetEnd())
        if s_in and e_in:
            t.SetStart(target)
            moved += 1
        elif s_in:
            t.SetStart(target)
            moved += 1
        elif e_in:
            t.SetEnd(target)
            moved += 1
print("track ends moved:", moved)

# ---- swap the footprint ------------------------------------------------------------
new = pcbnew.FootprintLoad(LIB, NAME)
new.SetFPID(pcbnew.LIB_ID("fcl_local", NAME))
b.Add(new)
new.SetPosition(V(X0, Y0))
try:
    new.Flip(V(X0, Y0), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
except (AttributeError, TypeError):
    new.Flip(V(X0, Y0), True)
new.SetOrientationDegrees(0)
new.SetReference("J7")
new.SetValue(fields.get("Value", old.GetValue()))
new.SetPath(old.GetPath())
new.SetSheetname(old.GetSheetname())
new.SetSheetfile(old.GetSheetfile())
new.SetAttributes(old.GetAttributes())
for k, v in fields.items():
    if k in ("Reference", "Value", "Footprint"):
        continue
    if k == "LCSC":
        v = "C202115"
    if k in ("FT Rotation Offset", "FT Position Offset"):
        v = "0" if k.startswith("FT Rot") else ""
    try:
        new.SetField(k, v)
    except Exception as e:  # field API differs between versions
        print("field not copied:", k, e)
for p in new.Pads():
    if p.GetNumber() == "MP":
        p.SetNet(gnd)
    else:
        p.SetNetCode(oldpads[int(p.GetNumber())][0])
b.Remove(old)

chk = {p.GetNumber(): P(p.GetPosition()) for p in new.Pads() if p.GetNumber() in ("1", "2", "40")}
print("new pads:", chk)
assert abs(chk["1"][0] - 44.63) < 0.01 and abs(chk["1"][1] - (Y0 + ROW)) < 0.01, "pad 1 is not where the ribbon's pin 1 lands"

# ---- ground the four mounting pads -------------------------------------------------
def track(a, c, w, net):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*a)); t.SetEnd(V(*c)); t.SetWidth(mm(w)); t.SetLayer(pcbnew.B_Cu); t.SetNet(net)
    b.Add(t)

for x in (X0 - 10.75, X0 + 10.75):
    track((x, Y0 - 1.35), (x, Y0 + 1.35), 0.3, gnd)
track((45.344, 70.084), (X0 + 10.75, Y0 + 1.35), 0.3, gnd)      # old right MP stub
track((24.43, 70.48), (X0 - 10.75, Y0 + 1.35), 0.3, gnd)        # old left MP stub

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print("saved", PCB)
