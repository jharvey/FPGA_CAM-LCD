#!/usr/bin/env python3
"""Test of the guided calibration (firmware/tools/fcl_calibrate.py): a simulated unit whose hardware has known
errors, a simulated user, and a check that the calibration finds every error and that the readings are right after.

    python firmware/sim/test_calibrate.py
Exit code 0 = all checks pass.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fcl_calibrate as fc      # noqa: E402

fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


link = fc.SimLink()
user = fc.DemoUser(link, quiet=True)
res, cal = fc.calibrate(link, user)
E = user.ERRORS
check(all(ok for _, ok, _ in res) and len(res) == 15, "all %d steps of the calibration succeed" % len(res))
check([t for n, ok, t in res if n.startswith("axes")] and all(ok for n, ok, _ in res if n.startswith("axes")),
      "axes: level, lens down, tipped right and a quarter turn all read the right way round")
check(abs(cal["pitch0"] - E["pitch"]) < 0.2 and abs(cal["roll0"] - E["roll"]) < 0.2,
      "level: mounting error found %+.2f / %+.2f deg (built in: %+.1f / %+.1f)" % (cal["pitch0"], cal["roll0"], E["pitch"], E["roll"]))
check(abs(cal["hfov"] - user.HFOV) < 0.5, "lens: %.1f deg across the screen (built in: %.0f)" % (cal["hfov"], user.HFOV))
check(abs(cal["dist0"] + E["dist"]) <= 2, "distance: offset %+.0f mm (built in: %+.0f)" % (cal["dist0"], E["dist"]))
check(abs(cal["cell1"] * E["cell1"] - 1) < 0.002 and abs(cal["cell2"] * E["cell2"] - 1) < 0.002 and abs(cal["cell3"] - 1) < 0.002,
      "cells: gains %.4f, %.4f, %.4f (built in: 1 / %.3f, 1 / %.3f, 1)" % (cal["cell1"], cal["cell2"], cal["cell3"], E["cell1"], E["cell2"]))
check(abs(cal["temp1"]) < 0.3 and abs(cal["temp2"] + E["temp2"]) < 0.3 and abs(cal["temp3"] + E["temp3"]) < 0.3,
      "temps: offsets %+.1f, %+.1f, %+.1f C (built in: 0, %+.1f, %+.1f)" % (cal["temp1"], cal["temp2"], cal["temp3"], E["temp2"], E["temp3"]))
check(abs(cal["head0"] - user.DECLINATION) < 1.5, "north: heading offset %+.1f deg (built in: %+.1f)" % (cal["head0"], user.DECLINATION))
m = [t for n, ok, t in res if n == "compass"][0]
off = [int(x) for x in m.split("offset ")[1].split(" mG")[0].split(",")]
want = [int(round(c * 1.5)) for c in user.HARD_IRON]
check(all(abs(a - b) <= 6 for a, b in zip(off, want)), "compass: hard-iron offset %s mG (built in: %s)" % (off, want))

# after the calibration the readings are right
user.pose(120, 10, -5, dist=1500)
t = fc.Unit(link).measure(2.0)
s = link.sim.world.s
check(abs(t["pitch"] - 10) < 0.4 and abs(t["roll"] + 5) < 0.4 and abs(fc.wrap180(t["heading"] - 120 - user.DECLINATION)) < 2.5,
      "afterwards: pitch %.1f, roll %.1f, heading %.1f (truth 10, -5, %.0f true)" % (t["pitch"], t["roll"], t["heading"], 120 + user.DECLINATION))
check(abs(t["dist_mm"] - 1500) <= 2 and abs(t["cell1_mv"] - s["cell1"] * 1000) < 6 and abs(t["temp2_c"] - s["temp2"]) < 0.3,
      "afterwards: distance %d mm, cell 1 %d mV, cell 2 at %.1f C (truth 1500, %d, %.1f)" % (
          t["dist_mm"], t["cell1_mv"], t["temp2_c"], s["cell1"] * 1000, s["temp2"]))

# a wrong measurement is refused, not stored
class Wrong(fc.DemoUser):
    def ask(self, key, text):
        return {"cell1": 2.0, "wall": 2.5}.get(key, fc.DemoUser.ask(self, key, text))


link2 = fc.SimLink()
res2, cal2 = fc.calibrate(link2, Wrong(link2, quiet=True), ("cells", "distance"))
bad = dict((n, ok) for n, ok, _ in res2)
check(bad["cell 1"] is False and bad["distance"] is False and cal2["cell1"] == 1 and cal2["dist0"] == 0 and bad["cell 2"] is True,
      "a meter reading 2.0 V on a 4 V cell and a wall 1.5 m further than measured are refused; nothing stored for them")
link.close()
link2.close()
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
