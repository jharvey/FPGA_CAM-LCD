#!/usr/bin/env python3
"""Second pass after place_battery_blocks.py:
 - re-route the left-edge entries of TEMP_BAT_CELL1/2/3 on In1 so they clear the new block holes
 - remove GND stitching vias that sit on the new holes / new trace paths
 - delete the BAY_END_WALL_L rule area (the aluminium blocks are the end wall now)
 - footprint housekeeping on BT12 / BT32: library link, fields copied from the schematic
"""
import math
import pcbnew

BOARD = "FCL.kicad_pcb"
OX, OY = 78.0, 55.5
mm, MM = pcbnew.ToMM, pcbnew.FromMM
b = pcbnew.LoadBoard(BOARD)
KEEP = []


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def near(a, b_, tol=0.03):
    return abs(a[0] - b_[0]) < tol and abs(a[1] - b_[1]) < tol


def seg_xy(t):
    s, e = t.GetStart(), t.GetEnd()
    return (mm(s.x) - OX, mm(s.y) - OY), (mm(e.x) - OX, mm(e.y) - OY)


REROUTE = {
    "/power/TEMP_BAT_CELL1": {
        "delete": [((5.4, 23.4), (5.97, 23.4)), ((1.6, 27.2), (5.4, 23.4)), ((1.6, 47.23), (1.6, 27.2)),
                   ((0.6, 48.23), (1.6, 47.23)), ((0.6, 73.07), (0.6, 48.23))],
        "add": [(5.97, 23.4), (5.97, 26.4), (1.6, 30.77), (1.6, 40.0), (0.6, 41.0), (0.6, 73.07)],
    },
    "/power/TEMP_BAT_CELL2": {
        "delete": [((18.03, 37.53), (10.95, 44.6)), ((10.95, 44.6), (4.8, 44.6)), ((4.8, 44.6), (1.0, 48.4)),
                   ((1.0, 48.4), (1.0, 72.9))],
        "add": [(18.03, 37.53), (11.66, 43.9), (1.0, 43.9), (1.0, 72.9)],
    },
    "/power/TEMP_BAT_CELL3": {
        "delete": [((6.8, 64.3), (14.6, 56.5)), ((5.2, 64.3), (6.8, 64.3)), ((1.4, 68.1), (5.2, 64.3)),
                   ((1.4, 72.5), (1.4, 68.1))],
        "add": [(14.6, 56.5), (13.8, 57.3), (2.2, 57.3), (1.4, 58.1), (1.4, 72.5)],
    },
}
DROP_VIAS = [(6.0, 25.28), (2.72, 30.36), (4.5, 43.47), (8.61, 44.07), (6.0, 45.67), (2.2, 63.9)]

in1 = b.GetLayerID("In1.Cu")
for net, r in REROUTE.items():
    width = None
    found = 0
    for t in list(b.GetTracks()):
        if t.GetClass() == "PCB_VIA" or t.GetNetname() != net or t.GetLayer() != in1:
            continue
        a, e = seg_xy(t)
        for d in r["delete"]:
            if (near(a, d[0]) and near(e, d[1])) or (near(a, d[1]) and near(e, d[0])):
                width = t.GetWidth()
                KEEP.append(t)
                b.Remove(t)
                found += 1
                break
    assert found == len(r["delete"]), f"{net}: deleted {found} of {len(r['delete'])}"
    netinfo = b.FindNet(net)
    pts = r["add"]
    for p0, p1 in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(*p0))
        t.SetEnd(P(*p1))
        t.SetWidth(width)
        t.SetLayer(in1)
        t.SetNet(netinfo)
        b.Add(t)
    print(net, "re-routed:", found, "segments replaced by", len(pts) - 1)

n = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        p = t.GetPosition()
        if any(math.hypot(mm(p.x) - OX - x, mm(p.y) - OY - y) < 0.05 for x, y in DROP_VIAS):
            KEEP.append(t)
            b.Remove(t)
            n += 1
print("GND vias removed", n, "of", len(DROP_VIAS))
assert n == len(DROP_VIAS)

for z in list(b.Zones()):
    if z.GetIsRuleArea() and z.GetZoneName() == "BAY_END_WALL_L":
        KEEP.append(z)
        b.Remove(z)
        print("removed rule area BAY_END_WALL_L")

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")

# R78 reference text sat on the BT32 dowel-pin hole: move it above the resistor
b = pcbnew.LoadBoard(BOARD)
r78 = b.FindFootprintByReference("R78")
ref = r78.Reference()
print("R78 ref was at", round(mm(ref.GetPosition().x) - OX, 2), round(mm(ref.GetPosition().y) - OY, 2), "angle", ref.GetTextAngleDegrees())
ref.SetPosition(P(3.6, 61.5))
ref.SetTextAngleDegrees(90)
b.Save(BOARD)
print("R78 reference moved; saved")
