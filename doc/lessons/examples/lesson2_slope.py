"""Lesson 2: angles and slopes.

A ramp that climbs 1 m over 10 m along the ground has a slope of 10 %.  The unit measures the angle; the slope
is the tangent of the angle.  This script lays the unit on five ramps and compares its Level page with the sum.

    python doc/lessons/examples/lesson2_slope.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "firmware", "tools"))
import fcl      # noqa: E402

with fcl.connect("sim", realtime=False) as u:
    u.page("level")
    ok = True
    print("ramp: up per 10 m   angle (worked out)   unit's pitch   slope (worked out)   the Level page says")
    for rise in (0.0, 0.5, 1.0, 2.0, 5.0):
        angle = math.degrees(math.atan2(rise, 10.0))
        u.command("sim set pitch %.2f" % angle)
        u.wait(4)
        slope = 100.0 * rise / 10.0
        page = u.rows.get(8, "").strip()                 # row 8 of the LCD: "SLOPE +10.0%"
        print("     %4.1f m           %5.2f deg            %5.2f deg        %5.1f %%               %s" % (rise, angle, u.pitch, slope, page))
        shown = float(page.replace("SLOPE", "").replace("%", "")) if page.startswith("SLOPE") else 999
        ok = ok and abs(shown - slope) < 1.0
    print("\nA wheelchair ramp may be at most about 8 %% (1 in 12): that is only %.1f degrees." % math.degrees(math.atan(1 / 12.0)))
    sys.exit(0 if ok else 1)
