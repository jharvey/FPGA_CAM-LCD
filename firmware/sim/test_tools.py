#!/usr/bin/env python3
"""Tests of the PC tools above the USB protocol: fcl.py (scripting), fcl_survey.py (plan of a survey),
fcl_update.py (new software over Wi-Fi) and fcl_bringup.py (the first board's stage 9), all against the simulator.

    python firmware/sim/test_tools.py
Exit code 0 = all checks pass.
"""
import math
import os
import shutil
import socket
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fcl              # noqa: E402
import fcl_survey       # noqa: E402
import fcl_update       # noqa: E402
import fcl_sim          # noqa: E402
import fcl_web          # noqa: E402

fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


# ---------------------------------------------------------------- fcl.py
u = fcl.connect("sim", realtime=False)
u.command("sim set heading 100")
u.command("sim set pitch 2")
u.command("sim set roll -3")
u.command("sim set dist 1500")
t0 = time.time()
u.wait(4)
check(abs(u.heading - 100) < 2 and abs(u.pitch - 2) < 0.5 and abs(u.roll + 3) < 0.5 and abs(u.distance - 1.5) < 0.02 and u.frames >= 35
      and time.time() - t0 < 3, "fcl.connect('sim', realtime=False): 4 s of the unit in %.1f s; heading %.1f pitch %.1f roll %.1f distance %.2f m"
      % (time.time() - t0, u.heading, u.pitch, u.roll, u.distance))
try:
    u.command("servo 9 1500")
    raised = ""
except fcl.Error as e:
    raised = str(e)
check(raised and u.command("servo 3 1700").startswith("servo 3"), "command(): returns the reply; a refused command raises fcl.Error ('%s')" % raised)
u.page("level")
u.wait(0.5)
check(u.page_name == "level" and u.rows.get(4, "").strip() == "LEVEL" and u.graphics[0] == 3,
      "page('level'): LCD row 4 '%s', graphics %s" % (u.rows.get(4, "").strip(), u.graphics))
frames = list(u.telemetry(count=20))
span = frames[-1]["t_ms"] - frames[0]["t_ms"]
check(len(frames) == 20 and 1800 <= span <= 2000 and set(fcl.FIELDS) <= set(frames[0]), "telemetry(count=20): 20 frames over %d ms" % span)
u.command("sim set dist 9000")
u.wait(1.5)
check(u.distance is None and len(u.cells) == 3 and u.cells[0][0] > 3.0, "distance is None out of range; cells %s" % (u.cells[0],))

# a room 3.0 m east-west by 2.4 m, seen from its centre, the unit 1.2 m above the floor
u.page("survey")
u.points(clear=True)
for e, n in ((1.5, 1.2), (1.5, -1.2), (-1.5, -1.2), (-1.5, 1.2)):
    g = math.hypot(e, n)
    u.command("sim set heading %.2f" % (math.degrees(math.atan2(e, n)) % 360))
    u.command("sim set pitch %.2f" % -math.degrees(math.atan2(1.2, g)))
    u.command("sim set dist %d" % round(1000 * math.hypot(g, 1.2)))
    u.wait(4)
    u.key("B2")
    u.wait(0.3)
pts = u.points()
check(len(pts) == 4 and [p["n"] for p in pts] == [1, 2, 3, 4] and abs(pts[0]["x"] - 1.5) < 0.12 and abs(pts[0]["y"] - 1.2) < 0.12,
      "points(): 4 points, the first at x %.2f y %.2f z %.2f" % (pts[0]["x"], pts[0]["y"], pts[0]["z"]) if pts else "points(): none")

# ---------------------------------------------------------------- fcl_survey.py
work = tempfile.mkdtemp(prefix="fcl_tools_")
lines = ["$I,start", "$P,1,10.0,0.0,1.000,0.174,0.985,0.000"] + ["$T,1,2,3"] + \
        ["$P,%d,%.1f,%.1f,%.3f,%.3f,%.3f,%.3f" % (p["n"], p["heading"], p["pitch"], p["dist"], p["x"], p["y"], p["z"]) for p in pts]
got = fcl_survey.parse(lines)
sd = fcl_survey.sides(got)
check(len(got) == 4 and abs(fcl_survey.area(got) - 7.2) < 0.3 and abs(sd[0] - 2.4) < 0.15 and abs(sd[1] - 3.0) < 0.15,
      "fcl_survey: an earlier survey in the same log is left out; sides %s, area %.2f m2" % (" ".join("%.2f" % x for x in sd), fcl_survey.area(got)))
svg = fcl_survey.svg(got)
csv = fcl_survey.csv_text(got)
check(svg.count("<circle") == 5 and "<polygon" in svg and "area 7." in svg and svg.count(" m</text>") >= 5 and csv.count("\n") == 5
      and csv.startswith("n,heading,pitch,dist,x,y,z"), "fcl_survey: plan drawing with 4 corners, 4 side lengths and the area; CSV with 4 rows")
open(os.path.join(work, "plan.svg"), "w", encoding="utf-8").write(svg)
tbl = fcl_survey.table(got)
check("area on the ground 7." in tbl and len(tbl.split("\n")) == 7, "fcl_survey: table with the summary line '%s'" % tbl.split("\n")[-1])
u.close()

# ---------------------------------------------------------------- fcl_update.py
root = os.path.join(work, "unit")
os.makedirs(root)
sim = fcl_sim.Sim("bridge")
s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()
web = fcl_web.Web(sim.bridge, sim.hubpy, sim.plat, port, root + os.sep)
sim.command("webpin 2468")
running = True


def serve():
    n = 0
    while running:
        web.poll()
        n += 1
        if n % 50 == 0:
            sim.step()
        time.sleep(0.0005)


th = threading.Thread(target=serve, daemon=True)
th.start()
said = []
link = fcl_update.Link("127.0.0.1:%d" % port, "2468")
files = fcl_update.local_files()
ok = fcl_update.update(link, files, say=said.append)
on_unit = dict((n, open(os.path.join(root, n), "rb").read()) for n in os.listdir(root) if n.endswith(".py"))
check(ok and on_unit == files and len(files) >= 15 and sim.plat.rebooted == 1,
      "update: %d Python files of firmware/esp32 on the unit, byte for byte; restarted" % len(on_unit))
said = []
ok = fcl_update.update(link, files, say=said.append)
check(ok and sim.plat.rebooted == 1 and "nothing to do" in said[-1], "again: nothing sent, no restart ('%s')" % said[0])
changed = dict(files, **{"fcl_user.py": b"def setup(apps):\n    pass\n"})
changed["fcl_calc.py"] = files["fcl_calc.py"] + b"# changed\n"
said = []
ok = fcl_update.update(link, changed, say=said.append)
check(ok and said[0].endswith("2 to send: fcl_calc.py fcl_user.py") and sim.plat.rebooted == 2 and
      open(os.path.join(root, "fcl_calc.py"), "rb").read().endswith(b"# changed\n"), "one file changed, one added: only those two are sent")
bit = bytes((i * 13) & 255 for i in range(200000))
said = []
ok = fcl_update.update(link, changed, bit, flash=True, say=said.append)
check(ok and open(os.path.join(root, "fcl_full.bit"), "rb").read() == bit and sim.plat.fpga_log == [("fcl_full.bit", True)] and sim.plat.rebooted == 3,
      "bitstream: sent whole, loaded into the configuration memory, restarted ('%s')" % said[-2].strip())
said = []
ok = fcl_update.update(fcl_update.Link("127.0.0.1:%d" % port, "0000"), files, say=said.append)
check(not ok and "REFUSED" in said[-1] and sim.plat.rebooted == 3 and open(os.path.join(root, "fcl_calc.py"), "rb").read().endswith(b"# changed\n"),
      "wrong PIN: refused, nothing changed, no restart ('%s')" % said[-1].strip())
said = []
ok = fcl_update.update(link, files, dry=True, say=said.append)
check(ok and "1 to send: fcl_calc.py" in said[0] and open(os.path.join(root, "fcl_calc.py"), "rb").read().endswith(b"# changed\n"),
      "--dry: says what it would send and sends nothing")
running = False
th.join()
web.close()

# ---------------------------------------------------------------- fcl_bringup.py
import fcl_bringup      # noqa: E402
import fcl_calibrate    # noqa: E402
link = fcl_calibrate.SimLink()
person = fcl_bringup.DemoPerson(link, quiet=True)
res, bu = fcl_bringup.bringup(link, person)
link.close()
bad = [x for x in res if x[1] is False]
check(len(res) >= 25 and not bad and [x[0] for x in res if x[1] is None] == ["wifi"],
      "fcl_bringup: %d checks on a good simulated unit, all pass but Wi-Fi (not set up)%s" % (len(res), "; FAIL: %s" % bad if bad else ""))
link = fcl_calibrate.SimLink()
person = fcl_bringup.DemoPerson(link, quiet=True)
link.send("sim error cell2 1.05")                       # a sense divider 5 % off
person.ask = lambda key, text: link.sim.world.s[key] if key.startswith("cell") else None
res, bu = fcl_bringup.bringup(link, person, ("readings", "buttons"))
link.close()
failed = [x[0] for x in res if x[1] is False]
text = chr(10).join(fcl_bringup.report(res, bu, "7", "simulator"))
check(failed == ["readings: cell 2"] and "**FAIL**" in text and "# Bring-up stage 9, board 7" in text,
      "fcl_bringup: a cell reading 5 %% high is the one failure, and the report marks it (%s)" % failed)
shutil.rmtree(work, ignore_errors=True)
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
