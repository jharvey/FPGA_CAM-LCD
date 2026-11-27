"""Silkscreen pass (2026-11-27): mirror back texts, move reference labels off pads / other text,
and add labels that help build and debug the board (button and LED names, cell polarity, test point nets,
servo pin order, serial-number box, JLC order-number spot). Every new item is placed by a free-spot search;
anything that does not fit is reported and left out. Run from the board folder:  python3 silk_update.py [--save]"""
import math, sys
import pcbnew
B = pcbnew.LoadBoard("FCL.kicad_pcb")
mm, MM = pcbnew.ToMM, pcbnew.FromMM
OX, OY = 78.0, 55.5
SIDE = {"F": (pcbnew.F_SilkS, pcbnew.F_Cu, pcbnew.F_CrtYd), "B": (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_CrtYd)}
P = lambda x, y: pcbnew.VECTOR2I(MM(x + OX), MM(y + OY))
outline = pcbnew.SHAPE_POLY_SET()
B.GetBoardPolygonOutlines(outline, True)
log = []


def inside_board(bb, margin=0.6):
    m = MM(margin)
    for x in (bb.GetLeft() - m, bb.GetRight() + m):
        for y in (bb.GetTop() - m, bb.GetBottom() + m):
            if not outline.Contains(pcbnew.VECTOR2I(x, y)):
                return False
    return True


def obstacles(side, skip_fp=None, skip_item=None, courtyards=True):
    silk, cu, cy = SIDE[side]
    obs = []   # (shape, clearance mm)
    for f in B.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(cu) or p.GetDrillSize().x > 0:
                obs.append((p.GetEffectiveShape(cu), 0.15))
        for it in f.GraphicalItems():
            if it.GetLayer() == silk and it is not skip_item:
                if it.GetClass() in ("PCB_TEXT", "PCB_FIELD"):
                    if it.IsVisible():
                        obs.append((it.GetEffectiveShape(), 0.15))
                else:
                    obs.append((it.GetEffectiveShape(), 0.15))
        for t in (f.Reference(), f.Value()):
            if t.IsVisible() and t.GetLayer() == silk and not (skip_item is not None and t.m_Uuid.AsString() == skip_item.m_Uuid.AsString()):
                obs.append((t.GetEffectiveShape(), 0.15))
        if courtyards and f.GetReference() != skip_fp and not f.GetReference().startswith("BT") and (f.IsFlipped() == (side == "B")):
            c = f.GetCourtyard(cy)
            if c.OutlineCount():
                obs.append((c, 0.05))
    for d in B.GetDrawings():
        if d.GetLayer() == silk and d is not skip_item:
            obs.append((d.GetEffectiveShape(), 0.15))
    for t in B.GetTracks():
        if t.GetClass() == "PCB_VIA" and ((side == "B" and t.GetBackTentingMode() == pcbnew.TENTING_MODE_NOT_TENTED)
                                          or (side == "F" and t.GetFrontTentingMode() == pcbnew.TENTING_MODE_NOT_TENTED)):
            obs.append((t.GetEffectiveShape(cu), 0.15))
    return obs


def fits(bb, obs):
    if not inside_board(bb):
        return False
    rect = pcbnew.SHAPE_RECT(bb)
    for shp, cl in obs:
        if shp.Collide(rect, MM(cl)):
            return False
    return True


def spiral(x, y, rmax, step=0.2):
    yield x, y
    r = step
    while r <= rmax + 1e-9:
        n = max(8, int(2 * math.pi * r / step))
        for k in range(n):
            a = 2 * math.pi * k / n
            yield x + r * math.cos(a), y + r * math.sin(a)
        r += step


def new_text(txt, side, h=0.8, th=0.15, angle=0):
    t = pcbnew.PCB_TEXT(B)
    t.SetText(txt); t.SetLayer(SIDE[side][0])
    t.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h))); t.SetTextThickness(MM(th))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetMirrored(side == "B")
    t.SetTextAngleDegrees(angle)
    return t


def place_text(txt, side, x, y, rmax=3.0, h=0.8, th=0.15, angle=0, courtyards=True):
    obs = obstacles(side, courtyards=courtyards)
    t = new_text(txt, side, h, th, angle)
    for cx, cy in spiral(x, y, rmax):
        t.SetPosition(P(cx, cy))
        bb = t.GetBoundingBox()
        if fits(bb, obs):
            B.Add(t)
            log.append(("label", side, txt, round(cx, 2), round(cy, 2)))
            return t
    log.append(("label", side, txt, "NO ROOM near", (x, y)))
    return None


# ---- 1. mirror back-side texts that are not mirrored
for f in B.GetFootprints():
    for t in [f.Reference(), f.Value()] + [g for g in f.GraphicalItems() if g.GetClass() in ("PCB_TEXT", "PCB_FIELD")]:
        if t.GetLayer() == pcbnew.B_SilkS and t.IsVisible() and not t.IsMirrored():
            t.SetMirrored(True); log.append(("mirrored", f.GetReference(), t.GetText()))
for d in B.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.B_SilkS and not d.IsMirrored():
        d.SetMirrored(True); log.append(("mirrored", "board", d.GetText()))

# ---- 2. move reference labels that sit on pads, on other text, or past the edge
MOVE = "R18 R19 R65 R82 C74 C13 C91 D16 D10 TP13 U12 C56 R32 R30 C30 RP3 R38 R27 B0 R20".split()
for ref in MOVE:
    f = B.FindFootprintByReference(ref)
    if not f or not f.Reference().IsVisible():
        continue
    side = "B" if f.IsFlipped() else "F"
    t = f.Reference()
    obs = obstacles(side, skip_fp=ref, skip_item=t, courtyards=False)
    start = t.GetPosition()
    sx, sy = mm(start.x) - OX, mm(start.y) - OY
    bb0 = t.GetBoundingBox()
    if fits(bb0, obs):
        log.append(("ref ok", ref)); continue
    fx, fy = mm(f.GetPosition().x) - OX, mm(f.GetPosition().y) - OY
    done = False
    for cx, cy in spiral(fx, fy, 3.5, 0.15):
        t.SetPosition(P(cx, cy))
        if fits(t.GetBoundingBox(), obs):
            log.append(("ref moved", ref, (round(sx, 2), round(sy, 2)), "->", (round(cx, 2), round(cy, 2)))); done = True
            break
    if not done:
        # smaller text is not allowed (0.8 mm minimum): hide it rather than print it over pads
        t.SetPosition(start)
        if mm(t.GetTextSize().y) >= 0.8:
            t.SetVisible(False); log.append(("ref hidden (no room)", ref))

# billboard: serial-number box, JLC order-number spot, battery warning, title on the front
sn = None
obsB = obstacles("B")
for cx, cy in spiral(62.0, 75.6, 30.0, 0.3):
    r = pcbnew.BOX2I(P(cx - 5.0, cy - 1.6), pcbnew.VECTOR2L(MM(10.0), MM(3.2)))
    lab = new_text("S/N", "B"); lab.SetPosition(P(cx + 6.6, cy))
    if fits(r, obsB) and fits(lab.GetBoundingBox(), obsB):
        box = pcbnew.PCB_SHAPE(B); box.SetShape(pcbnew.SHAPE_T_RECTANGLE); box.SetLayer(pcbnew.B_SilkS)
        box.SetStart(P(cx - 5.0, cy - 1.6)); box.SetEnd(P(cx + 5.0, cy + 1.6)); box.SetFilled(True); box.SetWidth(MM(0.15))
        B.Add(box); B.Add(lab); sn = (round(cx, 2), round(cy, 2)); break
log.append(("serial box", sn or "NO ROOM"))
place_text("JLCJLCJLCJLC", "B", 62.0, 72.0, 30.0)
place_text("3x 18650 Li-ion: check + / - before fitting", "B", 42.5, 40.0, 35.0)
place_text("FCL V0.1  github.com/jharvey/FPGA_CAM-LCD", "F", 42.5, 76.8, 10.0, h=1.0, th=0.18)


# ---- 3. labels.  A group is placed whole or not at all (no half-labelled rows).
def group(items, name):
    placed = []
    for args, kw in items:
        t = place_text(*args, **kw)
        if t is None:
            for q in placed:
                B.Remove(q)
            log.append(("group dropped", name))
            return False
        placed.append(t)
    return True


def g(*args, **kw):
    return (args, kw)


group([g("POWER", "B", 9.0, 8.3, 3.0), g("USER 1", "B", 16.0, 8.3, 3.0), g("USER 2", "B", 26.5, 8.3, 3.0)], "buttons") or     place_text("B0 POWER  B1 USER 1  B2 USER 2", "B", 18.0, 10.0, 8.0)
cells = []
for n, (xp, yp, xm, ym) in enumerate(((79.5, 15.5, 5.5, 15.5), (5.5, 36.0, 79.5, 36.0), (79.5, 56.5, 5.5, 56.5)), 1):
    ip = -1 if xp > 40 else 1
    im = -1 if xm > 40 else 1
    _unused = [g("+", "B", xp + ip * 7.0, yp, 8.0, h=2.0, th=0.3, courtyards=False),
              g("-", "B", xm + im * 7.0, ym, 8.0, h=2.0, th=0.3, courtyards=False),
              g("CELL%d" % n, "B", 42.5, yp, 20.0, h=1.2, th=0.2)]
group([g("+  CELL1  -", "B", 42.5, 15.5, 25.0, h=1.5, th=0.25),
       g("-  CELL2  +", "B", 42.5, 36.0, 25.0, h=1.5, th=0.25),
       g("+  CELL3  -", "B", 42.5, 56.5, 25.0, h=1.5, th=0.25)], "cell polarity")   # mirrored: reads + on the + end, seen from the back
for tp, txt in (("TP1", "GND"), ("TP2", "GND"), ("TP3", "3V3"), ("TP4", "1V1"), ("TP5", "2V5"), ("TP7", "5V"),
                ("TP8", "IMU SCL"), ("TP9", "IMU SDA"), ("TP10", "RTC SCL"), ("TP11", "RTC SDA"),
                ("TP6", "VSYS")):
    f = B.FindFootprintByReference(tp)
    side = "B" if f.IsFlipped() else "F"
    x, y = mm(f.GetPosition().x) - OX, mm(f.GetPosition().y) - OY
    place_text(txt, side, x, y + 1.7, 4.0)
# front
place_text("BOOT", "F", 80.1, 26.0, 2.5)
place_text("RST", "F", 50.0, 12.0, 2.5)
place_text("JTAG", "F", 44.6, 16.4, 2.5)
place_text("5V ONLY", "F", 77.0, 64.8, 6.0)
place_text("SPK", "F", 3.6, 23.4, 3.5)
place_text("CAMERA", "F", 34.8, 57.0, 3.0)
place_text("SERVO S + -", "F", 15.0, 76.0, 6.0)
for l in log:
    print(*l)
if "--save" in sys.argv:
    B.Save("FCL.kicad_pcb"); print("saved")
