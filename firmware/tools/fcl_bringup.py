#!/usr/bin/env python3
"""The first board's stage 9 (doc/BRINGUP.md), step by step: it tells you what to do, reads the unit over USB,
decides pass or fail, and writes a report with every measured value.

    python firmware/tools/fcl_bringup.py --port COM7 --board 1          (Linux: /dev/ttyACM0); needs pyserial
    python firmware/tools/fcl_bringup.py --port COM7 cells buttons      only these checks
    python firmware/tools/fcl_bringup.py --sim --demo                   the whole run in the simulator, with a simulated person

Before it: stages 0 to 8 by hand, then the full bitstream loaded (9.4) and the ESP32 running the FCL files.
You need a multimeter, and for the servo check a servo on J_SRV1.  Questions: y = yes, n = no, Enter = skip.

The report (bringup_board<N>_<date>.md) is the first article's record: keep it with the board, and use the first good
board's values as the golden values of doc/PRODUCTION_TEST.md.

Checks   link      the stream: version, telemetry rate, all five sensors answer
         readings  pressure, temperatures and cell voltages plausible; cells against a multimeter
         attitude  level on a table; the lens pointing down
         distance  the ranger sees your hand at about 30 cm, and nothing when aimed at the sky or far away
         buttons   B1, B2 and a short PWR press reach the ESP32 (it reads them through the FPGA)
         screen    text, graphics and the edge view on the round TFT (you look)
         pages     the Level page writes its rows; back to the Overview
         servo     a 1.5 ms pulse on servo 1 (you look, if a servo is fitted)
         audio     a tone from the speaker (you listen)
         log       a log file written on the unit
         wifi      connected; the phone page opens (you look; skipped when Wi-Fi is not set up)
"""
import datetime
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcl_calibrate as fc      # noqa: E402    (the links to the unit, the Unit class and the console are shared)
import fcl_usb                  # noqa: E402

CHECKS = ("link", "readings", "attitude", "distance", "buttons", "screen", "pages", "servo", "audio", "log", "wifi")


class Unit(fc.Unit):
    """the calibration tool's unit, also keeping button lines, events, LCD rows, info and Wi-Fi lines"""

    def __init__(self, link):
        fc.Unit.__init__(self, link)
        self.buttons, self.rows, self.info, self.wifi, self.tele = [], {}, [], None, []

    def _take(self, lines):
        for line in lines:
            r = fcl_usb.parse_line(line)
            if not r:
                continue
            k, v = r
            if k == "B" and len(v) >= 2 and v[1] == "1":
                self.buttons.append(v[0])
            elif k == "E":
                self.buttons.append("E:" + v[0])
            elif k == "L":
                text = line.split(",", 2)[2] if line.count(",") >= 2 else ""
                if text.strip():
                    self.rows[int(v[0])] = text.strip()
                else:
                    self.rows.pop(int(v[0]), None)
            elif k == "I":
                self.info.append(v[0])
            elif k == "W":
                self.wifi = v
        tele = fc.Unit._take(self, lines)
        self.tele += tele
        return tele

    def reply(self, line, wait=0.5):
        """send a command -> (ok, the reply text)"""
        n = len(self.replies)
        self.link.send(line)
        self._take(self.link.read(wait))
        new = self.replies[n:]
        return (bool(new) and new[-1][0] == "ok"), (new[-1][1] if new and len(new[-1]) > 1 else "")


class Person(fc.Console):
    def yes(self, key, text):
        s = input("\n" + text + "  [y / n / Enter = skip] ").strip().lower()
        return True if s.startswith("y") else False if s.startswith("n") else None


class DemoPerson(fc.DemoUser):
    """a simulated person at a simulated unit: does what is asked, and says yes only to what the simulator shows"""
    ERRORS = {}

    def __init__(self, link, quiet=False):
        fc.DemoUser.__init__(self, link, quiet)
        self.pose(0, 0, 0, dist=3000)

    def do(self, key, text):
        self.say("\n" + text + "\n  (simulated person: done)")
        s = self.link
        if key == "flat":
            self.pose(0, 0, 0)
        elif key == "down":
            self.pose(0, -88, 0)
        elif key == "hand":
            self.pose(0, 0, 0, dist=300)
        elif key == "far":
            self.pose(0, 0, 0, dist=9000)
        elif key in ("B1", "B2", "PWR"):
            s.send("sim press %s 300" % key)             # the check reads what follows

    def yes(self, key, text):
        m = self.link.sim.model
        st = self.link.sim.state
        v = {"graphics": m.hud[0] == 7, "edges": m.edges, "camera": not m.edges,
             "text": any(r.strip() for r in st["osd"]),
             "servo": st["servo"][0] == 1500, "tone": bool(self.link.sim.plat.tone_log),
             "phone": self.link.sim.plat.wifi[0] == "connected"}.get(key)
        self.say("\n" + text + "\n  (simulated person: %s)" % {True: "yes", False: "no", None: "skip"}[v])
        return v


def r(name, ok, measured, expected=""):
    return (name, ok, measured, expected)


# ------------------------------------------------------------------ the checks: each returns [(name, ok, measured, expected)]
def check_link(u, ui):
    u.info[:] = []
    ok, _ = u.reply("status", 1.0)
    ver = [x for x in u.info if x.startswith("FCL USB")]
    u.tele[:] = []
    m = u.measure(3.0)
    n = len(u.tele)
    sensors = int(u.tele[-1]["sensors"]) if u.tele else 0
    names = [nm for i, nm in enumerate(("IMU", "compass", "barometer", "ranger", "ADC")) if not sensors >> i & 1]
    return [r("link: answers", ok and bool(ver), ver[-1] if ver else "no reply to `status`", "FCL USB protocol 1"),
            r("link: telemetry", m is not None and 25 <= n <= 35, "%d lines in 3 s" % n, "about 30 (10 per second)"),
            r("link: sensors", sensors == 0x1F, "0x%02X%s" % (sensors, " (missing: %s)" % ", ".join(names) if names else ""), "0x1F: all five")]


def check_readings(u, ui):
    m = u.measure(2.0)
    out = [r("readings: pressure", 870 <= m["press_hpa"] <= 1085, "%.1f hPa" % m["press_hpa"], "870-1085 hPa (sea level to about 1300 m)")]
    for i in (1, 2, 3):
        t = m["temp%d_c" % i]
        out.append(r("readings: cell %d temperature" % i, 5 <= t <= 45, "%.1f C" % t, "near the room's, 5-45 C"))
    ui.do("multimeter", "CELLS. Measure each cell's voltage with a multimeter, at the cell's contacts, unit switched on.")
    for i in (1, 2, 3):
        mv = m["cell%d_mv" % i]
        meter = ui.ask("cell%d" % i, "Cell %d on the multimeter, in volts (the unit reads %.3f V):" % (i, mv / 1000.0))
        if meter is None:
            out.append(r("readings: cell %d" % i, None, "%.3f V on the unit" % (mv / 1000.0), "within 2 % of a multimeter"))
        else:
            err = 100.0 * (mv / 1000.0 - meter) / meter if meter else 100.0
            out.append(r("readings: cell %d" % i, abs(err) <= 2.0, "unit %.3f V, meter %.3f V (%+.1f %%)" % (mv / 1000.0, meter, err),
                         "within 2 % (the calibration's `cells` step removes the rest)"))
    return out


def check_attitude(u, ui):
    ui.do("flat", "ATTITUDE 1/2. Put the unit on a table, lens at the horizon, buttons on top.")
    m = u.measure(2.0)
    out = [r("attitude: on a table", abs(m["pitch"]) < 10 and abs(m["roll"]) < 10, "pitch %+.1f, roll %+.1f" % (m["pitch"], m["roll"]),
             "both within 10 degrees (before calibration)")]
    ui.do("down", "ATTITUDE 2/2. Point the lens straight down at the floor.")
    m = u.measure(2.0)
    out.append(r("attitude: lens down", m["pitch"] < -70, "pitch %+.1f" % m["pitch"], "near -90 (+90: a sign is reversed)"))
    return out


def check_distance(u, ui):
    ui.do("hand", "DISTANCE 1/2. Lens at the horizon; hold your flat hand about 30 cm in front of the ranger, still.")
    m = u.measure(2.0)
    out = [r("distance: hand at 30 cm", m["dist_ok"] and 150 <= m["dist_mm"] <= 450,
             "%.0f mm" % m["dist_mm"] if m["dist_ok"] else "nothing seen", "150-450 mm")]
    ui.do("far", "DISTANCE 2/2. Aim at the sky, or across a room more than 5 m wide.")
    m = u.measure(2.0)
    out.append(r("distance: nothing in reach", not m["dist_ok"], "nothing seen" if not m["dist_ok"] else "%.0f mm" % m["dist_mm"],
                 "nothing seen (the ranger reaches about 4 m)"))
    return out


def check_buttons(u, ui):
    out = []
    for key, how in (("B1", "Press B1 once, briefly (the page changes)."), ("B2", "Press B2 once, briefly."),
                     ("PWR", "Press the power button once, briefly (under a second: longer switches the unit off).")):
        u.buttons[:] = []
        ui.do(key, "BUTTONS. " + how)
        u._take(u.link.read(1.5))
        seen = [b for b in u.buttons if b == key]
        out.append(r("buttons: " + key, bool(seen), "reported" if seen else "nothing reported", "a $B line"))
    u.reply("mode 0")
    return out


def check_screen(u, ui):
    u.reply("mode 0")
    u.reply("hud all", 1.0)
    out = [r("screen: text", ui.yes("text", "SCREEN 1/3. Is the camera picture on the round screen, with the heading at the "
                                     "top and the cell charges near the bottom?"), "", "picture and text"),
           r("screen: graphics", ui.yes("graphics", "SCREEN 2/3. Do you see a cross at the centre, a line along the "
                                         "horizon, and ticks at the top that slide when you turn the unit?"), "", "all three")]
    u.reply("view edges", 1.0)
    out.append(r("screen: edge view", ui.yes("edges", "SCREEN 3/3. Is the picture now black with white outlines of "
                                             "what the camera sees?"), "", "white edges on black"))
    u.reply("view camera", 1.0)
    u.reply("hud off")
    return out


def check_pages(u, ui):
    u.rows.clear()
    u.reply("mode 1", 0.8)
    level = u.rows.get(4, "")
    u.reply("mode 0", 0.8)
    return [r("pages: Level", level == "LEVEL", "row 4: %r" % level, "'LEVEL'"),
            r("pages: back to the Overview", 4 not in u.rows, "row 4 given back" if 4 not in u.rows else "row 4 still %r" % u.rows[4], "")]


def check_servo(u, ui):
    ok, _ = u.reply("servo 1 1500")
    seen = ui.yes("servo", "SERVO. If a servo is plugged into J_SRV1: does it move to its middle position and hold "
                           "it? (Enter if none is fitted; a scope on pin 1 shows a 1.5 ms pulse every 20 ms.)")
    u.reply("servo 1 off")
    return [r("servo: 1 at 1500 us", ok and seen is not False and (True if seen else None), "", "the servo holds its middle")]


def check_audio(u, ui):
    ok, _ = u.reply("tone 880 400", 0.8)
    heard = ui.yes("tone", "AUDIO. Did the speaker play a short high tone just now?")
    return [r("audio: tone", ok and heard if heard is not None else None, "", "a short 880 Hz tone")]


def check_log(u, ui):
    ok, _ = u.reply("log on", 0.5)
    u.link.read(3.0)
    ok2, text = u.reply("log off", 0.5)
    words = text.split()                                 # the unit: "fcl001.log 4321 bytes" (the simulator: "35 lines")
    n = int(words[-2]) if len(words) >= 2 and words[-2].isdigit() else -1
    big = n > 500 if words[-1:] == ["bytes"] else n >= 20
    return [r("log: written", ok and ok2 and big, text or "no reply", "a file of some kilobytes after 3 s")]


def check_wifi(u, ui):
    u.reply("wifi", 1.0)
    st = u.wifi or ["off"]
    if st[0] != "connected":
        return [r("wifi", None, "state: %s" % st[0], "skipped: set it up with `wifi <name> <password>` and run this check again")]
    seen = ui.yes("phone", "WI-FI. Open http://%s/ on a phone on the same network. Does the page show live readings?" % st[2])
    return [r("wifi: connected", True, "%s, %s, %s dBm" % (st[1], st[2], st[3]), ""),
            r("wifi: phone page", seen, "", "the page with live readings")]


RUN = dict((c, globals()["check_" + c]) for c in CHECKS)


def bringup(link, ui, checks=CHECKS):
    u = Unit(link)
    link.read(1.0)
    if u.measure(1.0) is None:
        return [r("link", False, "no telemetry", "the FCL stream on the USB port (is the unit at the Python prompt? `import fcl_usbdev; fcl_usbdev.run()`)")], u
    res = []
    for c in checks:
        try:
            res += RUN[c](u, ui)
        except (KeyError, TypeError, ValueError) as e:            # a reading that never came
            res.append(r(c, False, "no reading: %s" % e, ""))
    return res, u


def report(res, u, board, port):
    now = datetime.datetime.now()
    ver = [x for x in u.info if x.startswith("FCL USB")]
    out = ["# Bring-up stage 9, board %s" % board, "",
           "%s, %s, %s. Written by `firmware/tools/fcl_bringup.py`." % (now.strftime("%Y-%m-%d %H:%M"), port, ver[-1] if ver else "version not read"), "",
           "| Check | Result | Measured | Expected |", "|---|---|---|---|"]
    for name, ok, measured, expected in res:
        out.append("| %s | %s | %s | %s |" % (name, "skipped" if ok is None else "pass" if ok else "**FAIL**", measured, expected))
    n_fail = sum(1 for x in res if x[1] is False)
    n_skip = sum(1 for x in res if x[1] is None)
    out += ["", "%d checks: %d passed, %d failed, %d skipped." % (len(res), len(res) - n_fail - n_skip, n_fail, n_skip)]
    if n_fail:
        out.append("Look up each failure in doc/TROUBLESHOOTING.md, and note it in ROADMAP.md with the board number.")
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--port")
    g.add_argument("--tcp")
    g.add_argument("--sim", action="store_true")
    ap.add_argument("--demo", action="store_true", help="with --sim: a simulated person")
    ap.add_argument("--board", default="1", help="the board's number, for the report")
    ap.add_argument("--out", help="report file (default bringup_board<N>_<date>.md)")
    ap.add_argument("checks", nargs="*", help="checks to run (default: all): " + " ".join(CHECKS))
    a = ap.parse_args()
    for c in a.checks:
        if c not in CHECKS:
            ap.error("unknown check %s" % c)
    if a.sim and not a.demo:
        ap.error("--sim needs --demo: the simulator has no hands")
    link = fc.SimLink() if a.sim else fc.PortLink(a.port, a.tcp)
    try:
        res, u = bringup(link, DemoPerson(link) if a.sim else Person(), tuple(a.checks) or CHECKS)
    finally:
        link.close()
    text = report(res, u, a.board, "simulator" if a.sim else (a.port or a.tcp))
    path = a.out or "bringup_board%s_%s.md" % (a.board, datetime.date.today().isoformat())
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(text) + "\n")
    print("\n".join(text[4:]))
    print("\nreport written to", path)
    return 1 if any(x[1] is False for x in res) else 0


if __name__ == "__main__":
    sys.exit(main())
