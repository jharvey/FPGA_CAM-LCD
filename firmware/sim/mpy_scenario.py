"""One fixed session with the simulated unit (about 40 s of its time), printed line by line.  test_mpy.py runs this file under ordinary
Python and under MicroPython (Unix port) and compares the two outputs.

    python firmware/sim/mpy_scenario.py
    micropython firmware/sim/mpy_scenario.py        (from firmware/sim, see test_mpy.py for the search path)
"""
import sys

MPY = sys.implementation.name == "micropython"
HERE = __file__.replace("\\", "/").rsplit("/", 1)[0] if "/" in __file__.replace("\\", "/") else "."
if sys.platform == "esp32":                  # on the board (test_esp32_qemu.py): every file at the top of its flash
    HERE = ""
if MPY:
    sys.path.insert(0, HERE + "/mpy")       # os.path, subprocess, random: what the simulator needs from the desktop
sys.path.insert(0, HERE + "/../esp32")
sys.path.insert(0, HERE)
import json         # noqa: E402
import os           # noqa: E402
import socket       # noqa: E402
import fcl_sim      # noqa: E402
import fcl_web      # noqa: E402

ns = {}
exec(open(HERE + "/mpy/random.py").read(), ns)      # the same noise generator on both interpreters

sim = fcl_sim.Sim("bridge", user="fcl_user_example")
sim.world.rnd = ns["Random"](12345)
print("sensors 0x%02X" % sim.sensors_found)


def go(seconds):
    for _ in range(int(round(seconds / fcl_sim.STEP_S))):
        for line in sim.step():
            print(line)


def cmd(*lines):
    for line in lines:
        print("> " + line)
        sim.command(line)
        for out in sim.lines:
            print(out)
        del sim.lines[:]


cmd("sim buttons off", "sim set heading 100", "sim set pitch 2", "sim set roll -3", "sim set dist 2000", "status")
go(3.0)
cmd("zero", "log on", "sim set alt 2.5", "sim set heading 250")
go(3.0)
for key in ("B1", "B2", "B1", "B2"):                 # Level, hold; Height, first sighting
    cmd("key " + key)
    go(0.6)
cmd("sim set pitch 30")
go(2.0)
cmd("key B2", "key B1")                              # second sighting; Bearing
go(0.6)
cmd("key B2", "sim set heading 300")
go(2.0)
cmd("key B2", "key B1", "sim set heading 40", "sim set pitch -30", "sim set dist 1800")      # Survey
go(3.0)
cmd("key B2", "sim set heading 130")
go(3.0)
cmd("key B2", "sim set heading 220")
go(3.0)
cmd("key B2", "points", "hud all")
go(1.0)
cmd("hud off", "key B1", "key B2")                   # user page (Climb): start
go(1.0)
cmd("sim set alt 4.0")
go(3.0)
cmd("key B2", "key B1L")                             # stop; menu
go(0.6)
cmd("key B1", "key B2", "key B1L")
go(0.6)
cmd("mode 0", "cal", "cal set hfov 50", "cal set pitch0 1.5", "cal set cell2 1.02", "cal", "view edges", "threshold up",
    "follow on", "servo 3 1700", "pan here", "sim set heading 320", "overlay 63")
go(2.0)
cmd("pan off", "follow off", "view camera", "magcal", "sim set pitch -88", "sim set dist 9000")
go(3.0)
cmd("sim error cell1 1.03", "sim set cell3 3.35", "sim set temp2 61", "sim press PWR 300")
go(3.0)
cmd("log off", "wifi", "tone 880 100", "status", "nonsense", "cal reset", "hud bogus", "points clear", "webpin 1234", "reboot")
go(1.0)

# ---- the web page over real sockets
print("== web")
PORT = 18473
ROOT = HERE + "/mpy_fs_" + ("m" if MPY else "c") + "/"       # the unit's flash for this run
try:
    os.mkdir(ROOT[:-1])
except OSError:
    pass
for name in os.listdir(ROOT[:-1]):
    os.remove(ROOT + name)
web = fcl_web.Web(sim.bridge, sim.hubpy, sim.plat, PORT, ROOT)


def ask(path, body=None, put=False, pin="1357"):
    c = socket.socket()
    c.connect(socket.getaddrinfo("127.0.0.1", PORT)[0][-1])
    c.settimeout(3)
    req = ("%s %s HTTP/1.1\r\nX-Pin: %s\r\nContent-Length: %d\r\n\r\n%s" % ("PUT" if put else "POST", path, pin, len(body), body)) \
        if body is not None else "GET %s HTTP/1.1\r\n\r\n" % path
    c.send(req.encode())
    data = b""
    for _ in range(200):
        web.poll()
        try:
            c.setblocking(False)
            d = c.recv(4096)
            if d == b"":
                break
            if d:
                data += d
        except OSError:
            pass
    c.close()
    head, _, payload = data.partition(b"\r\n\r\n")
    return head.split(b"\r\n")[0].decode(), payload.decode()


st, body = ask("/")
print("web / :", st, len(body), "<title>FCL monocular</title>" in body)
st, body = ask("/s")
s = json.loads(body)
print("web /s:", st, s["page"], len(s["lcd"]), "%.0f" % s["t"]["heading"], s["t"]["soc1"], s["menu"])
for i in range(15):
    print("lcd %2d |%s|" % (i, s["lcd"][i]))
st, body = ask("/c", "key B1")
print("web /c key B1:", st, json.loads(body)["ok"])
go(0.5)
st, body = ask("/s")
print("web page now:", json.loads(body)["page"])
st, body = ask("/c", "repl")
print("web /c repl:", st, json.loads(body)["ok"])
st, body = ask("/nothing")
print("web /nothing:", st)
st, body = ask("/files")
print("web /files:", st, sorted(f["name"] for f in json.loads(body))[:3])
sim.command("webpin 1357")
del sim.lines[:]
data = "x = 1\n" * 300
st, body = ask("/f/mpy_up.py", data, put=True)
print("web PUT:", st, json.loads(body)["ok"])
st, body = ask("/f/mpy_up.py")
print("web GET file:", st, len(body), body == data)
st, body = ask("/c", "cal set hfov 55", pin="1357")
print("web cal with PIN:", st, json.loads(body)["ok"], sim.hubpy.cfg.get("hfov"))
st, body = ask("/c", "cal set hfov 60", pin="1111")
print("web cal with a wrong PIN:", st, json.loads(body)["ok"], sim.hubpy.cfg.get("hfov"))
web.close()
for name in os.listdir(ROOT[:-1]):
    os.remove(ROOT + name)
os.rmdir(ROOT[:-1])
print("frames %d crc errors %d" % sim.link_stats())
print("END")
