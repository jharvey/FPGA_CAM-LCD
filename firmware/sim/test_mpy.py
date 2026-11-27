#!/usr/bin/env python3
"""The ESP32's files under real MicroPython (the Unix port), not only under ordinary Python.

    python firmware/sim/test_mpy.py            needs a `micropython` program: on the PATH, or MICROPYTHON=/path/to/it
                                               (build: github.com/micropython/micropython, ports/unix, v1.24.1 used)
Exit code 0 = all checks pass, or no micropython found (it says so).

1. Every file of firmware/esp32 that the unit loads is compiled and imported by MicroPython.
2. mpy_scenario.py (a 28 s session: pages, tools, menu, calibration values, log, servos, the web page over real
   sockets, with the example user page) runs under both interpreters; the two outputs must agree line for line.
   Here the viper code (attitude filter, CRC) runs as compiled machine code.
3. mpy_unit.py runs the unit's real main loop (fcl_usbdev.py) with stand-ins for the ESP32's pins, I2S, UART and
   Wi-Fi, in real time, driven through stdin / stdout as the USB port would be.

What this does not show: the ESP32 itself.  The Unix port is 64-bit and has plenty of memory; the ESP32-S3 is
32-bit with about 2 MB of heap, and its machine / network / I2S modules are the real ones.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ESP = os.path.join(HERE, "..", "esp32")
MODULES = ("fcl_bridge", "fcl_calc", "fcl_cfg", "fcl_fix", "fcl_magcal", "fcl_app", "fcl_hubpy", "fcl_usb", "fcl_web",
           "fcl_user_example", "fcl_hub")
fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


def same(a, b):
    """two output lines agree: text equal, numbers equal to one unit in the last printed place"""
    if a == b:
        return True
    fa, fb = a.replace("|", ",").split(","), b.replace("|", ",").split(",")
    if len(fa) != len(fb):
        return False
    for x, y in zip(fa, fb):
        if x == y:
            continue
        try:
            places = len(x.split(".")[1]) if "." in x else 0
            if abs(float(x) - float(y)) > 1.0001 * 10 ** -places:
                return False
        except ValueError:
            return False
    return True


mpy = os.environ.get("MICROPYTHON") or shutil.which("micropython")
if not mpy:
    print("SKIPPED: no micropython program (set MICROPYTHON=/path/to/micropython); nothing was tested")
    sys.exit(0)
ver = subprocess.run([mpy, "-c", "import sys; print(sys.version)"], stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
print("MicroPython:", ver)

# ---- 1
bad = []
for m in MODULES:
    r = subprocess.run([mpy, "-c", "import %s" % m], cwd=ESP, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode or r.stdout.strip():
        bad.append("%s: %s" % (m, r.stdout.strip().split("\n")[-1]))
check(not bad, "MicroPython compiles and imports %d files of firmware/esp32%s" % (len(MODULES), "" if not bad else ": " + "; ".join(bad)))

# ---- 2
out = {}
for name, exe in (("python", sys.executable), ("micropython", mpy)):
    r = subprocess.run([exe, "mpy_scenario.py"], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                       timeout=300)
    out[name] = r.stdout.replace("\r\n", "\n").split("\n")
a, b = out["python"], out["micropython"]
check("END" in a and "END" in b, "the session runs to its end under both (%d and %d lines)" % (len(a), len(b)))
if "END" not in b:
    print("\n".join(b[-8:]))
diff = [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if not same(x, y)]
exact = sum(x == y for x, y in zip(a, b))
check(len(a) == len(b) and not diff, "the two outputs agree: %d lines, %d identical to the character" % (len(a), exact))
for i, x, y in diff[:5]:
    print("   line %d\n     python      %s\n     micropython %s" % (i + 1, x, y))
t = [x for x in b if x.startswith("$T")]
check(len(t) > 200 and "frames" in b[-3] and b[-3].endswith("crc errors 0"),
      "under MicroPython: %d telemetry lines, %s" % (len(t), b[-3] if len(b) > 3 else "?"))

# ---- 3
work = tempfile.mkdtemp(prefix="fcl_mpy_")
p = subprocess.Popen([mpy, "mpy_unit.py", work], cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     universal_newlines=True, bufsize=1)
SCRIPT = ((2.5, "status"), (0.2, "key B1"), (0.6, "log on"), (1.5, "log off"), (0.2, "tone 880 60"), (0.2, "servo 3 1700"),
          (0.2, "cal set hfov 50"), (0.2, "wifi HomeNet secret"), (0.5, "wifi"), (0.5, "repl"))
for wait, line in SCRIPT:
    time.sleep(wait)
    try:
        p.stdin.write(line + "\n")
        p.stdin.flush()
    except OSError:
        break                           # it has stopped: the checks below show its last lines
try:
    text = p.communicate(timeout=20)[0]
except subprocess.TimeoutExpired:
    p.kill()
    text = p.communicate()[0] + "\n(stopped: did not end)"
lines = text.replace("\r\n", "\n").split("\n")
t = [x.split(",") for x in lines if x.startswith("$T")]
check("#unit end" in lines, "fcl_usbdev.run() starts, runs and returns on 'repl'")
if "#unit end" not in lines:
    print("\n".join(lines[-12:]))
check(any("sensors found 0x1F" in x for x in lines), "the main loop finds all five sensors through the bridge driver")
secs = sum(w for w, _ in SCRIPT)
check(len(t) > 5 * secs and all(len(x) == len(t[0]) for x in t),
      "telemetry in real time: %d lines in %.1f s (%.0f per second)" % (len(t), secs, len(t) / secs))
check("$E,B1" in lines and any(x.startswith("#unit row4 |") and "LEVEL" in x for x in lines), "key B1: event, and LEVEL on the LCD model")
check(any(x.startswith("#unit servo") and "1700" in x for x in lines), "servo 3 1700 reaches the bridge model")
check(any(x.startswith("#unit i2s") and "written 0" not in x for x in lines), "tone: samples written to the I2S stand-in")
check(any(x.startswith("$W,connected,HomeNet") for x in lines), "wifi: saved and reported connected")
files = os.listdir(work)
log = open(os.path.join(work, "fcl001.log")).read().split("\n") if "fcl001.log" in files else []
check(sum(x.startswith("$T") for x in log) >= 8, "log on / off: fcl001.log with %d telemetry lines" % sum(x.startswith("$T") for x in log))
check("cal.json" in files and "50" in open(os.path.join(work, "cal.json")).read() and "wifiman.conf" in files,
      "cal set and wifi write cal.json and wifiman.conf")
errs = [x for x in lines if "Traceback" in x or "Error" in x]
check(not errs, "no Python error in the stream" + ("" if not errs else ": " + errs[0]))
shutil.rmtree(work, ignore_errors=True)
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
