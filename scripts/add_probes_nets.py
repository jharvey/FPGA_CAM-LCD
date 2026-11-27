"""Probe points (part 2: more existing nets). Probe points: spare U1 balls get a dog-bone via with the back side left uncovered (bare copper),
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
NETS = """PWRBTn WAKEUPn HOLD VBUS_C VBAT1 VBAT2 VBAT3 CHG1_CHRGn CHG2_CHRGn CHG3_CHRGn PROG1 PROG2 PROG3 VADC VREF_SENSE
SD3V3 LCD_BL_K GP13 PD_CC1 FPGA_DONE FPGA_INITN FPGA_PROGRAMN FLASH_SCK FLASH_nCS FLASH_MOSI FLASH_MISO
ADC_SCK ADC_SDO ADC_DIN ADC_CNV SD_CLK SD_CMD SD_D0 I2S_BCLK I2S_WS I2S_SPK I2S_MIC AMP_SD IMU_INT1 TOF_INT MAG_DRDY
BARO_INT""".split()
already = {t.GetNetname().split("/")[-1] for t in tracks if t.GetClass() == "PCB_VIA" and t.GetBackTentingMode() == pcbnew.TENTING_MODE_NOT_TENTED}
for net in NETS:
    if net in already:
        report.append(("NET", net, "already", 0, 0)); continue
    vs = [t for t in tracks if t.GetClass() == "PCB_VIA" and t.GetNetname().split("/")[-1] == net]
    vs.sort(key=lambda v: -v.GetWidth(pcbnew.F_Cu))
    pick = None
    for v in vs:
        if not in_back_courtyard(v.GetPosition(), mm(v.GetWidth(pcbnew.F_Cu)) / 2 + 0.2):
            pick = v; break
    if pick:
        pick.SetBackTentingMode(pcbnew.TENTING_MODE_NOT_TENTED)
        report.append(("NET", net, "via", round(mm(pick.GetPosition().x) - OX, 2), round(mm(pick.GetPosition().y) - OY, 2)))
        continue
    done = False
    for pd in [q for q in pads if q.GetNetname().split("/")[-1] == net and not q.GetParentFootprint().IsFlipped()
               and q.GetParentFootprint().GetReference() not in ("U1", "U9")]:
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
        report.append(("NET", net, "no room", None, None))
for r in report:
    print(*r)
print("placed", sum(1 for r in report if r[3] is not None), "of", len(report))
if "--save" in sys.argv:
    pcbnew.ZONE_FILLER(B).Fill(B.Zones())
    B.Save("FCL.kicad_pcb"); print("saved")
