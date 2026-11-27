#!/usr/bin/env python3
"""Two J7-area vias off the pads they touched.

    flatpak run --command=python3 org.kicad.KiCad scripts/fix_j7_vias.py     (repo root, run once)

* C38 GND via (36.13, 67.7) sat on the edge of C38 pad 2 -> (34.13, 67.7), between the C38 pads, short F.Cu link.
* LCD_BL_A via (44.13, 67.3) touched the end of J7 pad 2 -> (44.83, 66.8), in the gap between pad 2 and the
  J7 mounting pad (0.175 mm to each); F.Cu straight on to it, short B.Cu link into pad 2.
"""
import pcbnew

BOARD = "FCL.kicad_pcb"
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
b = pcbnew.LoadBoard(BOARD)
KEEP = []
F, B_ = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")
A = "/display/LCD_BL_A"


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(p):
    return (round(mm(p.x) - OX, 3), round(mm(p.y) - OY, 3))


def near(a, c, tol=0.02):
    return abs(a[0] - c[0]) < tol and abs(a[1] - c[1]) < tol


def rm_track(layer, net, p0, p1):
    hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == net and t.GetLayer() == layer
           and ((near(xy(t.GetStart()), p0) and near(xy(t.GetEnd()), p1)) or (near(xy(t.GetStart()), p1) and near(xy(t.GetEnd()), p0)))]
    assert len(hit) == 1, (net, p0, p1, len(hit))
    KEEP.append(hit[0])
    b.Remove(hit[0])


def mv_via(net, p, q):
    hit = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == net and near(xy(t.GetPosition()), p)]
    assert len(hit) == 1, (net, p, len(hit))
    hit[0].SetPosition(V(*q))


def add(layer, net, pts, w):
    for p0, p1 in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(V(*p0))
        t.SetEnd(V(*p1))
        t.SetWidth(MM(w))
        t.SetLayer(layer)
        t.SetNet(b.FindNet(net))
        b.Add(t)


rm_track(F, "GND", (35.638, 67.483), (36.13, 67.7))
mv_via("GND", (36.13, 67.7), (34.13, 67.7))
add(F, "GND", [(35.638, 67.483), (35.42, 67.7), (34.13, 67.7)], 0.3)

rm_track(F, A, (43.63, 66.8), (44.13, 67.3))
rm_track(B_, A, (44.13, 67.3), (44.13, 66.3))
mv_via(A, (44.13, 67.3), (44.83, 66.8))
add(F, A, [(43.63, 66.8), (44.83, 66.8)], 0.4)
add(B_, A, [(44.83, 66.8), (44.13, 66.8)], 0.3)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
