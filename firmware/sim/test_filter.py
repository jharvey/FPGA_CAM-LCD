#!/usr/bin/env python3
"""Accuracy of the integer attitude filter (firmware/esp32/fcl_fix.py) through the whole bridge path.

Two runs, both with sensor noise and a gyro bias of about 0.5 deg/s:
  1. the motion the C hub was tested with: turning 18 deg/s while pitching +-20 deg and rolling +-10 deg
  2. the demo loop, which swings the lens to straight down and back
Also a long still period (drift), and that no value ever left the 32-bit range (array('i') would raise).

    python firmware/sim/test_filter.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcl_sim      # noqa: E402

fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


class Motion(fcl_sim.Scenario):
    """sim.c's scripted truth"""

    def at(self, t):
        u = 0.0 if t < 2 else (20.0 if t > 22 else t - 2)
        s = {"heading": 30.0 + 18.0 * u, "pitch": 20.0 * math.sin(2 * math.pi * u / 8.0),
             "roll": 10.0 * math.sin(2 * math.pi * u / 5.0), "alt": 0.0 if t < 10 else (3.0 if t > 14 else 3.0 * (t - 10) / 4.0),
             "dist": 1500.0, "cell1": 3.95, "cell2": 3.9, "cell3": 3.8, "temp1": 25.0, "temp2": 25.0, "temp3": 25.0}
        return s, 0


class Still(fcl_sim.Scenario):
    def at(self, t):
        s, _ = fcl_sim.Scenario.at(self, 0.0)
        s.update(heading=200.0, pitch=7.0, roll=-4.0)
        return s, 0


def run(scenario, seconds, t_from, t_to, skip=None):
    sim = fcl_sim.Sim("bridge")
    sim.scenario = scenario
    sim.world.sc = scenario
    e = [0.0, 0.0, 0.0]
    alt = 0.0
    while sim.t < seconds:
        sim.step()
        s = sim.world.s
        if t_from <= sim.t <= t_to and sim.last and not (skip and skip(s)):
            t = sim.last
            e[0] = max(e[0], abs(wrap(t["heading"] - s["heading"])))
            e[1] = max(e[1], abs(t["pitch"] - s["pitch"]))
            e[2] = max(e[2], abs(wrap(t["roll"] - s["roll"])))
        alt = sim.last.get("alt_m", 0.0) if sim.last else 0.0
    st = list(sim.hubpy.st)
    sim.close()
    return e, alt, st


e, alt, st = run(Motion(), 28.0, 4.0, 28.0)
check(e[0] < 5.0, "heading error while turning 18 deg/s and tilting: max %.2f deg (limit 5)" % e[0])
check(e[1] < 3.0 and e[2] < 3.0, "pitch / roll error: max %.2f / %.2f deg (limit 3)" % (e[1], e[2]))
check(abs(alt - 3.0) < 0.3, "height after a 3 m climb: %.2f m" % alt)
bias = [b / 65.5 for b in st[6:9]]
check(all(abs(b - x) < 0.1 for b, x in zip(bias, (0.4, -0.3, 0.5))), "gyro bias learned in the first second: %.2f %.2f %.2f deg/s (true 0.40 -0.30 0.50)" % tuple(bias))
n = math.sqrt(sum(float(v) * v for v in st[0:3])) / (1 << 28)
check(abs(n - 1.0) < 0.002, "up vector stays at unit length: %.5f" % n)

# near straight down, heading and roll are not defined (any roll gives the same view): leave those moments out
e, alt, st = run(fcl_sim.Scenario(), 60.0, 3.0, 60.0, skip=lambda s: s["pitch"] < -70.0)
check(e[0] < 6.0 and e[1] < 3.0 and e[2] < 4.0, "demo loop (swing to straight down and back): heading %.2f, pitch %.2f, roll %.2f deg max" % tuple(e))
e2, alt, st = run(fcl_sim.Scenario(), 22.0, 16.5, 19.5)
check(e2[1] < 3.5, "pitch while pointing straight down: within %.2f deg of the truth" % e2[1])

e, alt, st = run(Still(), 120.0, 5.0, 120.0)
check(max(e) < 1.0, "two minutes still: heading / pitch / roll stay within %.2f / %.2f / %.2f deg" % tuple(e))
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
