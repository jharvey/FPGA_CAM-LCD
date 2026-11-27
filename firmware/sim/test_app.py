#!/usr/bin/env python3
"""Tests of the layer above the drivers (firmware/esp32/fcl_app.py, fcl_cfg.py) through the simulator:
pages, the tools, the menu, calibration values, pan hold, logging, a page of your own.

    python firmware/sim/test_app.py
Exit code 0 = all checks pass.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcl_sim      # noqa: E402
import fcl_usb      # noqa: E402
import fcl_app      # noqa: E402

fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


class Rig:
    def __init__(self, **kw):
        self.sim = fcl_sim.Sim("bridge", **kw)
        self.seen = {}
        self.lcd = {}

    def go(self, seconds):
        for _ in range(int(round(seconds / fcl_sim.STEP_S))):
            for line in self.sim.step():
                r = fcl_usb.parse_line(line)
                if r:
                    self.seen.setdefault(r[0], []).append(r[1])
                    if r[0] == "L":
                        self.lcd[int(r[1][0])] = line.split(",", 2)[2]

    def cmd(self, *lines):
        for line in lines:
            self.sim.command(line)

    def row(self, n):
        return self.sim.state["osd"][n].strip()

    @property
    def t(self):
        return self.seen["T"][-1]


r = Rig()
r.cmd("sim buttons off", "sim set heading 100", "sim set pitch 0", "sim set roll 0", "sim set dist 2000")
r.go(3.0)

# ---- pages
r.cmd("key B1")
r.go(0.5)
check(r.t["mode"] == 1 and r.row(4) == "LEVEL" and r.row(5) == "== LEVEL ==" and ["B1"] in r.seen["E"],
      "key B1: page 1, LCD shows '%s' / '%s'" % (r.row(4), r.row(5)))
check(r.lcd.get(4, "").strip() == "LEVEL" and r.row(1) != "", "the page's rows are reported as $L lines; the heading row stays")
r.cmd("sim set pitch 10")
r.go(2.0)
check(r.row(5).startswith("UP 10.") or r.row(5).startswith("UP 9.9"), "level page at 10 deg up: '%s', '%s'" % (r.row(5), r.row(8)))
check(abs(float(r.row(8).split()[1].rstrip("%")) - 17.6) < 0.4, "slope shown as %s (17.6 %% for 10 deg)" % r.row(8).split()[1])

r.cmd("mode 2", "sim set pitch -20")
r.go(2.0)
check(r.row(4) == "HEIGHT" and r.row(5) == "AIM AT THE FOOT" and r.row(9) == "B2 = MARK", "height page: '%s', '%s'" % (r.row(5), r.row(9)))
r.cmd("key B2", "sim set pitch 25")
r.go(2.0)
live = r.row(5)
r.cmd("key B2")
r.go(0.5)
# foot 2.000 m away 20 deg down, top 25 deg up: 1.879 m off, 0.684 m below and 0.876 m above -> 1.560 m
h = float(r.row(5).split()[1].rstrip("m"))
said = [i[0] for i in r.seen["I"] if i[0].startswith("height")]
check(abs(h - 1.56) < 0.05 and live.startswith("H 1.") and r.row(8).startswith("AT 1.8") and said,
      "height from two sightings: %.2f m (1.56), '%s', reported '%s'" % (h, r.row(8), said[-1] if said else ""))
r.cmd("sim set dist 9000")
r.go(4.0)
r.cmd("key B2")
r.go(0.5)
check(r.row(5) == "AIM AT THE FOOT" and r.row(9) == "OUT OF RANGE", "foot out of the ranger's reach: '%s'" % r.row(9))

r.cmd("mode 3", "sim set pitch 0", "sim set dist 2000")
r.go(1.5)
r.cmd("key B2")
r.go(0.3)
r.cmd("sim set heading 70", "sim set alt 1.5")
r.go(4.0)
turn = r.row(5)
r.cmd("sim set heading 100")
r.go(2.0)
check(turn.startswith("TURN R") and abs(int(turn.split()[2]) - 30) <= 2 and r.row(5) == "ON MARK" and "+1." in r.row(8),
      "bearing page: 30 deg left of the mark '%s', back on it '%s', '%s'" % (turn, r.row(5), r.row(8)))

# ---- a page of your own
class Count(fcl_app.App):
    name = "COUNT"

    def __init__(self):
        self.n = 0

    def button(self, unit):
        self.n += 1

    def draw(self, unit, put):
        put(4, self.name)
        put(5, "%d PRESSES" % self.n)


n = r.sim.hubpy.apps.add(Count())
r.cmd("mode %d" % n, "key B2", "key B2")
r.go(0.5)
check(n == 5 and r.row(5) == "2 PRESSES", "a page added with apps.add(): page %d shows '%s'" % (n, r.row(5)))
r.cmd("key B1")
r.go(0.3)
check(r.t["mode"] == 0 and r.row(4) == "" and r.lcd.get(4) == "", "B1 on the last page: back to the overview, rows given back")

# ---- menu
m = r.sim.model
r.cmd("sim press B1 900")
r.go(1.2)
check(r.t["flags"] & 128 and r.row(3) == "MENU" and r.row(4).startswith("> View: camera") and ["B1_LONG"] in r.seen["E"]
      and r.t["mode"] == 0 and r.sim.state["dot"][2] == 0,
      "B1 held 0.9 s: menu open, '%s', page unchanged, dot hidden" % r.row(4))
check(m.aux & 8 and not m.edges, "the ESP32 owns B1 / B2: holding B1 did not switch the FPGA's view")
r.cmd("key B2")
r.go(0.5)
check(m.edges and r.t["flags"] & 64 and r.row(4).startswith("> View: edges"), "menu, View: video key pressed, LCD picture = edges")
r.cmd("key B1", "key B2", "key B2")
r.go(1.0)
check(m.threshold == 8 and r.row(5).startswith("> Edges +"), "menu, Edges + twice: threshold up by %d" % m.threshold)
r.cmd("key B1", "key B1", "key B2")
r.go(0.3)
check(r.t["overlay"] == 0x01 and "Overlay: dot" in r.row(7), "menu, Overlay: mask 0x%02X, '%s'" % (r.t["overlay"], r.row(7)))
r.cmd("key B2", "key B2", "key B1", "key B2")
r.go(0.3)
foll = r.sim.hubpy.follow_on
r.cmd("key B1", "key B1", "key B2")
r.go(0.5)
cal = r.sim.hubpy.cal.manual
r.cmd("key B2", "key B1", "key B2")
r.go(3.0)
wifi = [x for x in r.sim.state["osd"] if "WiFi" in x]
r.cmd("key B1", "key B2")
r.go(1.0)
check(r.t["overlay"] == 0x3F and not foll and cal and wifi and "192.168" in wifi[0] and r.t["flags"] & 256,
      "menu: overlay all, level servo off, compass calibration started, '%s', logging" % (wifi[0].strip() if wifi else ""))
r.cmd("key B1", "key B2")
r.go(0.3)
check(r.sim.hubpy.hud_mask == 1 and m.hud[0] == 0 and any("Graphics: reticle" in x for x in r.sim.state["osd"]),
      "menu, Graphics: reticle chosen; no graphics drawn while the menu is open")
r.cmd("key B1", "key B1", "key B2")
r.go(0.3)
check(not r.t["flags"] & 128 and r.row(3) != "MENU" and r.sim.state["dot"][2] == 1, "menu, Exit: closed, overlay and dot back")
check(m.hud[0] == 1 and ["1", "0", "0", "0", "0"] in r.seen["H"], "reticle on the overview after the menu closes; $H,1,0,0,0,0 sent")
r.cmd("hud off")

# ---- logging
r.go(2.0)
r.cmd("log off")
r.go(0.2)
log = r.sim.plat.log_lines
kinds = [fcl_usb.parse_line(x)[0] for x in log]
check(25 <= kinds.count("T") <= 40 and not r.t["flags"] & 256 and r.seen["R"][-1][1].startswith("log off"),
      "log: %d telemetry lines in about 3 s, every line readable; '%s'" % (kinds.count("T"), r.seen["R"][-1][1]))

# ---- calibration values
r.cmd("sim error cell1 1.03", "sim error temp2 4", "sim error dist 35", "sim error pitch 3")
r.go(4.0)
t0 = dict(r.t)
r.cmd("cal set cell1 %.5f" % (1 / 1.03), "cal set temp2 -4", "cal set dist0 -35", "cal set pitch0 3")
r.go(4.0)
t1 = r.t
truth = r.sim.world.s
check(abs(t0["cell1_mv"] - truth["cell1"] * 1030) < 8 and abs(t1["cell1_mv"] - truth["cell1"] * 1000) < 8,
      "cell 1 reading 3 %% high: %d mV, after cal set cell1: %d mV (truth %d)" % (t0["cell1_mv"], t1["cell1_mv"], truth["cell1"] * 1000))
check(abs(t0["temp2_c"] - 30) < 0.5 and abs(t1["temp2_c"] - 26) < 0.5 and t0["dist_mm"] == 2035 and t1["dist_mm"] == 2000,
      "temperature and distance offsets: %.1f -> %.1f C, %d -> %d mm" % (t0["temp2_c"], t1["temp2_c"], t0["dist_mm"], t1["dist_mm"]))
check(abs(t0["pitch"] - 3) < 0.5 and abs(t1["pitch"]) < 0.5, "sensor board mounted 3 deg off: pitch %.1f -> %.1f" % (t0["pitch"], t1["pitch"]))
r.cmd("sim set pitch -83", "cal set pitch0 0", "sim error pitch 0")
r.go(4.0)
y40 = r.t["dot_y"]
r.cmd("cal set hfov 60")
r.go(0.5)
check(abs(y40 - 81) <= 4 and abs(r.t["dot_y"] - 51) <= 4, "camera angle 40 -> 60 deg: down dot 7 deg off axis moves from %d to %d px (81, 51)" % (y40, r.t["dot_y"]))
r.cmd("cal set hfov 500", "cal set nothing 1", "cal")
r.go(0.2)
errs = [x[1] for x in r.seen["R"] if x[0] == "err"][-2:]
check("20..90" in errs[0] and "nothing" in errs[1] and r.seen["C"][-1][0] == "hfov=60", "bad values refused: '%s', '%s'" % tuple(errs))
r2 = Rig(cfg_store=r.sim.hubpy.cfg.store)
check(r2.sim.hubpy.cfg.get("hfov") == 60 and r2.sim.hubpy.cfg.get("temp2") == -4, "calibration values are stored and loaded at the next start")

# ---- pan hold
r.cmd("sim set pitch 0", "sim set heading 90", "pan 100")
r.go(3.0)
a = r.sim.state["servo"][1]
r.cmd("sim set heading 115")
r.go(2.0)
b = r.sim.state["servo"][1]
r.cmd("pan off")
r.go(0.2)
check(abs(a - 1600) <= 15 and abs(b - 1350) <= 15 and r.sim.state["servo"][1] == 0,
      "pan 100: servo 2 at %d us when heading 90 (1600), %d us at 115 (1350), off after pan off" % (a, b))

# ---- graphics drawn by the FPGA: reticle, horizon, compass tape
import math      # noqa: E402
r.cmd("mode 1", "sim set pitch 5", "sim set roll 20", "sim set heading 123")
r.go(3.0)
f, a, b, c, tape = m.hud
check(f == 3 and abs(a - 512 * math.sin(math.radians(20))) <= 6 and abs(b - 512 * math.cos(math.radians(20))) <= 6
      and abs(c + 4 * 5 * 480 / r.sim.hubpy.cfg.get("hfov")) <= 10,
      "Level page: reticle and horizon on; line a %d b %d c %d for roll 20, pitch 5" % (a, b, c))
r.cmd("sim set pitch 40")
r.go(2.5)
check(m.hud[0] == 1 and m.hud[1:4] == (0, 0, 0), "horizon switched off when it has left the picture (pitch 40)")
r.cmd("mode 3", "sim set pitch 0", "sim set roll 0")
r.go(2.5)
want = int(round(r.t["heading"] * 3.2)) & 31
check(m.hud[0] == 5 and (m.hud[4] - want + 16) % 32 - 16 in (-1, 0, 1), "Bearing page: reticle and compass tape, tape at %d for heading %.1f"
      % (m.hud[4], r.t["heading"]))
r.cmd("mode 0", "hud horizon tape")
r.go(0.5)
got = m.hud[0]
r.cmd("hud bogus", "hud")
r.go(0.3)
check(got == 6 and r.seen["R"][-2][0] == "err" and r.seen["R"][-1] == ["ok", "hud 6"] and any(h[0] == "6" for h in r.seen["H"]),
      "hud horizon tape: on every page; a wrong word is refused; $H line sent")
r.cmd("hud off")
r.go(0.5)
check(m.hud == (0, 0, 0, 0, 0), "hud off: nothing drawn on the overview")

# ---- Survey: the four corners of a room 3.0 m (east-west) by 2.4 m, the unit 1.2 m above the floor at its centre
r.cmd("mode 4", "points clear")
corners = ((1.5, 1.2), (1.5, -1.2), (-1.5, -1.2), (-1.5, 1.2))            # (east, north) of each corner, going round
for e, nn in corners:
    g = math.hypot(e, nn)
    r.cmd("sim set heading %.2f" % (math.degrees(math.atan2(e, nn)) % 360), "sim set pitch %.2f" % -math.degrees(math.atan2(1.2, g)),
          "sim set dist %d" % round(1000 * math.hypot(g, 1.2)))
    r.go(4.0)
    r.cmd("key B2")
    r.go(0.3)
sv = r.sim.hubpy.apps.survey
area, around = sv.area()
err = max(math.hypot(p[3] - c[0], p[4] - c[1]) for p, c in zip(sv.pts, corners)) if len(sv.pts) == 4 else 9
check(len(sv.pts) == 4 and err < 0.12 and abs(area - 7.2) < 0.3 and abs(around - 10.8) < 0.25 and all(abs(p[5] + 1.2) < 0.06 for p in sv.pts),
      "Survey: 4 corners within %.0f mm, area %.2f m2 (7.20), around %.2f m (10.80), floor %.2f m below" % (1000 * err, area, around, -sv.pts[0][5]))
check(len(r.seen.get("P", [])) == 4 and r.seen["P"][-1][0] == "4" and "AREA 7." in r.row(8) and r.row(4) == "SURVEY  4 PT",
      "Survey: $P line per point; LCD '%s' / '%s'" % (r.row(4), r.row(8)))
r.cmd("sim set dist 9000")
r.go(2.0)
r.cmd("key B2")
r.go(0.3)
r.cmd("points")
r.go(0.2)
check(len(sv.pts) == 4 and r.row(9) == "OUT OF RANGE" and len(r.seen["P"]) == 8 and r.seen["R"][-1] == ["ok", "points 4"],
      "Survey: no point when the ranger sees nothing; 'points' lists them again")
r.cmd("points clear", "sim set dist 2000", "mode 0")
r.go(0.3)
check(not sv.pts, "points clear")

# ---- the example of a page of your own (fcl_user_example.py), loaded as fcl_user.py would be on the unit
r3 = Rig(user="fcl_user_example")
r3.cmd("sim buttons off", "sim set alt 0", "mode 5")
r3.go(3.0)
first = r3.row(5)
r3.cmd("key B2", "sim set alt 2")
r3.go(6.0)
running = (r3.row(5), r3.row(8))
r3.cmd("key B2")
r3.go(0.5)
said = [i[0] for i in r3.seen["I"] if i[0].startswith("climb")]
check(first == "B2 = START" and running[0].startswith("+2.0m  0:0") and "m/min" in running[1] and said and r3.row(9) == "B2 = AGAIN",
      "example page CLIMB: '%s' -> '%s', '%s'; reported '%s'" % (first, running[0], running[1], said[-1] if said else ""))

print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
