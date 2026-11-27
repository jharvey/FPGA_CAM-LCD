#!/usr/bin/env python3
"""Widen CELL2_RAW where there is room.

    flatpak run --command=python3 org.kicad.KiCad scripts/widen_cell2.py [--dry]     (repo root, run once)

1. GND stitching vias (no track attached) that sit within reach of a CELL2_RAW track are removed.
2. Every CELL2_RAW track is cut into 0.5 mm steps; each step gets the widest of WIDTHS that keeps CLR from all
   other-net copper on its layer (tracks, pads, vias), HOLE_CLR from holes and EDGE from the board outline.
   Steps of the same width are joined again.  Never narrower than now, never wider than MAXW.
Zones are refilled afterwards; run DRC to confirm.
"""
import math
import sys
import pcbnew

BOARD = "FCL.kicad_pcb"
NET = "/power/CELL2_RAW"
WIDTHS = (2.0, 1.8, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0)
MAXW = 2.0
STEP = 0.5
CLR, EDGE, HOLE_CLR = 0.25, 0.55, 0.3        # board edge rule is 0.5
VIA_REACH = MAXW / 2 + CLR + 0.35          # GND stitching vias closer than this to the track centre line go
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
DRY = "--dry" in sys.argv
b = pcbnew.LoadBoard(BOARD)
KEEP = []


def xy(p):
    return (mm(p.x) - OX, mm(p.y) - OY)


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def ps(p, s0, s1):
    dx, dy = s1[0] - s0[0], s1[1] - s0[1]
    L = dx * dx + dy * dy
    u = 0 if L == 0 else max(0, min(1, ((p[0] - s0[0]) * dx + (p[1] - s0[1]) * dy) / L))
    return math.hypot(p[0] - s0[0] - u * dx, p[1] - s0[1] - u * dy)


def seg_seg(a, b_, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if o(a, b_, c) * o(a, b_, d) < 0 and o(c, d, a) * o(c, d, b_) < 0:
        return 0.0
    return min(ps(a, c, d), ps(b_, c, d), ps(c, a, b_), ps(d, a, b_))


def seg_rect(a, c, r):
    x0, y0, x1, y1 = r
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
        return 0.0
    es = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(seg_seg(a, c, e0, e1) for e0, e1 in es)


cell2 = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == NET]

# ---- 1. GND stitching vias near the track
ends = {}
for t in b.GetTracks():
    if t.GetClass() != "PCB_VIA" and t.GetNetname() == "GND":
        for p in (t.GetStart(), t.GetEnd()):
            ends[(p.x, p.y)] = 1
gone = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        q = t.GetPosition()
        if (q.x, q.y) in ends:
            continue                                     # a via with a track on it: keep
        c = xy(q)
        if any(ps(c, xy(s.GetStart()), xy(s.GetEnd())) < VIA_REACH for s in cell2):
            KEEP.append(t)
            if not DRY:
                b.Remove(t)
            gone += 1
print("GND stitching vias removed beside CELL2_RAW:", gone)
removed = {id(v) for v in KEEP}

# ---- obstacles
layers = [b.GetLayerID(n) for n in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")]
obs = {lid: [] for lid in layers}
holes = []
for t in b.GetTracks():
    if t.GetNetname() == NET or id(t) in removed:
        continue
    if t.GetClass() == "PCB_VIA":
        for lid in layers:
            obs[lid].append(("pt", xy(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu)) / 2))
        holes.append((xy(t.GetPosition()), mm(t.GetDrill()) / 2))
    else:
        obs[t.GetLayer()].append(("seg", (xy(t.GetStart()), xy(t.GetEnd())), mm(t.GetWidth()) / 2))
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetDrillSize().x > 0:
            holes.append((xy(p.GetPosition()), mm(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2))
        if p.GetNetname() == NET or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            continue
        bb = p.GetBoundingBox()
        r = (mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY)
        for lid in layers:
            if p.IsOnLayer(lid):
                obs[lid].append(("rect", r, 0.0))
edge = []
for d in b.GetDrawings():
    if d.GetLayer() == b.GetLayerID("Edge.Cuts"):
        if d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            edge.append((xy(d.GetStart()), xy(d.GetEnd())))
        elif d.GetShape() == pcbnew.SHAPE_T_ARC:
            pts = [d.GetStart(), d.GetArcMid(), d.GetEnd()]
            edge += [(xy(pts[0]), xy(pts[1])), (xy(pts[1]), xy(pts[2]))]


def half_room(layer, a, c):
    m = 99.0
    for kind, g, r in obs[layer]:
        if kind == "seg":
            m = min(m, seg_seg(a, c, g[0], g[1]) - r - CLR)
        elif kind == "pt":
            m = min(m, ps(g, a, c) - r - CLR)
        else:
            m = min(m, seg_rect(a, c, g) - CLR)
    for (h, r) in holes:
        m = min(m, ps(h, a, c) - r - HOLE_CLR)
    for e0, e1 in edge:
        m = min(m, seg_seg(a, c, e0, e1) - EDGE)
    return m


# ---- 2. per 0.5 mm step
before = after = 0.0
total = 0.0
for t in cell2:
    lid, w0 = t.GetLayer(), mm(t.GetWidth())
    a, c = xy(t.GetStart()), xy(t.GetEnd())
    L = math.hypot(c[0] - a[0], c[1] - a[1])
    n = max(1, int(math.ceil(L / STEP)))
    pts = [(a[0] + (c[0] - a[0]) * i / n, a[1] + (c[1] - a[1]) * i / n) for i in range(n + 1)]
    ws = []
    for p0, p1 in zip(pts, pts[1:]):
        h = half_room(lid, p0, p1)
        w = next((x for x in WIDTHS if x / 2 <= h + 1e-6), w0)
        ws.append(max(w0, min(w, MAXW)))
    runs = []                                            # (start index, end index, width)
    for i, w in enumerate(ws):
        if runs and abs(runs[-1][2] - w) < 1e-6:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1, w])
    total += L
    before += L * w0
    after += sum((r[1] - r[0]) * L / n * r[2] for r in runs)
    if len(runs) == 1 and abs(runs[0][2] - w0) < 1e-6:
        continue
    print(f"{b.GetLayerName(lid):6s} ({a[0]:6.2f},{a[1]:6.2f})-({c[0]:6.2f},{c[1]:6.2f}) L {L:5.2f}  w {w0:.2f} -> "
          + " ".join(f"{r[2]:.1f}x{(r[1] - r[0]) * L / n:.1f}" for r in runs))
    if DRY:
        continue
    net = t.GetNet()
    KEEP.append(t)
    b.Remove(t)
    for i0, i1, w in runs:
        nt = pcbnew.PCB_TRACK(b)
        nt.SetStart(V(*pts[i0]))
        nt.SetEnd(V(*pts[i1]))
        nt.SetWidth(MM(w))
        nt.SetLayer(lid)
        nt.SetNet(net)
        b.Add(nt)
print(f"CELL2_RAW tracks {total:.1f} mm long; average width {before / total:.2f} -> {after / total:.2f} mm")
if not DRY:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(BOARD)
    print("saved")
