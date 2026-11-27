#!/usr/bin/env python3
"""Tests of the unit's web page (firmware/esp32/fcl_web.py) against the simulator, over real sockets on this PC:
the page, the state, commands, the PIN, files up and down.

    python firmware/sim/test_web.py
Exit code 0 = all checks pass.
"""
import binascii
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcl_sim      # noqa: E402
import fcl_web      # noqa: E402

fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


root = tempfile.mkdtemp(prefix="fcl_web_")          # the unit's flash for this test
sim = fcl_sim.Sim("bridge")
sim.plat.fs_root = root
sim.command("sim buttons off")
s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()
web = fcl_web.Web(sim.bridge, sim.hubpy, sim.plat, port, root + os.sep)
for _ in range(60):
    sim.step()


def ask(path, body=None, method=None, pin=None, crc=None, raw=False):
    """one request from a second thread, while this one keeps the simulator and the server going"""
    res = {}

    def work():
        try:
            data = None if body is None else body if isinstance(body, bytes) else body.encode()
            req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=data, method=method)
            if pin is not None:
                req.add_header("X-Pin", pin)
            if crc is not None:
                req.add_header("X-Crc", crc)
            with urllib.request.urlopen(req, timeout=10) as r:
                d = r.read()
                res["status"], res["type"], res["body"] = r.status, r.headers.get("Content-Type"), d if raw else d.decode()
        except urllib.error.HTTPError as e:
            res["status"], res["body"], res["error"] = e.code, e.read().decode(errors="replace"), e
        except Exception as e:
            res["error"] = e
    th = threading.Thread(target=work)
    th.start()
    n = 0
    while th.is_alive():
        web.poll()
        n += 1
        if n % 200 == 0:
            sim.step()
        th.join(0.001)
    res["polls"] = n
    return res


def crc_of(data):
    return "%08x" % (binascii.crc32(data) & 0xFFFFFFFF)


r = ask("/")
check(r.get("status") == 200 and "text/html" in r["type"] and "<title>FCL monocular</title>" in r["body"] and len(r["body"]) > 4000,
      "GET /: the page, %d bytes" % len(r.get("body", "")))
r = ask("/s")
st = json.loads(r["body"])
check(len(st["lcd"]) == 15 and all(len(x) == 30 for x in st["lcd"]) and st["page"] == "OVERVIEW" and 0 <= st["t"]["heading"] < 360
      and st["t"]["soc1"] > 50, "GET /s: telemetry and the 15 LCD rows; heading %.0f, page %s" % (st["t"]["heading"], st["page"]))
r = json.loads(ask("/c", "key B1")["body"])
for _ in range(10):
    sim.step()
st = json.loads(ask("/s")["body"])
check(r["ok"] and st["page"] == "LEVEL" and "LEVEL" in st["lcd"][4], "POST /c key B1: next page, LCD row 4 '%s'" % st["lcd"][4].strip())
check(st["hud"][0] & 1 and st["gfx"] == 0 and st["pin"] is False and "pitch0" in st["cal"],
      "state carries the graphics the FPGA draws (%s), the level trim and whether a PIN is set" % st["hud"])
r = json.loads(ask("/c", "view edges")["body"])
for _ in range(10):
    sim.step()
st = json.loads(ask("/s")["body"])
check(r["ok"] and st["edges"] and sim.model.edges, "POST /c view edges: reaches the FPGA's video key")
r = json.loads(ask("/c", "wifi HomeNet secret-password")["body"])
r2 = json.loads(ask("/c", "repl")["body"])
r3 = json.loads(ask("/c", "webpin 1111")["body"])
check(not r["ok"] and not r2["ok"] and not r3["ok"] and sim.plat.wifi[0] == "off" and not sim.bridge.exit and not web.pin,
      "Wi-Fi settings, the Python prompt and the PIN itself are refused on the web page: '%s'" % r["lines"][-1])
r = ask("/nothing")
check(r.get("status") == 404, "unknown path: 404")
lines_before = len(sim.lines)
json.loads(ask("/c", "status")["body"])
check(len(sim.lines) == lines_before, "answers to web commands do not leak into the USB stream")

# ---- the PIN
code = b"# a page of your own\nimport fcl_app\n\n\ndef setup(apps):\n    pass\n"
r = ask("/f/fcl_user.py", code, "PUT", crc=crc_of(code))
r2 = json.loads(ask("/c", "cal set hfov 50")["body"])
check(r["status"] == 403 and "no PIN" in r["body"] and not r2["ok"] and sim.hubpy.cfg.get("hfov") == 40 and not os.listdir(root),
      "no PIN set: uploads and calibration values are refused ('%s')" % json.loads(r["body"])["error"])
sim.command("webpin 12")
bad = sim.lines[-1]
sim.command("webpin 4321")
check("err" in bad and web.pin == "4321" and open(os.path.join(root, "webpin.txt")).read() == "4321", "webpin on the USB port: 2 digits refused, 4321 stored")
r = ask("/f/fcl_user.py", code, "PUT", pin="0000", crc=crc_of(code))
r2 = json.loads(ask("/c", "cal set hfov 50", pin="4321")["body"])
check(r["status"] == 403 and "fcl_user.py" not in os.listdir(root) and r2["ok"] and sim.hubpy.cfg.get("hfov") == 50,
      "wrong PIN: upload refused; right PIN: 'cal set hfov 50' taken")

# ---- files up
r = ask("/f/fcl_user.py", code, "PUT", pin="4321", crc=crc_of(code))
got = open(os.path.join(root, "fcl_user.py"), "rb").read() if "fcl_user.py" in os.listdir(root) else b""
check(r.get("status") == 200 and json.loads(r["body"])["crc"] == crc_of(code) and got == code, "PUT /f/fcl_user.py with the PIN: stored, CRC %s" % crc_of(code))
r = ask("/f/fcl_user.py", b"broken on the way", "PUT", pin="4321", crc="12345678")
check(r["status"] == 400 and open(os.path.join(root, "fcl_user.py"), "rb").read() == code and "fcl_user.py.new" not in os.listdir(root),
      "an upload with the wrong CRC is thrown away and the old file stays")
r = ask("/f/notes.txt", b"x", "PUT", pin="4321")
r2 = ask("/f/..%2Fevil.py", b"x", "PUT", pin="4321")
r3 = ask("/f/sub/evil.py", b"x", "PUT", pin="4321")
check(r["status"] == 403 and r2["status"] == 403 and r3["status"] == 403 and sorted(os.listdir(root)) == ["fcl_user.py", "webpin.txt"],
      "only .py and .bit with a plain name: .txt, .. and a folder are refused")
big = bytes((i * 7 + (i >> 8)) & 255 for i in range(300000))
t_before = sim.t
r = ask("/f/fcl_full.bit", big, "PUT", pin="4321", crc=crc_of(big))
check(r.get("status") == 200 and open(os.path.join(root, "fcl_full.bit"), "rb").read() == big,
      "a 300 kB bitstream arrives whole (%d calls of poll, the unit ran %.1f s meanwhile)" % (r["polls"], sim.t - t_before))
r = json.loads(ask("/files")["body"])
names = dict((f["name"], f) for f in r)
check(names["fcl_user.py"]["crc"] == crc_of(code) and names["fcl_full.bit"]["size"] == 300000 and names["fcl_full.bit"]["crc"] is None
      and "webpin.txt" not in names, "GET /files: names, sizes and CRCs; the PIN file is not listed")
r = json.loads(ask("/c", "fpga fcl_full.bit flash", pin="4321")["body"])
r2 = json.loads(ask("/c", "reboot", pin="4321")["body"])
r3 = json.loads(ask("/c", "reboot")["body"])
check(r["ok"] and r2["ok"] and not r3["ok"] and sim.plat.fpga_log == [("fcl_full.bit", True)] and sim.plat.rebooted == 1,
      "fpga and reboot with the PIN: '%s'; without it refused" % r["lines"][-1])
for _ in range(5):
    ask("/c", "reboot", pin="9999")
r = json.loads(ask("/c", "reboot", pin="4321")["body"])
check(not r["ok"] and "wait" in r["lines"][-1] and sim.plat.rebooted == 1, "five wrong PINs: locked for a minute, even for the right one")
web.lock_t = 0

# ---- files down: a log
sim.command("log on")
for _ in range(60):
    sim.step()
sim.command("log off")
want = open(os.path.join(root, "fcl001.log"), "rb").read() if "fcl001.log" in os.listdir(root) else b"?"
r = ask("/f/fcl001.log", raw=True)
r2 = ask("/f/webpin.txt")
check(r.get("status") == 200 and r["body"] == want and want.count(b"$T,") >= 25 and r2["status"] == 404,
      "GET /f/fcl001.log: the log as written, %d bytes; the PIN file cannot be fetched" % len(want))
r = ask("/f/fcl_full.bit", raw=True)
check(r.get("status") == 200 and r["body"] == big, "a 300 kB file is sent in pieces between sensor frames (%d calls of poll)" % r["polls"])

# a client that connects and says nothing must not stop anything
idle = socket.create_connection(("127.0.0.1", port))
for _ in range(50):
    web.poll()
st = json.loads(ask("/s")["body"])
check(st["t"]["heading"] is not None and web.requests >= 9, "a silent client does not block the others (%d requests served)" % web.requests)
idle.close()
half = socket.create_connection(("127.0.0.1", port))
half.send(b"PUT /f/half.py HTTP/1.1\r\nX-Pin: 4321\r\nContent-Length: 1000\r\n\r\nonly the start")
for _ in range(50):
    web.poll()
half.close()
for _ in range(50):
    web.poll()
check("half.py" not in os.listdir(root) and "half.py.new" not in os.listdir(root), "an upload that breaks off leaves no file behind")
web.close()
shutil.rmtree(root, ignore_errors=True)
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
