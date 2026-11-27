#!/usr/bin/env python3
"""Make the pictures of doc/USER_MANUAL.md and doc/DEVELOPER_GUIDE.md from the simulator (doc/manual/).

    python firmware/tools/make_manual.py            all pictures
    python firmware/tools/make_manual.py --no-web   skip the web page screenshot (it needs Edge or Chrome)

LCD pictures: the text, the graphics and the dot are what the simulated unit sent to the FPGA's overlay, drawn with
the FPGA's pixel rules; the camera picture behind them is a stand-in (sky, horizon, a 1 m grid on the ground).
"""
import os
import shutil
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "esp32"))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(0, HERE)
import fcl_sim      # noqa: E402
import fcl_osd      # noqa: E402
import fcl_usb      # noqa: E402
import fcl_log      # noqa: E402
import fcl_calibrate    # noqa: E402
import fcl_survey       # noqa: E402
import math             # noqa: E402

OUT = os.path.join(ROOT, "doc", "manual")


def lcd(sim, name):
    t = dict(sim.last)
    if t["flags"] & 128:
        t["overlay"] &= ~1                               # the menu hides the dot
    fcl_osd.render(t, sim.state["osd"], hud=sim.state["hud"]).save(os.path.join(OUT, name + ".png"))
    print("wrote", name + ".png", "|", " / ".join(r.strip() for r in sim.state["osd"] if r.strip())[:110])


def run(sim, seconds, *commands):
    for c in commands:
        sim.command(c)
    for _ in range(int(round(seconds / fcl_sim.STEP_S))):
        sim.step()


def lcd_pictures():
    sim = fcl_sim.Sim("bridge")
    run(sim, 5.0, "sim buttons off", "sim set heading 48", "sim set pitch -4", "sim set roll 2", "sim set dist 1870", "sim set alt 0")
    lcd(sim, "lcd_overview")
    run(sim, 3.0, "key B1", "sim set pitch 6.5", "sim set roll -3")
    lcd(sim, "lcd_level")
    run(sim, 3.0, "sim set pitch 0", "sim set roll 0")
    lcd(sim, "lcd_level_ok")
    run(sim, 3.0, "key B1", "sim set pitch -20", "sim set dist 2000")
    lcd(sim, "lcd_height_foot")
    run(sim, 2.5, "key B2", "sim set pitch 25")
    lcd(sim, "lcd_height_top")
    run(sim, 0.5, "key B2")
    lcd(sim, "lcd_height_result")
    run(sim, 2.0, "key B1", "sim set pitch 0", "sim set heading 100")
    run(sim, 3.0, "key B2", "sim set heading 77", "sim set alt 1.2")
    lcd(sim, "lcd_bearing")
    # Survey: a room 3.0 m by 2.4 m from its middle, the unit 1.2 m above the floor
    run(sim, 0.5, "mode 4", "points clear")
    for e, n in ((1.5, 1.2), (1.5, -1.2), (-1.5, -1.2), (-1.5, 1.2)):
        g = math.hypot(e, n)
        run(sim, 4.0, "sim set heading %.2f" % (math.degrees(math.atan2(e, n)) % 360), "sim set pitch %.2f" % -math.degrees(math.atan2(1.2, g)),
            "sim set dist %d" % round(1000 * math.hypot(g, 1.2)))
        run(sim, 0.4, "key B2")
    lcd(sim, "lcd_survey")
    pts = [dict(zip(fcl_survey.KEYS, (i + 1,) + p)) for i, p in enumerate(sim.hubpy.apps.survey.pts)]
    open(os.path.join(OUT, "survey_plan.svg"), "w", newline="\n", encoding="utf-8").write(fcl_survey.svg(pts))
    open(os.path.join(OUT, "survey_table.txt"), "w", newline="\n").write(fcl_survey.table(pts) + "\n")
    print("wrote survey_plan.svg, survey_table.txt")
    run(sim, 4.0, "mode 0", "hud all", "sim set heading 48", "sim set pitch 3", "sim set roll 8", "sim set dist 1870")
    lcd(sim, "lcd_graphics")
    run(sim, 0.5, "hud off", "sim set pitch 0", "sim set roll 0", "sim set heading 77")
    run(sim, 0.5, "mode 0", "key B1L")
    lcd(sim, "lcd_menu")
    run(sim, 0.5, "key B1", "key B1", "key B1", "key B1", "key B1", "key B1", "key B2")
    run(sim, 4.0, "sim set pitch 80")
    run(sim, 4.0, "sim set pitch -80")
    run(sim, 3.0, "sim set pitch 0")
    lcd(sim, "lcd_menu_compass")
    sim.close()


def log_plot():
    sim = fcl_sim.Sim("bridge")
    run(sim, 1.0, "log on")
    run(sim, 70.0)
    run(sim, 0.2, "log off")
    path = os.path.join(OUT, "demo.log")
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(sim.plat.log_lines) + "\n")
    tele, other = fcl_log.load(path)
    fcl_log.plot(tele, other, os.path.join(OUT, "log_plot.png"))
    with open(os.path.join(OUT, "log_summary.txt"), "w", newline="\n") as f:
        f.write("\n".join(fcl_log.summary(tele, other)) + "\n")
    print("wrote demo.log (%d lines), log_plot.png, log_summary.txt" % len(sim.plat.log_lines))
    sim.close()


def calibration_demo():
    link = fcl_calibrate.SimLink()
    said = []
    user = fcl_calibrate.DemoUser(link)
    user.say = said.append
    res, cal = fcl_calibrate.calibrate(link, user)
    link.close()
    with open(os.path.join(OUT, "calibration_demo.txt"), "w", newline="\n") as f:
        f.write("$ python firmware/tools/fcl_calibrate.py --sim --demo\n" + "\n".join(said + fcl_calibrate.report(res, cal)) + "\n")
    print("wrote calibration_demo.txt")


def web_picture():
    browser = None
    for p in (os.environ.get("BROWSER"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome")):
        if p and os.path.exists(p):
            browser = p
            break
    if not browser:
        print("no Edge / Chrome found: web page picture skipped")
        return
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, "..", "sim", "fcl_sim.py"), "--port", str(port + 1), "--web", str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(4.0)
        c = socket.create_connection(("127.0.0.1", port + 1))
        c.sendall(b"sim buttons off\nsim set heading 48\nsim set pitch -4\nsim set roll 6\nsim set dist 1870\nkey B1\nlog on\n")
        time.sleep(3.0)
        c.sendall(b"log off\nsim set alt 0.8\n")
        time.sleep(1.0)
        png = os.path.join(OUT, "web_page.png")
        prof = os.path.join(OUT, "_profile")
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--user-data-dir=" + prof,
                        "--window-size=500,1500", "--virtual-time-budget=3000", "--screenshot=" + png,
                        "http://127.0.0.1:%d/" % port], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        shutil.rmtree(prof, ignore_errors=True)
        c.close()
        print("wrote web_page.png" if os.path.exists(png) else "the browser made no screenshot")
    finally:
        srv.terminate()


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    lcd_pictures()
    log_plot()
    calibration_demo()
    if "--no-web" not in sys.argv:
        web_picture()
