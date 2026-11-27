"""Lesson 1: what the unit knows about itself.

Turn and tilt the (simulated) unit and read its sensors from Python.

    python doc/lessons/examples/lesson1_readings.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "firmware", "tools"))
import fcl      # noqa: E402

POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

with fcl.connect("sim", realtime=False) as u:
    print("facing  compass says  that is  tilted  pitch says  wall at  ranger says")
    ok = True
    for heading, pitch, wall_mm in ((0, 0, 1000), (90, 10, 1500), (180, -20, 2500), (270, 45, 3500), (315, 0, 6000)):
        u.command("sim set heading %d" % heading)       # in the simulator we hold the unit by typing
        u.command("sim set pitch %d" % pitch)
        u.command("sim set dist %d" % wall_mm)
        u.wait(4)                                       # give the hand time to get there, as a real hand needs
        point = POINTS[int((u.heading + 22.5) // 45) % 8]
        seen = "%.2f m" % u.distance if u.distance is not None else "nothing"
        print("%5d   %9.1f     %-3s     %5d   %8.1f    %.1f m    %s" % (heading, u.heading, point, pitch, u.pitch, wall_mm / 1000.0, seen))
        ok = ok and abs((u.heading - heading + 180) % 360 - 180) < 3 and abs(u.pitch - pitch) < 1
        ok = ok and ((u.distance is None) if wall_mm > 4000 else abs(u.distance - wall_mm / 1000.0) < 0.05)
    print("\nThe last wall is 6 m away: further than the ranger reaches, so it sees nothing.")
    print("cells:", ", ".join("%.2f V (%s %%)" % (v, p) for v, p, t in u.cells))
    sys.exit(0 if ok else 1)
