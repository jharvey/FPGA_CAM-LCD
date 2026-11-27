"""Probe points: spare U1 balls get a dog-bone via with the back side left uncovered (bare copper),
spare U9 pads get a stub + 0.6 mm via (back uncovered, labelled), and one via of 5 existing nets is uncovered.
Run from the board folder. Writes FCL.kicad_pcb and prints what it did."""
import math, sys
import pcbnew
B = pcbnew.LoadBoard("FCL.kicad_pcb")
mm, MM = pcbnew.ToMM, pcbnew.FromMM
OX, OY = 78.0, 55.5
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
P = lambda x, y: pcbnew.VECTOR2I(MM(x + OX), MM(y + OY))

tracks = list(B.GetTracks())
pads = [p for f in B.GetFootprints() for p in f.Pads()]
back_cy = []
for f in B.GetFootprints():
    if f.IsFlipped():
        cy = f.GetCourtyard(pcbnew.B_CrtYd)
        if cy.OutlineCount():
            back_cy.append((f.GetReference(), cy))
new_items = []


def near(item, pos, r):
    bb = item.GetBoundingBox()
    return bb.GetLeft() - r < pos.x < bb.GetRight() + r and bb.GetTop() - r < pos.y < bb.GetBottom() + r


def clear(shape_by_layer, pos, net, cl, extra=()):
    r = MM(3)
    for it in list(tracks) + pads + list(extra):
        if it.GetNetCode() == net and net != 0:
            continue
        if not near(it, pos, r):
            continue
        for L, shp in shape_by_layer.items():
            if not it.IsOnLayer(L):
                continue
            if it.GetEffectiveShape(L).Collide(shp, MM(cl)):
                return False, it
    return True, None


def in_back_courtyard(pos, margin):
    for ref, cy in back_cy:
        if cy.Collide(pos, MM(margin)):
            return ref
    return None


def make_via(pos, net, d, drill):
    v = pcbnew.PCB_VIA(B)
    v.SetPosition(pos); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetWidth(pcbnew.F_Cu, MM(d)); v.SetDrill(MM(drill)); v.SetNetCode(net)
    v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    v.SetBackTentingMode(pcbnew.TENTING_MODE_NOT_TENTED)
    return v


def make_track(a, c, net, w):
    t = pcbnew.PCB_TRACK(B)
    t.SetStart(a); t.SetEnd(c); t.SetWidth(MM(w)); t.SetLayer(pcbnew.F_Cu); t.SetNetCode(net)
    return t


def try_place(padpos, net, vpos, d, drill, w, cl, hole_cl):
    v = make_via(vpos, net, d, drill)
    t = make_track(padpos, vpos, net, w)
    shapes = {L: v.GetEffectiveShape(L) for L in CU}
    ok, hit = clear(shapes, vpos, net, cl, new_items)
    if not ok:
        return None, "via vs %s" % (hit.GetParentFootprint().GetReference() if hit.GetParentFootprint() else hit.GetClass())
    # hole clearance / hole-to-hole against all vias and TH pads
    for it in list(tracks) + new_items + pads:
        if it.GetClass() in ("PCB_VIA",) or (it.GetClass() == "PAD" and it.GetDrillSize().x > 0):
            if near(it, vpos, MM(2)):
                dd = math.hypot(it.GetPosition().x - vpos.x, it.GetPosition().y - vpos.y)
                other = it.GetDrill() if it.GetClass() == "PCB_VIA" else it.GetDrillSize().x
                if dd < (MM(drill) + other) / 2 + MM(hole_cl):
                    return None, "hole-to-hole"
    ok, hit = clear({pcbnew.F_Cu: t.GetEffectiveShape(pcbnew.F_Cu)}, vpos, net, cl, new_items)
    if not ok:
        return None, "stub vs %s" % (hit.GetParentFootprint().GetReference() if hit.GetParentFootprint() else hit.GetClass())
    ref = in_back_courtyard(vpos, d / 2 + 0.15)
    if ref:
        return None, "under " + ref
    return (v, t), ""


def commit(vt):
    for it in vt:
        B.Add(it); new_items.append(it)


report = []
# ---- U1 spare balls
u1 = B.FindFootprintByReference("U1")
cx, cy = u1.GetPosition().x, u1.GetPosition().y
skip_prefix = ("HDTX",)
for p in sorted(u1.Pads(), key=lambda p: p.GetNumber()):
    n = p.GetNetname()
    if not n.startswith("unconnected-") or not p.GetPinFunction() or p.GetPinFunction().startswith(skip_prefix):
        continue
    pos = p.GetPosition()
    # diagonals, outward-from-centre first
    ds = sorted([(sx, sy) for sx in (-1, 1) for sy in (-1, 1)],
                key=lambda s: -(s[0] * (pos.x - cx) + s[1] * (pos.y - cy)))
    why = []
    for sx, sy in ds:
        vpos = pcbnew.VECTOR2I(pos.x + sx * MM(0.4), pos.y + sy * MM(0.4))
        vt, w = try_place(pos, p.GetNetCode(), vpos, 0.45, 0.2, 0.1, 0.13, 0.3)
        if vt:
            commit(vt)
            report.append(("U1", p.GetNumber(), p.GetPinFunction(), round(mm(vpos.x) - OX, 2), round(mm(vpos.y) - OY, 2)))
            break
        why.append(w)
    else:
        report.append(("U1", p.GetNumber(), p.GetPinFunction(), None, ";".join(why)))

# ---- U9 spare pads: right column stub to +x, bottom row stub to +y
u9 = B.FindFootprintByReference("U9")
spare9 = [p for p in sorted(u9.Pads(), key=lambda p: p.GetNumber())
          if p.GetNetname().startswith("unconnected-") and p.GetNumber().isdigit()]
failed9 = []
for p in spare9:
    pos = p.GetPosition(); num = int(p.GetNumber())
    if 32 <= num <= 39:
        cands = [P(mm(pos.x) - OX + dx, mm(pos.y) - OY) for dx in (1.55, 1.8, 2.1, 2.5)]
        edge = P(mm(pos.x) - OX + 0.5, mm(pos.y) - OY)
    else:
        cands = [P(mm(pos.x) - OX, mm(pos.y) - OY + dy) for dy in (1.4, 1.7, 2.0, 2.5)]
        edge = P(mm(pos.x) - OX, mm(pos.y) - OY + 0.5)
    for vpos in cands:
        vt, w = try_place(edge, p.GetNetCode(), vpos, 0.6, 0.3, 0.2, 0.16, 0.5)
        if vt:
            commit(vt)
            report.append(("U9", p.GetNumber(), p.GetPinFunction(), round(mm(vpos.x) - OX, 2), round(mm(vpos.y) - OY, 2)))
            break
    else:
        failed9.append(p)
for p in failed9:
    pos = p.GetPosition()
    num = int(p.GetNumber())
    if 32 <= num <= 39:
        cands = [P(mm(pos.x) - OX + dx, mm(pos.y) - OY) for dx in (1.55, 1.8, 2.1, 2.5)]
        edge = P(mm(pos.x) - OX + 0.5, mm(pos.y) - OY)
    else:
        cands = [P(mm(pos.x) - OX, mm(pos.y) - OY + dy) for dy in (1.4, 1.7, 2.0, 2.5)]
        edge = P(mm(pos.x) - OX, mm(pos.y) - OY + 0.5)
    why = []
    if True:
        placed = False
        out = (1, 0) if 32 <= num <= 39 else (0, 1)
        for r in (1.6, 2.0, 2.4, 2.8, 3.2):
            for k in range(-6, 7):
                a = math.radians(k * 15)
                dx = out[0] * math.cos(a) - out[1] * math.sin(a); dy = out[0] * math.sin(a) + out[1] * math.cos(a)
                vpos = P(mm(edge.x) - OX + r * dx, mm(edge.y) - OY + r * dy)
                vt, w = try_place(edge, p.GetNetCode(), vpos, 0.6, 0.3, 0.2, 0.16, 0.5)
                if vt:
                    commit(vt); placed = True
                    report.append(("U9", p.GetNumber(), p.GetPinFunction(), round(mm(vpos.x) - OX, 2), round(mm(vpos.y) - OY, 2)))
                    break
            if placed:
                break
        if not placed:
            report.append(("U9", p.GetNumber(), p.GetPinFunction(), None, ";".join(why)))

# ---- existing nets: uncover the back of one via (prefer one not under a back part, largest pad)
for net in ("CLK_25MHz", "PWREN", "SHUTDOWN", "VBAT_OR", "WIFIEN"):
    vs = [t for t in tracks if t.GetClass() == "PCB_VIA" and t.GetNetname().split("/")[-1] == net]
    vs.sort(key=lambda v: -v.GetWidth(pcbnew.F_Cu))
    pick = None
    for v in vs:
        if not in_back_courtyard(v.GetPosition(), mm(v.GetWidth(pcbnew.F_Cu)) / 2 + 0.15):
            pick = v; break
    if pick:
        pick.SetBackTentingMode(pcbnew.TENTING_MODE_NOT_TENTED)
        report.append(("NET", net, "", round(mm(pick.GetPosition().x) - OX, 2), round(mm(pick.GetPosition().y) - OY, 2)))
    else:
        done = False
        for pd in [q for q in pads if q.GetNetname().split("/")[-1] == net and not q.GetParentFootprint().IsFlipped()]:
            pp = pd.GetPosition()
            for r in (0.9, 1.2, 1.5, 1.9):
                for k in range(16):
                    a = math.radians(k * 22.5)
                    vpos = pcbnew.VECTOR2I(int(pp.x + MM(r) * math.cos(a)), int(pp.y + MM(r) * math.sin(a)))
                    vt, w = try_place(pp, pd.GetNetCode(), vpos, 0.6, 0.3, 0.2, 0.16, 0.5)
                    if vt:
                        commit(vt); done = True
                        report.append(("NET", net, "new via from " + pd.GetParentFootprint().GetReference(), round(mm(vpos.x) - OX, 2), round(mm(vpos.y) - OY, 2)))
                        break
                if done: break
            if done: break
        if not done:
            report.append(("NET", net, "", None, "no room"))

for r in report:
    print(*r)
print("placed", sum(1 for r in report if r[3] is not None), "of", len(report))
if "--save" in sys.argv:
    pcbnew.ZONE_FILLER(B).Fill(B.Zones())
    B.Save("FCL.kicad_pcb"); print("saved")
