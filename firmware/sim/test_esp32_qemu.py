#!/usr/bin/env python3
"""The ESP32 files on an emulated ESP32: Espressif's QEMU, the official MicroPython 1.24.1 firmware for the ESP32
with PSRAM, the files copied onto its flash, and mpy_scenario.py run there.  Its output must equal ordinary
Python's line for line: that checks the viper code (attitude filter, CRC) as real Xtensa machine code, and the
ESP32 port of MicroPython itself.

    python3 firmware/sim/test_esp32_qemu.py --qemu DIR       DIR holds qemu/bin/qemu-system-xtensa, lib/ (libslirp)
                                                             and flash32.bin (the firmware at 0x1000 of 4 MB)
Set up on the Linux VM (see doc/DEVELOPER_GUIDE.md, Tests).  Takes several minutes: the emulator is slow.

Emulated: the ESP32 (Xtensa LX6, 240 MHz) and its PSRAM.  The unit has an ESP32-S3 (Xtensa LX7); the emulator's S3
machine stops at the S3 firmware's USB set-up, so the ESP32 stands in.  Both run the same MicroPython code
generator for viper.  Not emulated: Wi-Fi (the session's web part is reported, not required), I2S, the real UART.
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ESP = os.path.join(HERE, "..", "esp32")
sys.path.insert(0, HERE)
import esp_raw      # noqa: E402

FILES = [(os.path.join(ESP, n), "/" + n) for n in ("fcl_bridge.py", "fcl_calc.py", "fcl_cfg.py", "fcl_fix.py", "fcl_magcal.py",
                                                  "fcl_app.py", "fcl_hubpy.py", "fcl_usb.py", "fcl_web.py", "fcl_user_example.py",
                                                  "fcl_hub.py")] + \
        [(os.path.join(HERE, n), "/" + n) for n in ("fcl_sim.py", "bridge_model.py", "fcl_osd.py", "mpy_scenario.py")] + \
        [(os.path.join(HERE, "mpy", n), "/mpy/" + n.replace(os.sep, "/")) for n in ("random.py", "subprocess.py", os.path.join("os", "__init__.py"),
                                                                                    os.path.join("os", "path.py"))]
fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    sys.stdout.flush()
    fail += not ok


def main():
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
        out, err = b.exec("import os\nos.chdir('/')\nimport mpy_scenario", timeout=7200)
        secs = time.time() - t0
    finally:
        q.kill()
        q.wait()
    board = out.replace("\r\n", "\n").rstrip("\n").split("\n")
    ref = subprocess.run([sys.executable, os.path.join(HERE, "mpy_scenario.py")], stdout=subprocess.PIPE, universal_newlines=True).stdout
    ref = ref.rstrip("\n").split("\n")
    cut = ref.index("== web") if "== web" in ref else len(ref)
    check(not err, "the session ran on the board in %.0f s without an error%s" % (secs, "" if not err else ": " + err.strip().split("\n")[-1]))
    same = sum(a == b for a, b in zip(ref[:cut], board[:cut]))
    diff = [(i, a, b) for i, (a, b) in enumerate(zip(ref[:cut], board[:cut])) if a != b]
    check(len(board) >= cut and not diff, "its output equals ordinary Python's: %d lines before the web part, %d identical" % (cut, same))
    for i, a, b in diff[:4]:
        print("   line %d\n     python  %s\n     esp32   %s" % (i + 1, a, b))
    t = [x for x in board[:cut] if x.startswith("$T")]
    print("      %d telemetry lines from the board; after the web marker it printed: %s" %
          (len(t), " | ".join(board[cut + 1:cut + 3])[:150] if len(board) > cut else "nothing"))
    print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
