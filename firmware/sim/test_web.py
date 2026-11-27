#!/usr/bin/env python3
"""Tests of the unit's web page (firmware/esp32/fcl_web.py) against the simulator, over real sockets on this PC.

    python firmware/sim/test_web.py
Exit code 0 = all checks pass.
"""
import json
import os
import socket
import sys
import threading
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


sim = fcl_sim.Sim("bridge")
sim.command("sim buttons off")
s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()
web = fcl_web.Web(sim.bridge, sim.hubpy, sim.plat, port)
for _ in range(60):
    sim.step()


def ask(path, body=None):
    """one request from a second thread, while this one keeps the simulator and the server going"""
    res = {}

    def work():
        try:
            req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=None if body is None else body.encode())
            with urllib.request.urlopen(req, timeout=5) as r:
                res["status"], res["type"], res["body"] = r.status, r.headers.get("Content-Type"), r.read().decode()
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
    return res


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
r = json.loads(ask("/c", "view edges")["body"])
for _ in range(10):
    sim.step()
st = json.loads(ask("/s")["body"])
check(r["ok"] and st["edges"] and sim.model.edges, "POST /c view edges: reaches the FPGA's video key")
r = json.loads(ask("/c", "wifi HomeNet secret-password")["body"])
r2 = json.loads(ask("/c", "repl")["body"])
check(not r["ok"] and not r2["ok"] and sim.plat.wifi[0] == "off" and not sim.bridge.exit,
      "Wi-Fi settings and the Python prompt are refused on the web page: '%s'" % r["lines"][-1])
r = ask("/nothing")
check("404" in str(r.get("error", "")), "unknown path: 404")
lines_before = len(sim.lines)
json.loads(ask("/c", "status")["body"])
check(len(sim.lines) == lines_before, "answers to web commands do not leak into the USB stream")
# a client that connects and says nothing must not stop anything
idle = socket.create_connection(("127.0.0.1", port))
for _ in range(50):
    web.poll()
st = json.loads(ask("/s")["body"])
check(st["t"]["heading"] is not None and web.requests >= 9, "a silent client does not block the others (%d requests served)" % web.requests)
idle.close()
web.close()
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
