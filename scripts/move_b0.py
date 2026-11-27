#!/usr/bin/env python3
"""Move the power button B0 from under cell 3 to the top strip (next to B1 / B2), reachable through the rear shell.

    flatpak run --command=python3 org.kicad.KiCad scripts/move_b0.py [X Y ROT]     (repo root, run once)

* B0 (KMR2, back side) moves to (X, Y), default (9.0, 4.0), rotation 90: left of B1, outside the U9 antenna keepout
  (x >= 43.6, y <= 6) and clear of cell 1 (its can starts at y 6.2), the cell-1 block flange (x <= 7.0) and the TFT ring.
* Where its pin-1 pads used to pass PWRBTn through, a B.Cu track bridges the two halves of the net.
* New PWRBTn link: B.Cu stub from pin 1 to a via, then an In1.Cu track (path search on a 0.1 mm grid, CLR from
  everything else on In1) to the existing PWRBTn via at (19.5, 15.8).
* GND pins connect through the B.Cu GND pour.
"""
import heapq
import math
import sys
import pcbnew

BOARD = "FCL.kicad_pcb"
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
NEW = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (9.0, 4.0)
ROT = float(sys.argv[3]) if len(sys.argv) > 3 else 90.0
TARGET = (19.5, 15.8)                       # existing PWRBTn via
W, CLR, VIA_D, VIA_DR = 0.15, 0.22, 0.45, 0.2
GRID = 0.1
X0, X1, Y0, Y1 = 1.0, 32.0, 0.6, 26.0
b = pcbnew.LoadBoard(BOARD)
KEEP = []
NET = "PWRBTn"
F, IN1, BCU = b.GetLayerID("F.Cu"), b.GetLayerID("In1.Cu"), b.GetLayerID("B.Cu")


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(p):
    return (mm(p.x) - OX, mm(p.y) - OY)


def ps(p, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    L = dx * dx + dy * dy
    u = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def add(layer, pts, w):
    for p0, p1 in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(V(*p0))
        t.SetEnd(V(*p1))
        t.SetWidth(MM(w))
        t.SetLayer(layer)
        t.SetNet(b.FindNet(NET))
        b.Add(t)


def via(p):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(V(*p))
    v.SetWidth(MM(VIA_D))
    v.SetDrill(MM(VIA_DR))
    v.SetNet(b.FindNet(NET))
    b.Add(v)


# ---- 1. move B0, bridge the net through its old pin-1 pads
b0 = b.FindFootprintByReference("B0")
old1 = [xy(p.GetPosition()) for p in b0.Pads() if p.GetNetname() == NET]
assert len(old1) == 2, old1
b0.SetOrientationDegrees(ROT)
b0.SetPosition(V(*NEW))
add(BCU, [old1[0], old1[1]], W)
add(BCU, [(48.3, 58.75), (48.1161, 58.3847)], W)          # tracks that ended on the old pads
add(BCU, [(50.75, 61.0), (51.0153, 61.2839)], W)
add(BCU, [min(old1, key=lambda q: math.hypot(q[0] - 51.0, q[1] - 61.85)), (51.0, 61.85)], W)   # old route left the pad at its edge
pads = {p.GetNumber(): [] for p in b0.Pads()}
for p in b0.Pads():
    pads[p.GetNumber()].append((xy(p.GetPosition()), p))
p1 = sorted(q for q, _ in pads["1"])
add(BCU, [p1[0], p1[1]], W)                            # the two pin-1 pads are one contact inside the switch
ends = set()
for t in b.GetTracks():
    if t.GetClass() != "PCB_VIA":
        ends |= {(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)}
gone = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND" and (t.GetPosition().x, t.GetPosition().y) not in ends:
        c = xy(t.GetPosition())
        if any(math.hypot(c[0] - q[0], c[1] - q[1]) < 1.6 for v in pads.values() for q, _ in v):
            KEEP.append(t)
            b.Remove(t)
            gone += 1
print("GND stitching vias under B0 removed:", gone)
print("B0 now at", NEW, "pads", {k: [tuple(round(c, 2) for c in q) for q, _ in v] for k, v in pads.items()})

# ---- obstacles (everything not PWRBTn), per layer
obs = {F: [], IN1: [], BCU: []}
for t in b.GetTracks():
    if t.GetNetname() == NET:
        continue
    if t.GetClass() == "PCB_VIA":
        for l in obs:
            obs[l].append(("c", xy(t.GetPosition()), mm(t.GetWidth(pcbnew.F_Cu)) / 2))
    elif t.GetLayer() in obs:
        obs[t.GetLayer()].append(("s", (xy(t.GetStart()), xy(t.GetEnd())), mm(t.GetWidth()) / 2))
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() == NET:
            continue
        bb = p.GetBoundingBox()
        r = (mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY)
        for l in obs:
            if p.IsOnLayer(l) or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                obs[l].append(("r", r, 0.0))


def dist(l, q):
    m = 99.0
    for k, g, r in obs[l]:
        if k == "c":
            d = math.hypot(q[0] - g[0], q[1] - g[1]) - r
        elif k == "s":
            d = ps(q, g[0], g[1]) - r
        else:
            d = math.hypot(max(g[0] - q[0], 0, q[0] - g[2]), max(g[1] - q[1], 0, q[1] - g[3]))
        m = min(m, d)
    return m


# ---- 2. via beside pin 1 (all layers clear for a via)
best = None
for (q, _) in pads["1"]:
    for ang in range(0, 360, 15):
        for r in (1.0, 1.2, 1.4, 1.6, 1.8, 2.0):
            c = (q[0] + r * math.cos(math.radians(ang)), q[1] + r * math.sin(math.radians(ang)))
            if not (X0 < c[0] < X1 and Y0 + 0.3 < c[1] < Y1):
                continue
            d = min(dist(l, c) for l in obs) - VIA_D / 2
            if d >= CLR + 0.03 and (best is None or r < best[0]):
                best = (r, c, q)
    if best:
        break
assert best, "no room for a via next to pin 1"
_, vpos, pin = best
print("via at", tuple(round(v, 2) for v in vpos), "from pin", tuple(round(v, 2) for v in pin))

# ---- 3. In1 path search from the via to TARGET
nx, ny = int((X1 - X0) / GRID) + 1, int((Y1 - Y0) / GRID) + 1
need = W / 2 + CLR
in1_segs = [(k, g, r) for k, g, r in obs[IN1]]
free = {}


def ok(i, j):
    k = (i, j)
    if k not in free:
        q = (X0 + i * GRID, Y0 + j * GRID)
        free[k] = dist(IN1, q) >= need
    return free[k]


def cell(p):
    return (int(round((p[0] - X0) / GRID)), int(round((p[1] - Y0) / GRID)))


s, g = cell(vpos), cell(TARGET)
openq = [(0, s)]
came = {s: None}
cost = {s: 0.0}
steps = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
while openq:
    _, cur = heapq.heappop(openq)
    if cur == g:
        break
    for dx, dy, c in steps:
        n = (cur[0] + dx, cur[1] + dy)
        if not (0 <= n[0] < nx and 0 <= n[1] < ny):
            continue
        if n != g and not ok(*n):
            continue
        nc = cost[cur] + c
        if nc < cost.get(n, 1e9):
            cost[n] = nc
            came[n] = cur
            heapq.heappush(openq, (nc + math.hypot(n[0] - g[0], n[1] - g[1]), n))
assert g in came, "no In1 path"
path = []
n = g
while n is not None:
    path.append((X0 + n[0] * GRID, Y0 + n[1] * GRID))
    n = came[n]
path.reverse()
path[0], path[-1] = vpos, TARGET


def clear_line(a, c):
    L = math.hypot(c[0] - a[0], c[1] - a[1])
    k = max(1, int(L / 0.05))
    return all(dist(IN1, (a[0] + (c[0] - a[0]) * t / k, a[1] + (c[1] - a[1]) * t / k)) >= need for t in range(1, k))


simp = [path[0]]
i = 0
while i < len(path) - 1:
    j = len(path) - 1
    while j > i + 1 and not clear_line(path[i], path[j]):
        j -= 1
    simp.append(path[j])
    i = j
length = sum(math.hypot(c[0] - a[0], c[1] - a[1]) for a, c in zip(simp, simp[1:]))
print("In1 path:", len(simp) - 1, "segments,", round(length, 1), "mm:", [tuple(round(v, 2) for v in p) for p in simp])

via(vpos)
add(BCU, [pin, vpos], W)
add(IN1, simp, W)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
