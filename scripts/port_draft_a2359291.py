#!/usr/bin/env python3
"""Carry the hand re-routing of commit a2359291 (monocular-strip, 2026-11-25) over to this board.

    flatpak run --command=python3 org.kicad.KiCad scripts/port_draft_a2359291.py base.kicad_pcb draft.kicad_pcb
    (repo root, run once; base = FCL.kicad_pcb of 241ea618, draft = FCL.kicad_pcb of a2359291)

Takes the tracks and vias that the draft removed / added relative to its parent and does the same here.
Items the draft removed that this board no longer has are reported and skipped.
"""
import sys
import pcbnew

OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM


def xy(p):
    return (round(mm(p.x) - OX, 3), round(mm(p.y) - OY, 3))


def tkey(b, t):
    a, c = sorted((xy(t.GetStart()), xy(t.GetEnd())))
    return (t.GetNetname(), b.GetLayerName(t.GetLayer()), a, c, round(mm(t.GetWidth()), 3))


def vkey(t):
    return (t.GetNetname(), xy(t.GetPosition()), round(mm(t.GetWidth(pcbnew.F_Cu)), 3), round(mm(t.GetDrill()), 3))


def sets(p):
    b = pcbnew.LoadBoard(p)
    trk, via = set(), set()
    for t in b.GetTracks():
        (via.add(vkey(t)) if t.GetClass() == "PCB_VIA" else trk.add(tkey(b, t)))
    return trk, via


(ta, va), (tb, vb) = sets(sys.argv[1]), sets(sys.argv[2])
rm_t, add_t, rm_v, add_v = ta - tb, tb - ta, va - vb, vb - va
assert not add_v
b = pcbnew.LoadBoard("FCL.kicad_pcb")
KEEP = []
have_t = {tkey(b, t): t for t in b.GetTracks() if t.GetClass() != "PCB_VIA"}
have_v = {vkey(t): t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"}
missing = []
for k in sorted(rm_t):
    if k in have_t:
        KEEP.append(have_t[k])
        b.Remove(have_t[k])
    else:
        missing.append(k)
for k in sorted(rm_v):
    if k in have_v:
        KEEP.append(have_v[k])
        b.Remove(have_v[k])
    else:
        missing.append(k)
skipped = []
for net, layer, p0, p1, w in sorted(add_t):
    if (net, layer, p0, p1, w) in have_t:
        skipped.append((net, layer, p0, p1))
        continue
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(MM(OX + p0[0]), MM(OY + p0[1])))
    t.SetEnd(pcbnew.VECTOR2I(MM(OX + p1[0]), MM(OY + p1[1])))
    t.SetWidth(MM(w))
    t.SetLayer(b.GetLayerID(layer))
    t.SetNet(b.FindNet(net))
    b.Add(t)
print("removed", len(rm_t) + len(rm_v) - len(missing), "added", len(add_t) - len(skipped))
print("draft removed these, not on this board (skipped):", len(missing))
for k in missing:
    print("   ", k)

# ---- left edge: this board already has the three thermistor tracks at x 0.6 / 1.0 / 1.4 (moved for the block mounts),
# so the draft's own left-edge runs (x 0.95 / 1.35 / 1.725) are dropped and its three diagonals into the bottom
# edge are extended up to the existing verticals (same lines, 0.4 mm apart).
in1 = b.GetLayerID("In1.Cu")
P = "/power/TEMP_BAT_CELL"
DROP = {1: [((0.95, 47.884), (1.6, 47.234)), ((0.95, 47.884), (0.95, 75.4)), ((0.95, 75.4), (3.85, 78.3))],
        2: [((1.35, 48.05), (4.8, 44.6)), ((1.35, 48.05), (1.35, 75.2)), ((1.35, 75.2), (4.048, 77.898))],
        3: [((1.725, 67.775), (1.725, 74.925)), ((1.725, 67.775), (5.2, 64.3)), ((1.725, 74.925), (4.323, 77.523))]}
# cell: (x of the existing vertical, its old lower end y, new lower end y, end of the diagonal on the bottom run, width)
JOIN = {1: (0.6, 73.07, 75.05, (3.85, 78.3), 0.2), 2: (1.0, 72.9, 74.85, (4.048, 77.898), 0.2), 3: (1.4, 72.5, 74.6, (4.323, 77.523), 0.15)}


def near(a, c, tol=0.006):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


for n in (1, 2, 3):
    net = P + str(n)
    for p0, p1 in DROP[n]:
        hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == net and t.GetLayer() == in1
               and ((near(xy(t.GetStart()), p0) and near(xy(t.GetEnd()), p1)) or (near(xy(t.GetStart()), p1) and near(xy(t.GetEnd()), p0)))]
        assert len(hit) == 1, (net, p0, p1, len(hit))
        KEEP.append(hit[0])
        b.Remove(hit[0])
    x, y_old, y_new, end, w = JOIN[n]
    hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == net and t.GetLayer() == in1
           and (near(xy(t.GetStart()), (x, y_old)) or near(xy(t.GetEnd()), (x, y_old)))]
    assert len(hit) == 1, (net, "vertical", len(hit))
    v = hit[0]
    q = pcbnew.VECTOR2I(MM(OX + x), MM(OY + y_new))
    if near(xy(v.GetStart()), (x, y_old)):
        v.SetStart(q)
    else:
        v.SetEnd(q)
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(q)
    t.SetEnd(pcbnew.VECTOR2I(MM(OX + end[0]), MM(OY + end[1])))
    t.SetWidth(MM(w))
    t.SetLayer(in1)
    t.SetNet(b.FindNet(net))
    b.Add(t)
print("left edge joined")
zero = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetStart() == t.GetEnd()]
for t in zero:                      # zero-length leftovers of the hand edit
    KEEP.append(t)
    b.Remove(t)
print("zero-length tracks removed:", len(zero))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save("FCL.kicad_pcb")
print("saved")
