#!/usr/bin/env python3
"""The ESP32 files on an emulated ESP32: Espressif's QEMU, the official MicroPython 1.24.1 firmware for the ESP32
with PSRAM, and the files copied onto its flash.  Two runs there:

1. viper_check.py: the attitude filter (viper) and the link CRC on made-up integer data.  No floats: the output must
   equal ordinary Python's exactly.  This is the check of the viper code as Xtensa machine code.
2. mpy_scenario.py, the 40 s session of test_mpy.py.  MicroPython on the ESP32 calculates with 32-bit floats (the
   PC with 64-bit ones), so numbers differ in their last digits, a whole number worked out from a float can be
   one off, and a line timed by the clock can come one frame earlier or later.  So each line must have a partner
   of the same kind within three lines, with every number within 1 + 1 % of its value (a telemetry value also
   within what it changes in one frame); the largest difference of each telemetry field is printed.  The board's output is kept as esp32_session.txt in the --qemu folder.

    python3 firmware/sim/test_esp32_qemu.py --analyse FILE    compare a kept esp32_session.txt again, no emulator

    python3 firmware/sim/test_esp32_qemu.py --qemu DIR       DIR holds qemu/bin/qemu-system-xtensa, lib/ (libslirp)
                                                             and flash32.bin (the firmware at 0x1000 of 4 MB)
Set up on the Linux VM (see doc/DEVELOPER_GUIDE.md, Tests).  Takes several minutes: the emulator is slow.

Emulated: the ESP32 (Xtensa LX6, 240 MHz) and its PSRAM.  The unit has an ESP32-S3 (Xtensa LX7); the emulator's S3
machine stops at the S3 firmware's USB set-up, so the ESP32 stands in.  Both run the same MicroPython code
generator for viper.  Not emulated: Wi-Fi (the session's web part is reported, not required), I2S, the real UART.
"""
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ESP = os.path.join(HERE, "..", "esp32")
sys.path.insert(0, HERE)
sys.path.insert(0, ESP)
import esp_raw      # noqa: E402
from fcl_usb import T_FIELDS      # noqa: E402

FILES = [(os.path.join(ESP, n), "/" + n) for n in ("fcl_bridge.py", "fcl_calc.py", "fcl_cfg.py", "fcl_fix.py", "fcl_magcal.py",
                                                  "fcl_app.py", "fcl_hubpy.py", "fcl_usb.py", "fcl_web.py", "fcl_user_example.py",
                                                  "fcl_hub.py")] + \
        [(os.path.join(HERE, n), "/" + n) for n in ("fcl_sim.py", "bridge_model.py", "fcl_osd.py", "mpy_scenario.py", "viper_check.py")] + \
        [(os.path.join(HERE, "mpy", n), "/mpy/" + n.replace(os.sep, "/")) for n in ("random.py", "subprocess.py", os.path.join("os", "__init__.py"),
                                                                                    os.path.join("os", "path.py"))]
fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    sys.stdout.flush()
    fail += not ok


NUM = re.compile(r"-?\d+(?:\.\d+)?")


def close(a, b, worst, allow=None):
    """two lines of the same kind whose numbers agree within the float tolerance; allow: field -> what that field
    changes in one frame, for telemetry (a slewing value may arrive one frame late)"""
    if a.startswith("$T,"):
        fa, fb = a.split(","), b.split(",")
        if len(fa) != len(fb) or fb[0] != "$T":
            return False
        for k, (x, y) in enumerate(zip(fa, fb)):
            if k == 0 or x == y:
                continue
            try:
                d = abs(float(x) - float(y))
            except ValueError:
                return False
            name = T_FIELDS[k - 1] if k <= len(T_FIELDS) else ""
            if d > 1.0 + 0.01 * abs(float(x)) + (allow or {}).get(name, 0.0):
                return False
            if name != "t_ms":
                worst[name] = max(worst.get(name, 0.0), d)
        return True
    # other lines: the same words, and the numbers in them within the tolerance
    if NUM.sub("#", a) != NUM.sub("#", b):
        return False
    return all(abs(float(x) - float(y)) <= 1.0 + 0.01 * abs(float(x)) for x, y in zip(NUM.findall(a), NUM.findall(b)))


def compare(board):
    ref = subprocess.run([sys.executable, os.path.join(HERE, "mpy_scenario.py")], stdout=subprocess.PIPE, universal_newlines=True).stdout
    ref = ref.rstrip("\n").split("\n")
    cut = ref.index("== web") if "== web" in ref else len(ref)
    worst, used, bad, same = {}, set(), [], 0
    tele = [i for i, x in enumerate(ref[:cut]) if x.startswith("$T,")]
    for i, a in enumerate(ref[:cut]):
        if i < len(board) and board[i] == a:
            used.add(i)
            same += 1
            continue
        allow = {}
        if a.startswith("$T,"):                          # what each field changes over one frame here
            k = tele.index(i)
            this = a.split(",")[1:]
            for n in (k - 1, k + 1):
                if 0 <= n < len(tele):
                    other = ref[tele[n]].split(",")[1:]
                    for name, x, y in zip(T_FIELDS, this, other):
                        try:
                            allow[name] = max(allow.get(name, 0.0), abs(float(x) - float(y)))
                        except ValueError:
                            pass
        for j in sorted(range(max(0, i - 3), min(len(board), i + 4)), key=lambda j: abs(j - i)):
            if j not in used and close(a, board[j], worst, allow):
                used.add(j)
                break
        else:
            bad.append((i, a, board[i] if i < len(board) else ""))
    check(len(board) >= cut and not bad, "the session's output matches ordinary Python's within the float tolerance: %d lines, "
          "%d identical, %d within it, %d not" % (cut, same, cut - same - len(bad), len(bad)))
    for i, a, b in bad[:4]:
        print("   line %d\n     python  %s\n     esp32   %s" % (i + 1, a, b))
    if worst:
        print("      largest differences (32-bit floats): " + ", ".join("%s %g" % kv for kv in sorted(worst.items())))
    if len(board) > cut:
        print("      after the web marker the board printed: " + " | ".join(board[cut + 1:cut + 3])[:150])


def main():
    if "--analyse" in sys.argv:
        compare(open(sys.argv[sys.argv.index("--analyse") + 1]).read().rstrip("\n").split("\n"))
        print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
        return 1 if fail else 0
    qdir = os.path.abspath(sys.argv[sys.argv.index("--qemu") + 1])
    work = os.path.join(qdir, "run")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(os.path.join(qdir, "flash32.bin"), os.path.join(work, "flash.bin"))       # a fresh board every time
    env = dict(os.environ, LD_LIBRARY_PATH=os.path.join(qdir, "lib"))
    q = subprocess.Popen([os.path.join(qdir, "qemu", "bin", "qemu-system-xtensa"), "-nographic", "-machine", "esp32", "-m", "4M",
                          "-drive", "file=flash.bin,if=mtd,format=raw", "-serial", "tcp:127.0.0.1:%d,server=on,wait=on" % esp_raw.PORT,
                          "-monitor", "none"], cwd=work, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        b = esp_raw.Board()
        boot = b.read(15).decode(errors="replace")
        check("MicroPython v1.24.1" in boot and "with SPIRAM" in boot, "the emulated ESP32 boots MicroPython 1.24.1 (with PSRAM)")
        b.raw()
        out, _ = b.exec("import sys, gc\nprint(sys.platform, gc.mem_free())")
        print("     ", out.strip())
        t0 = time.time()
        b.mkdir("/mpy")
        b.mkdir("/mpy/os")
        for local, remote in FILES:
            b.put(local, remote)
        check(True, "%d files copied onto its flash in %.0f s" % (len(FILES), time.time() - t0))
        t0 = time.time()
        vout, verr = b.exec("import os\nos.chdir('/')\nimport viper_check", timeout=3600)
        vsecs = time.time() - t0
        t0 = time.time()
        out, err = b.exec("import mpy_scenario", timeout=7200)
        secs = time.time() - t0
    finally:
        q.kill()
        q.wait()
    vref = subprocess.run([sys.executable, os.path.join(HERE, "viper_check.py")], stdout=subprocess.PIPE, universal_newlines=True).stdout
    vboard = vout.replace("\r\n", "\n")
    check(not verr and vboard == vref and vref.endswith("END\n"),
          "viper code as Xtensa machine code: the filter and the CRC give exactly ordinary Python's numbers (%d lines, %.0f s)%s"
          % (vref.count("\n"), vsecs, "" if not verr else ": " + verr.strip().split("\n")[-1]))
    board = out.replace("\r\n", "\n").rstrip("\n").split("\n")
    open(os.path.join(qdir, "esp32_session.txt"), "w").write("\n".join(board) + "\n")
    check(not err, "the session ran on the board in %.0f s without an error%s" % (secs, "" if not err else ": " + err.strip().split("\n")[-1]))
    compare(board)
    t = [x for x in board[:cut] if x.startswith("$T")]
    print("      %d telemetry lines from the board; after the web marker it printed: %s" %
          (len(t), " | ".join(board[cut + 1:cut + 3])[:150] if len(board) > cut else "nothing"))
    print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
