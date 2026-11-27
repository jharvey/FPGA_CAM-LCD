"""Lesson 5: a map of a room from one spot.

Stand in a room and aim at each corner on the floor.  Heading, pitch and distance put every corner on a map; the
"shoelace" sum gives the area of any shape from its corners.

    python doc/lessons/examples/lesson5_room.py          writes lesson5_plan.svg next to this file
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "firmware", "tools"))
import fcl              # noqa: E402
import fcl_survey       # noqa: E402

EYE = 1.3                                                         # the unit's height above the floor
# an L-shaped room; (east, north) of each corner in metres from where we stand, going round
ROOM = ((2.0, 1.5), (2.0, -1.0), (0.0, -1.0), (0.0, -2.0), (-1.5, -2.0), (-1.5, 1.5))


def shoelace(corners):
    """area of a shape from its corners: half the sum of x1*y2 - x2*y1 over every side"""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(corners, corners[1:] + corners[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


with fcl.connect("sim", realtime=False) as u:
    u.page("survey")
    u.points(clear=True)
    for east, north in ROOM:
        ground = math.hypot(east, north)
        u.command("sim set heading %.1f" % (math.degrees(math.atan2(east, north)) % 360))
        u.command("sim set pitch %.1f" % -math.degrees(math.atan2(EYE, ground)))
        u.command("sim set dist %d" % round(1000 * math.hypot(ground, EYE)))
        u.wait(4)
        u.key("B2")
        u.wait(0.3)
    pts = u.points()
    print(fcl_survey.table(pts))
    true_area = shoelace(list(ROOM))
    ours = shoelace([(p["x"], p["y"]) for p in pts])
    print("\narea of the real room %.2f m2; from the unit's points %.2f m2; the unit's screen says: %s" % (true_area, ours, u.rows.get(8, "").strip()))
    out = os.path.join(HERE, "lesson5_plan.svg")
    open(out, "w", encoding="utf-8", newline="\n").write(fcl_survey.svg(pts))
    print("plan written to", out)
    sys.exit(0 if len(pts) == 6 and abs(ours - true_area) < 0.4 else 1)
