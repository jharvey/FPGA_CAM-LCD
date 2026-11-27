#!/usr/bin/env python3
"""Compass calibration (firmware/esp32/fcl_magcal.py) through the simulator, with a hard-iron field added.

    python firmware/sim/test_magcal.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcl_sim      # noqa: E402

fail = 0
IRON = (150.0, -100.0, 80.0)        # counts: 225, -150, 120 mG, about half the earth's field


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


class Pan(fcl_sim.Scenario):
    """a level pan: two turns at 20 deg/s, small tilts only"""

    def at(self, t):
        s, _ = fcl_sim.Scenario.at(self, 0.0)
        s.update(heading=10.0 + 20.0 * t, pitch=3.0 * math.sin(t / 3.0), roll=2.0 * math.sin(t / 2.0))
        return s, 0


class Tumble(fcl_sim.Scenario):
    """turned by hand to point every way"""

    def at(self, t):
        s, _ = fcl_sim.Scenario.at(self, 0.0)
        s.update(heading=40.0 * t, pitch=80.0 * math.sin(2 * math.pi * t / 11.0), roll=60.0 * math.sin(2 * math.pi * t / 7.0))
        return s, 0


def run(scenario, seconds, iron=IRON, store=None, commands=(), window=None, skip=None):
    sim = fcl_sim.Sim("bridge", store=store)
    sim.scenario = scenario
    sim.world.sc = scenario
    sim.world.hardiron = list(iron)
    todo = sorted(commands)
    lines = []
    err_early = err_late = 0.0
    while sim.t < seconds:
        while todo and todo[0][0] <= sim.t:
            sim.command(todo.pop(0)[1])
        lines += [x for x in sim.step() if x.startswith(("$M", "$R"))]
        if sim.last and not (skip and skip(sim.world.s)):
            e = abs(wrap(sim.last["heading"] - sim.world.s["heading"]))
            if 3.0 < sim.t < 8.0:
                err_early = max(err_early, e)
            if window and window[0] <= sim.t <= window[1]:
                err_late = max(err_late, e)
    return sim, lines, err_early, err_late


down = lambda s: s["pitch"] < -70.0 or s["pitch"] > 70.0      # heading is not defined looking straight up or down

sim, lines, e0, e1 = run(fcl_sim.Scenario(), 90.0, window=(60.0, 90.0), skip=down)
off = sim.hubpy.cal.off
check(e0 > 10.0, "uncalibrated, with a hard-iron field of half the earth's: heading up to %.0f deg wrong" % e0)
check(sim.hubpy.cal.state == "auto" and e1 < 4.0, "automatic, demo loop: after a minute the heading is within %.1f deg" % e1)
check(all(abs(o - i) < 20 for o, i in zip(off, IRON)), "offset found %.0f %.0f %.0f counts (true %.0f %.0f %.0f)" % (tuple(off) + IRON))

sim, lines, e0, e1 = run(Pan(), 60.0, window=(40.0, 60.0))
off = sim.hubpy.cal.off
check(e1 < 4.0, "automatic, level pan only: heading within %.1f deg after two turns (was up to %.0f)" % (e1, e0))
check(abs(off[0] - IRON[0]) < 15 and abs(off[1] - IRON[1]) < 15 and abs(off[2]) < 40,
      "level pan: the offset across the pan is found (%.0f %.0f); the vertical part is left alone (%.0f, not seen)" % tuple(off))

store = fcl_sim.MemStore()
sim, lines, e0, e1 = run(Tumble(), 45.0, store=store, commands=[(1.0, "magcal auto off"), (2.0, "magcal start")], window=(35.0, 45.0), skip=down)
off = sim.hubpy.cal.off
done = [x for x in lines if x.startswith("$M,manual,")]
prog = [x for x in lines if x.startswith("$M,manual-running")]
check(len(prog) >= 3 and done and sim.hubpy.cal.state == "manual", "manual: progress lines while turning, then finished by itself: %s" % (done[0] if done else "-"))
check(all(abs(o - i) < 8 for o, i in zip(off, IRON)) and e1 < 3.0,
      "manual: offset %.0f %.0f %.0f counts (true %.0f %.0f %.0f), heading within %.1f deg" % (tuple(off) + IRON + (e1,)))
check(store.d and all(abs(a - b) < 0.1 for a, b in zip(store.d["off"], off)), "calibration stored: %s" % store.d)

sim, lines, e0, e1 = run(Pan(), 12.0, store=store, window=(3.0, 12.0))
check(sim.hubpy.cal.state in ("stored", "auto") and max(e0, e1) < 4.0,
      "after a restart the stored calibration is used at once: heading within %.1f deg from the start" % max(e0, e1))

sim, lines, e0, e1 = run(fcl_sim.Scenario(), 90.0, iron=(0, 0, 0), window=(5.0, 90.0), skip=down)
off = sim.hubpy.cal.off
check(e1 < 4.0 and all(abs(o) < 15 for o in off), "no hard iron: automatic calibration leaves it alone (offset %.0f %.0f %.0f, heading within %.1f deg)" % (tuple(off) + (e1,)))

sim, lines, e0, e1 = run(Pan(), 20.0, commands=[(1.0, "magcal auto off"), (15.0, "magcal reset"), (16.0, "magcal bogus")])
check(sim.hubpy.cal.state == "none" and any("$R,err" in x for x in lines) and any(x.endswith(",fixed") for x in lines),
      "magcal auto off stops the automatic fit; reset clears it; a bad argument is refused")
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
