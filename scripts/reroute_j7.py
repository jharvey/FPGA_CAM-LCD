#!/usr/bin/env python3
"""Re-route the copper round the vertical J7 (FH12-40S-0.5SV, back side) after the flat -> vertical swap.

    flatpak run --command=python3 org.kicad.KiCad scripts/reroute_j7.py     (repo root, run once)

The backlight boost converter sits on the front right over J7, and its vias came out in the new pad rows.
  * vias moved into the 1.5 mm strip between the two pad rows (x = n + 0.13, between the GN tracks) or deleted
  * LCD_BL_A: C38/U8 -> D1 now on F.Cu (R18 turned 180 deg to make room); pad 2 fed from a via
    between the rows
  * GP13 via moved below the VSYS strip, In1 track re-drawn
  * WAKEUPn moved right of the J7 mounting pad
  * GN tracks 0.13 mm where they pass between the even-row pads (0.135 mm gap; the fan-out rule asks 0.127)
"""
import pcbnew

BOARD = "FCL.kicad_pcb"
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
b = pcbnew.LoadBoard(BOARD)
KEEP = []
L = {n: b.GetLayerID(n) for n in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")}


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(p):
    return (mm(p.x) - OX, mm(p.y) - OY)


def near(a, c, tol=0.02):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


def rm_track(layer, net, p0, p1):
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA" and t.GetNetname() == net and t.GetLayer() == L[layer]:
            s, e = xy(t.GetStart()), xy(t.GetEnd())
            if (near(s, p0) and near(e, p1)) or (near(s, p1) and near(e, p0)):
                KEEP.append(t)
                b.Remove(t)
                return t.GetWidth()
    raise AssertionError(("track not found", layer, net, p0, p1))


def get_via(net, p):
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == net and near(xy(t.GetPosition()), p):
            return t
    raise AssertionError(("via not found", net, p))


def rm_via(net, p):
    v = get_via(net, p)
    KEEP.append(v)
    b.Remove(v)


def mv_via(net, p, q, small=False):
    v = get_via(net, p)
    v.SetPosition(V(*q))
    if small:
        v.SetWidth(pcbnew.F_Cu, MM(0.45))
        v.SetDrill(MM(0.2))


def add(layer, net, pts, w):
    n = b.FindNet(net)
    assert n is not None, net
    for p0, p1 in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(V(*p0))
        t.SetEnd(V(*p1))
        t.SetWidth(MM(w))
        t.SetLayer(L[layer])
        t.SetNet(n)
        b.Add(t)


A, K = "/display/LCD_BL_A", "/display/LCD_BL_K"

# ---- 1. GN tracks between the even-row pads: 0.13 mm from y 65.0 down to the odd-row pad
n = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" or t.GetLayer() != L["B.Cu"] or not t.GetNetname().startswith("GN"):
        continue
    s, e = xy(t.GetStart()), xy(t.GetEnd())
    if abs(s[0] - e[0]) > 0.01 or not (26 < s[0] < 40):
        continue
    lo, hi = (s, e) if s[1] < e[1] else (e, s)
    if abs(hi[1] - 69.3) > 0.02:
        continue
    if lo[1] < 64.0:                       # long track straight from the FPGA: split it
        if s[1] < e[1]:
            t.SetEnd(V(s[0], 65.0))
        else:
            t.SetStart(V(s[0], 65.0))
        add("B.Cu", t.GetNetname(), [(s[0], 65.0), (s[0], 69.3)], 0.13)
    else:
        t.SetWidth(MM(0.13))
    n += 1
print("GN tracks narrowed:", n)
assert n == 14

# ---- 2. old GND link under the odd row, C37 GND via
for p0, p1 in (((25.13, 66.3), (25.2, 68.0)), ((25.2, 68.0), (25.7, 68.5)), ((25.7, 68.5), (28.2, 68.5)),
               ((28.2, 68.5), (28.2, 68.35)), ((28.2, 68.35), (28.25, 68.3))):
    rm_track("B.Cu", "GND", p0, p1)
rm_track("F.Cu", "GND", (28.25, 68.3), (28.6, 68.3))
mv_via("GND", (28.25, 68.3), (28.13, 67.8))
add("F.Cu", "GND", [(28.13, 67.8), (28.7, 67.98)], 0.3)

# ---- 3. C74 +3V3 via
rm_track("F.Cu", "+3V3", (26.18, 68.9), (26.282, 69.542))
mv_via("+3V3", (26.282, 69.542), (26.15, 67.45), small=True)
add("F.Cu", "+3V3", [(26.18, 68.9), (26.15, 67.45)], 0.25)

# ---- 4. C75: the two vias in the odd row go; the vias between the rows stay
rm_track("F.Cu", "+3V3", (43.55, 69.4), (44.4, 69.4))
rm_via("+3V3", (44.4, 69.4))
add("F.Cu", "+3V3", [(43.781, 68.471), (43.6, 69.0)], 0.3)
rm_track("F.Cu", "GND", (41.65, 69.4), (42.5, 69.4))
rm_via("GND", (42.5, 69.4))
add("F.Cu", "GND", [(41.63, 68.13), (41.63, 68.9)], 0.3)

# ---- 5. LCD_BL_A to J7 pad 2: via between the rows under the pad
rm_track("F.Cu", A, (39.6, 66.8), (46.6, 66.8))
rm_track("B.Cu", A, (46.6, 66.8), (44.9, 65.1))
rm_track("F.Cu", A, (44.9, 65.1), (43.3, 65.1))
rm_track("B.Cu", A, (43.3, 65.1), (44.1, 65.9))
rm_track("B.Cu", A, (44.1, 65.9), (44.13, 66.3))
rm_via(A, (44.9, 65.1))
rm_via(A, (43.3, 65.1))
mv_via(A, (46.6, 66.8), (44.13, 67.3), small=True)
add("F.Cu", A, [(39.6, 66.8), (43.63, 66.8), (44.13, 67.3)], 0.4)
add("B.Cu", A, [(44.13, 67.3), (44.13, 66.3)], 0.4)
# LCD_BL_K passes under that via
rm_track("F.Cu", K, (41.4, 67.55), (43.95, 67.55))
rm_track("F.Cu", K, (43.95, 67.55), (44.6, 68.2))
add("F.Cu", K, [(41.4, 67.55), (43.4, 67.55)], 0.4)
add("F.Cu", K, [(43.4, 67.55), (43.725, 67.875), (44.275, 67.875), (44.6, 68.2)], 0.3)

# ---- 6. R18 turned 180 deg: GP13 pad on top, GND pad next to R19
r18 = b.FindFootprintByReference("R18")
r18.SetOrientationDegrees((r18.GetOrientationDegrees() + 180) % 360)
p = r18.GetPosition()
r18.SetPosition(pcbnew.VECTOR2I(p.x, p.y + MM(0.04)))
pads = {q.GetNetname(): xy(q.GetPosition()) for q in r18.Pads()}
print("R18 pads:", pads)
assert pads["GP13"][1] < pads["GND"][1]
gp, gn = pads["GP13"], pads["GND"]
rm_track("F.Cu", "GND", (35.3, 68.3), (35.3, 68.9))
rm_track("F.Cu", "GND", (35.3, 68.9), (35.35, 68.95))
add("F.Cu", "GND", [gn, (35.65, 71.3)], 0.3)

# ---- 7. LCD_BL_A, C38 / U8 -> D1 on the front (was a hop on the back through the odd row)
rm_track("F.Cu", A, (33.95, 68.35), (34.6, 68.35))
rm_track("B.Cu", A, (34.6, 68.35), (35.85, 68.35))
rm_track("B.Cu", A, (35.85, 68.35), (37.05, 69.55))
rm_track("F.Cu", A, (37.05, 69.55), (37.4, 69.55))
rm_track("F.Cu", A, (37.4, 69.55), (37.5, 69.45))
rm_via(A, (34.6, 68.35))
rm_via(A, (37.05, 69.55))
add("F.Cu", A, [(33.95, 68.35), (34.4, 68.35), (34.71, 68.66), (37.7, 68.66)], 0.25)
# C38 GND via
rm_track("F.Cu", "GND", (35.638, 67.483), (36.817, 68.327))
mv_via("GND", (36.817, 68.327), (36.13, 67.7), small=True)
add("F.Cu", "GND", [(35.638, 67.483), (36.13, 67.7)], 0.3)

# ---- 8. GP13: via below the VSYS strip, In1 track re-drawn
rm_track("F.Cu", "GP13", (34.45, 70.0), (35.3, 70.0))
rm_track("F.Cu", "GP13", (36.3, 69.7), (35.7, 70.19))
for p0, p1 in (((36.3, 69.7), (36.3, 69.5)), ((36.3, 69.5), (36.95, 68.85)), ((36.95, 68.85), (37.1, 68.85)),
               ((37.1, 68.85), (41.05, 64.9))):
    rm_track("In1.Cu", "GP13", p0, p1)
mv_via("GP13", (36.3, 69.7), (36.8, 71.45))
add("F.Cu", "GP13", [(34.3, gp[1]), gp, (36.5, gp[1]), (36.8, gp[1] + 0.3), (36.8, 71.45)], 0.15)
add("In1.Cu", "GP13", [(41.05, 64.9), (41.05, 66.48), (36.8, 70.73), (36.8, 71.45)], 0.15)

# ---- 9. WAKEUPn right of the J7 mounting pad
rm_track("B.Cu", "/power/WAKEUPn", (48.65, 69.65), (40.95, 61.95))
rm_via("GND", (46.5, 64.252))
add("B.Cu", "/power/WAKEUPn", [(40.95, 61.95), (45.25, 61.95), (46.5, 63.2), (46.5, 67.5), (48.65, 69.65)], 0.15)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
