"""Lesson 3: how tall is it?  Measuring a height without climbing.

Stand some way from a door.  Aim at its foot: the ranger gives the distance along the line of sight, the unit its
angle below level.  Tilt up to the top: only the angle is needed now.

    foot:  along the ground  g = d * cos(a1)        below the unit  b = d * sin(a1)      (a1 is negative: looking down)
    top:   above the unit    t = g * tan(a2)
    height = t - b

    python doc/lessons/examples/lesson3_height.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "firmware", "tools"))
import fcl      # noqa: E402

DOOR, AWAY, EYE = 2.05, 2.5, 1.4          # the door's height, how far away we stand, how high we hold the unit (metres)

with fcl.connect("sim", realtime=False) as u:
    u.page("height")
    a1 = -math.degrees(math.atan2(EYE, AWAY))                    # angle down to the foot
    d = math.hypot(AWAY, EYE)                                    # what the ranger reads there
    a2 = math.degrees(math.atan2(DOOR - EYE, AWAY))              # angle up to the top
    u.command("sim set pitch %.2f" % a1)
    u.command("sim set dist %d" % round(d * 1000))
    u.wait(4)
    print("at the foot: the unit reads pitch %.1f deg, distance %.2f m" % (u.pitch, u.distance))
    g, b = u.distance * math.cos(math.radians(u.pitch)), u.distance * math.sin(math.radians(u.pitch))
    print("             along the ground %.2f m, the foot is %.2f m below the unit" % (g, -b))
    u.key("B2")
    u.command("sim set pitch %.2f" % a2)
    u.wait(4)
    t = g * math.tan(math.radians(u.pitch))
    print("at the top:  the unit reads pitch %.1f deg, so the top is %.2f m above the unit" % (u.pitch, t))
    u.key("B2")
    u.wait(0.5)
    ours = t - b
    said = [x for x in u.info if x.startswith("height")]
    theirs = float(said[-1].split()[1]) if said else -1
    print("\nworked out here: %.2f m     the unit says: %s     the door really is %.2f m" % (ours, said[-1] if said else "nothing", DOOR))
    sys.exit(0 if abs(ours - DOOR) < 0.05 and abs(theirs - DOOR) < 0.05 else 1)
