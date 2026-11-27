#!/usr/bin/env python3
"""Guided calibration of one unit, over the USB serial stream.  It asks you to do something, measures, and stores
the result on the unit (`cal set ...`, kept in cal.json).  Run it once on every new unit, and again after a change
to the mechanics.

    python firmware/tools/fcl_calibrate.py --port COM7            all steps (Linux: /dev/ttyACM0); needs pyserial
    python firmware/tools/fcl_calibrate.py --port COM7 level lens only these steps
    python firmware/tools/fcl_calibrate.py --sim --demo           the whole run in the simulator, with errors built
                                                                  into the simulated hardware and a simulated user

Steps   compass   the compass's hard-iron offset, pointing the unit in six directions; reports what is left over
        axes      are pitch, roll and heading the right way round?  (checks only: a wrong sign is a firmware fix)
        level     the unit on a level table: stores the mounting error of the sensor board (pitch0, roll0)
        lens      the camera's angle of view, for the down dot (hfov)
        distance  the ranger against a tape measure (dist0)
        cells     each cell against a multimeter (cell1..3)
        temps     the cell temperature sensors against the room temperature (temp1..3)
        north     the heading against a known bearing (head0: declination and mounting)

Enter on a question skips it.  Nothing is stored for a step whose measurement looks wrong.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "esp32"))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
import fcl_usb      # noqa: E402

STEPS = ("compass", "axes", "level", "lens", "distance", "cells", "temps", "north")


def wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


# ------------------------------------------------------------------ the unit
class SimLink:
    """the simulator, stepped as fast as it goes"""

    def __init__(self):
        import fcl_sim
        self.sim = fcl_sim.Sim("bridge")
        self.step_s = fcl_sim.STEP_S
        self.sim.command("sim buttons off")

    def send(self, line):
        self.sim.command(line)

    def read(self, seconds):
        out = []
        for _ in range(max(1, int(round(seconds / self.step_s)))):
            out += self.sim.step()
        return out

    def close(self):
        self.sim.close()


class PortLink:
    """serial port or TCP socket (host:port of a running fcl_sim.py)"""

    def __init__(self, port=None, tcp=None):
        if tcp:
            import socket
            host, p = tcp.rsplit(":", 1)
            s = socket.create_connection((host, int(p)))
            s.settimeout(0.05)

            def rd():
                try:
                    return s.recv(65536)
                except socket.timeout:
                    return b""
            self._rd, self._wr, self._close = rd, s.sendall, s.close
        else:
            import serial
            ser = serial.Serial(port, 115200, timeout=0.05)
            self._rd, self._wr, self._close = lambda: ser.read(4096), ser.write, ser.close
        self.buf = b""

    def send(self, line):
        self._wr((line + "\n").encode())

    def read(self, seconds):
        out = []
        end = time.time() + seconds
        while time.time() < end:
            self.buf += self._rd()
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                out.append(line.decode("utf-8", "replace").strip())
        return out

    def close(self):
        self._close()


class Unit:
    def __init__(self, link):
        self.link = link
        self.cal = {}
        self.mag = None
        self.replies = []

    def _take(self, lines):
        tele = []
        for line in lines:
            r = fcl_usb.parse_line(line)
            if not r:
                continue
            if r[0] == "T":
                tele.append(r[1])
            elif r[0] == "C":
                self.cal = dict((k, float(v)) for k, v in (x.split("=") for x in r[1]))
            elif r[0] == "M":
                self.mag = r[1]
            elif r[0] == "R":
                self.replies.append(r[1])
        return tele

    def command(self, line, wait=0.3):
        """-> True when the unit answered ok"""
        n = len(self.replies)
        self.link.send(line)
        self._take(self.link.read(wait))
        return any(r[0] == "ok" for r in self.replies[n:])

    def measure(self, seconds=2.0):
        """mean of the telemetry over this time -> dict (heading as a circular mean), or None without telemetry"""
        tele = self._take(self.link.read(seconds))
        if not tele:
            return None
        m = {}
        for k in fcl_usb.T_FIELDS:
            m[k] = sum(t[k] for t in tele) / float(len(tele))
        m["heading"] = math.degrees(math.atan2(sum(math.sin(math.radians(t["heading"])) for t in tele),
                                               sum(math.cos(math.radians(t["heading"])) for t in tele))) % 360.0
        m["dist_ok"] = all(t["flags"] & 8 for t in tele)
        m["flags"] = tele[-1]["flags"]
        return m

    def set(self, name, value):
        ok = self.command("cal set %s %.5g" % (name, value))
        return ok and abs(self.cal.get(name, 1e9) - value) < 1e-3 + 1e-4 * abs(value)


# ------------------------------------------------------------------ the person
class Console:
    def do(self, key, text):
        input("\n" + text + "\n  Press Enter when done. ")

    def ask(self, key, text):
        s = input("\n" + text + "\n  Value (Enter = skip): ").strip().replace(",", ".")
        try:
            return float(s) if s else None
        except ValueError:
            print("  not a number: skipped")
            return None

    def say(self, text):
        print(text)


class DemoUser:
    """A simulated person at a simulated unit whose hardware has known errors: for the demonstration and the test.
    What it 'measures with a multimeter' is the simulator's truth."""
    ERRORS = {"cell1": 1.03, "cell2": 0.985, "temp2": 4.0, "temp3": -2.5, "dist": 35.0, "pitch": 3.0, "roll": -2.0}
    HFOV, DECLINATION, HARD_IRON = 48.0, 5.0, (150, -100, 80)

    def __init__(self, link, quiet=False):
        self.link, self.quiet = link, quiet
        for k, v in self.ERRORS.items():
            link.send("sim error %s %g" % (k, v))
        link.send("sim hardiron %d %d %d" % self.HARD_IRON)
        for i in (1, 2, 3):                                  # a unit that has rested: all cells at room temperature
            link.send("sim set temp%d 24" % i)
        self.pose(0, 0, 0, dist=1000)
        self.mark_pitch = 0.0

    def pose(self, heading=None, pitch=None, roll=None, dist=None, wait=4.0):
        for k, v in (("heading", heading), ("pitch", pitch), ("roll", roll), ("dist", dist)):
            if v is not None:
                self.link.send("sim set %s %g" % (k, v))
        self.link.read(wait)

    def do(self, key, text):
        self.say("\n" + text + "\n  (simulated user: done)")
        if key in ("flat", "level", "aim_wall", "aim_bearing"):
            self.pose(40 if key == "aim_bearing" else 0, 0, 0)
        elif key == "down":
            self.pose(0, -90, 0)
        elif key == "roll_right":
            self.pose(0, 0, 45)
        elif key == "turn_right":
            self.pose(90, 0, 0)
        elif key == "mark_centre":
            self.pose(0, -10, 0)
        elif key == "mark_rim":
            self.pose(0, -10 + self.HFOV / 2, 0)          # the real lens puts the mark on the rim at half its angle
        elif key == "compass":
            for h, p in ((0, 85), (0, -85), (0, 0), (90, 0), (180, 0), (270, 0), (300, 40), (120, -40)):
                self.pose(h, p, 0, wait=3.5)
            self.pose(0, 0, 0)

    def ask(self, key, text):
        s = self.link.sim.world.s
        v = {"cell1": s["cell1"], "cell2": s["cell2"], "cell3": s["cell3"], "room": s["temp1"], "wall": 1.0,
             "bearing": 40.0 + self.DECLINATION}[key]
        self.say("\n" + text + "\n  (simulated user: %.3f)" % v)
        return v

    def say(self, text):
        if not self.quiet:
            print(text)


# ------------------------------------------------------------------ the steps: each returns [(name, ok, text)]
def step_axes(u, ui):
    out = []
    ui.do("flat", "AXES 1/4. Hold the unit level, lens pointing at the horizon, buttons on top.")
    m0 = u.measure()
    out.append(("axes: level", abs(m0["pitch"]) < 15 and abs(m0["roll"]) < 15, "pitch %+.1f, roll %+.1f (both near 0)" % (m0["pitch"], m0["roll"])))
    ui.do("down", "AXES 2/4. Point the lens straight down at the floor.")
    m = u.measure()
    out.append(("axes: lens down", m["pitch"] < -70, "pitch %+.1f (near -90%s)" % (m["pitch"], "; +90 means the pitch sign is reversed" if m["pitch"] > 70 else "")))
    ui.do("roll_right", "AXES 3/4. Level again, then tip the unit about 45 degrees to the right (clockwise, seen from behind).")
    m = u.measure()
    out.append(("axes: tipped right", 25 < m["roll"] < 65, "roll %+.1f (near +45%s)" % (m["roll"], "; negative means the roll sign is reversed" if m["roll"] < -25 else "")))
    ui.do("turn_right", "AXES 4/4. Level again, then turn a quarter turn to the right (clockwise, seen from above).")
    m = u.measure()
    d = wrap180(m["heading"] - m0["heading"])
    out.append(("axes: quarter turn right", 60 < d < 120, "heading changed by %+.0f (near +90%s)" % (d, "; negative means the heading runs the wrong way" if d < -60 else "")))
    return out


def step_level(u, ui):
    ui.do("level", "LEVEL. Put the unit on a table you know to be level, the way it will be used (lens at the horizon).")
    m = u.measure(3.0)
    p, r = m["pitch"] + u.cal.get("pitch0", 0.0), m["roll"] + u.cal.get("roll0", 0.0)
    if abs(p) > 15 or abs(r) > 15:
        return [("level", False, "pitch %+.1f, roll %+.1f: more than 15 degrees is not a mounting error; nothing stored" % (p, r))]
    ok = u.set("pitch0", p) and u.set("roll0", r)
    return [("level", ok, "sensor board sits %+.2f deg in pitch and %+.2f deg in roll; stored" % (p, r))]


def step_lens(u, ui):
    ui.do("mark_centre", "LENS 1/2. Aim so that a small, distant mark sits exactly in the centre of the screen. Keep the unit upright.")
    a = u.measure()
    ui.do("mark_rim", "LENS 2/2. Tilt the unit up slowly until the same mark just touches the bottom edge of the round screen.")
    b = u.measure()
    hfov = 2.0 * abs(b["pitch"] - a["pitch"])
    if not 20 <= hfov <= 90:
        return [("lens", False, "tilted %.1f deg: gives %.1f deg across the screen, outside 20..90; nothing stored" % (hfov / 2, hfov))]
    return [("lens", u.set("hfov", hfov), "the screen shows %.1f deg across; stored" % hfov)]


def step_distance(u, ui):
    ui.do("aim_wall", "DISTANCE. Aim at a plain wall, the front of the ranger window 1 to 3 m from it, at right angles.")
    true_m = ui.ask("wall", "Distance from the ranger window to the wall, in metres, with a tape measure.")
    if true_m is None:
        return [("distance", None, "skipped")]
    m = u.measure()
    if not m["dist_ok"]:
        return [("distance", False, "the ranger does not see the wall; nothing stored")]
    off = true_m * 1000.0 - (m["dist_mm"] - u.cal.get("dist0", 0.0))
    if abs(off) > 200:
        return [("distance", False, "off by %.0f mm: more than 200 mm is not an offset; nothing stored" % off)]
    return [("distance", u.set("dist0", round(off)), "ranger read %+.0f mm against the tape; stored" % -off)]


def step_cells(u, ui):
    out = []
    for i in (1, 2, 3):
        v = ui.ask("cell%d" % i, "CELLS. Voltage of cell %d in volts, with a multimeter across its holder contacts." % i)
        if v is None:
            out.append(("cell %d" % i, None, "skipped"))
            continue
        m = u.measure(1.5)
        raw = m["cell%d_mv" % i] / u.cal.get("cell%d" % i, 1.0)
        gain = v * 1000.0 / raw if raw > 500 else 0.0
        if not 0.9 <= gain <= 1.1:
            out.append(("cell %d" % i, False, "unit %d mV, meter %d mV: more than 10 %% apart, check the divider; nothing stored" % (raw, v * 1000)))
        else:
            out.append(("cell %d" % i, u.set("cell%d" % i, gain), "unit read %+.1f %% against the meter; stored" % ((1 / gain - 1) * 100)))
    return out


def step_temps(u, ui):
    room = ui.ask("room", "TEMPS. Room temperature in degrees C. The unit must have been off, or idle and cool, for 30 minutes.")
    if room is None:
        return [("temps", None, "skipped")]
    m = u.measure()
    out = []
    for i in (1, 2, 3):
        if m["soc%d" % i] == 255:
            out.append(("temp %d" % i, None, "no cell in this slot: skipped"))
            continue
        off = room - (m["temp%d_c" % i] - u.cal.get("temp%d" % i, 0.0))
        if abs(off) > 15:
            out.append(("temp %d" % i, False, "off by %.1f C: check the sensor; nothing stored" % off))
        else:
            out.append(("temp %d" % i, u.set("temp%d" % i, off), "sensor read %+.1f C against the room; stored" % -off))
    return out


def step_north(u, ui):
    ui.do("aim_bearing", "NORTH. Aim at a landmark whose true bearing you know (from a map), away from cars and steel.")
    true = ui.ask("bearing", "True bearing of the landmark, in degrees (0 = north, 90 = east).")
    if true is None:
        return [("north", None, "skipped")]
    m = u.measure(3.0)
    off = wrap180(true - (m["heading"] - u.cal.get("head0", 0.0)))
    return [("north", u.set("head0", off), "heading read %+.1f deg against the map; stored" % -off)]


def step_compass(u, ui):
    u.command("magcal start")
    ui.do("compass", "COMPASS. Away from steel: point the lens up, down, and level to north, east, south and west,\n"
                     "about two seconds each, any order. Then two more directions of your choice.")
    u.command("magcal", 1.0)
    if u.mag and u.mag[0] == "manual-running":
        u.command("magcal stop", 1.0)
    m = u.mag
    if not m or m[0] not in ("manual", "auto", "stored"):
        return [("compass", False, "no calibration came out of this (state %s): turn the unit further and repeat" % (m[0] if m else "unknown"))]
    err = float(m[5])
    text = "offset %s, %s, %s mG, field %s mG, left over %.1f %% of the field" % (m[1], m[2], m[3], m[4], err)
    text += " (rough guide: 1 % is 1 to 2 degrees of heading)."
    if err > 4:
        text += " That is a lot: steel nearby, or the unit's own parts bend the field (soft iron, not corrected)."
    return [("compass", err <= 8, text)]


RUN = {"axes": step_axes, "level": step_level, "lens": step_lens, "distance": step_distance, "cells": step_cells,
       "temps": step_temps, "north": step_north, "compass": step_compass}


def calibrate(link, ui, steps=STEPS):
    """-> ([(name, ok or None, text)], final calibration values)"""
    u = Unit(link)
    link.read(1.0)
    if not u.command("cal", 1.0) or not u.cal:
        return [("link", False, "the unit does not answer the `cal` command: wrong port, or older firmware")], {}
    if u.measure(1.0) is None:
        return [("link", False, "no telemetry: send `stream on`")], {}
    res = []
    for s in steps:
        res += RUN[s](u, ui)
    u.command("cal")
    return res, dict(u.cal)


def report(res, cal):
    out = ["", "RESULT"]
    for name, ok, text in res:
        out.append("  %-5s %-26s %s" % ("skip" if ok is None else ("ok" if ok else "FAIL"), name, text))
    if cal:
        out.append("")
        out.append("Stored on the unit: " + ", ".join("%s=%g" % kv for kv in sorted(cal.items())))
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--port")
    g.add_argument("--tcp")
    g.add_argument("--sim", action="store_true")
    ap.add_argument("--demo", action="store_true", help="with --sim: a simulated user at simulated hardware with known errors")
    ap.add_argument("steps", nargs="*", help="steps to run, in this order (default: all)")
    a = ap.parse_args()
    for s in a.steps:
        if s not in STEPS:
            ap.error("unknown step %s (steps: %s)" % (s, " ".join(STEPS)))
    if a.sim and not a.demo:
        ap.error("--sim needs --demo: the simulator has no hands (for a real unit use --port)")
    link = SimLink() if a.sim else PortLink(a.port, a.tcp)
    try:
        res, cal = calibrate(link, DemoUser(link) if a.sim else Console(), tuple(a.steps) or STEPS)
    finally:
        link.close()
    print("\n".join(report(res, cal)))
    sys.exit(0 if all(ok is not False for _, ok, _ in res) else 1)
