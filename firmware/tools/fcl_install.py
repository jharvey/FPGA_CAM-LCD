#!/usr/bin/env python3
"""Set up a unit's ESP32 over USB in one go: the unit's files, your Wi-Fi and PIN, the FPGA bitstream, a restart.

    python firmware/tools/fcl_install.py --port COM7
    python firmware/tools/fcl_install.py --port COM7 --wifi HomeNet secret --pin 1234
    python firmware/tools/fcl_install.py --port COM7 --bit fpga/prebuilt/full/fcl_full.bit --flash
    python firmware/tools/fcl_install.py --port COM7 --firmware ESP32_GENERIC_S3-20241129-v1.24.1.bin   (fresh ESP32)

Needs pyserial (pip install pyserial); --firmware also needs esptool (pip install esptool).

Steps, each reported:
  1. --firmware only: erase the ESP32's flash and write MicroPython (esptool; hold BOOT and tap RESET first if the
     port does not answer).  This erases everything on the ESP32.
  2. stop the unit's USB stream if it runs, and go to MicroPython's raw REPL;
  3. copy every .py file of firmware/esp32 (and --user as fcl_user.py), each checked by its length on arrival;
  4. --wifi: write wifiman.conf;  --pin: write webpin.txt;
  5. --bit: copy the bitstream; --flash: write it into the FPGA's configuration memory (about a minute; it stays
     after power-off), otherwise load it until the next power-off;
  6. restart the ESP32 (main.py starts the unit's software) and wait for its first line.
Files on the ESP32 that are not in firmware/esp32 (calibration values, logs) are left alone.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ESP = os.path.join(HERE, "..", "esp32")
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
import esp_raw      # noqa: E402

SKIP = ("fcl_user_example.py",)                      # an example, not part of the unit


def files(user=None):
    out = [(os.path.join(ESP, n), n) for n in sorted(os.listdir(ESP)) if n.endswith(".py") and n not in SKIP]
    if user:
        out.append((user, "fcl_user.py"))
    return out


def install(port, firmware=None, wifi=None, pin=None, bit=None, flash=False, user=None, say=print, wait_boot=20):
    """-> True when every step worked"""
    if firmware:
        say("1. MicroPython: erasing the ESP32 and writing %s" % os.path.basename(firmware))
        for args in (["erase_flash"], ["write_flash", "0", firmware]):
            r = subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32s3", "--port", port] + args)
            if r.returncode:
                say("   esptool failed (exit %d): hold BOOT, tap RESET, release BOOT, and try again" % r.returncode)
                return False
        time.sleep(3)
    b = esp_raw.Board(port)
    say("2. raw REPL")
    b.read(1.0)
    b.raw()
    out, err = b.exec("import sys, gc, os\nprint(sys.version.split(';')[1].strip() + '|' + str(gc.mem_free()) + '|' + "
                      "str(os.statvfs('/')[0] * os.statvfs('/')[3]))")
    parts = out.strip().split("|")
    say("   %s, %s bytes free in the heap, %s bytes free on the flash" % tuple(parts) if not err and len(parts) == 3 else "   " + (err or out))
    todo = files(user)
    say("3. copying %d files" % len(todo))
    t0 = time.time()
    for local, remote in todo:
        b.put(local, remote)
    say("   done in %.0f s" % (time.time() - t0))
    step = 4
    if wifi:
        b.exec("f=open('wifiman.conf','w')\nf.write(%r)\nf.close()" % ("%s:%s\n" % tuple(wifi)))
        say("%d. Wi-Fi: wifiman.conf written for %s" % (step, wifi[0]))
    if pin:
        if not (pin.isdigit() and 4 <= len(pin) <= 8):
            say("%d. PIN: must be 4 to 8 digits; not written" % step)
            return False
        b.exec("f=open('webpin.txt','w')\nf.write(%r)\nf.close()" % pin)
        say("%d. PIN for the phone page written" % step)
    if bit:
        say("5. bitstream: copying %s (%d bytes)" % (os.path.basename(bit), os.path.getsize(bit)))
        b.put(bit, "fcl_full.bit")
        out, err = b.exec("import ecp5\nprint(ecp5.%s('fcl_full.bit'))" % ("flash" if flash else "prog"), timeout=300)
        ok = not err and "True" in out
        say("   %s: %s" % ("written into the FPGA's configuration memory" if flash else "loaded", "ok" if ok else (err or out).strip()[-200:]))
        if not ok:
            return False
    say("6. restarting")
    try:
        b.exec("import machine\nmachine.reset()", timeout=3)
    except (TimeoutError, OSError):
        pass                                          # the board went away while answering: that is the restart
    seen = b.read(wait_boot).decode(errors="replace")
    b.close()
    started = "$I,FCL USB protocol" in seen
    say("   the unit's software %s" % ("started: " + [x for x in seen.splitlines() if x.startswith("$I,")][0] if started else
                                     "did not report within %d s; last lines: %s" % (wait_boot, " | ".join(seen.splitlines()[-3:]))))
    return started


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", required=True, help="the unit's USB serial port (or a TCP port number of the emulator)")
    ap.add_argument("--firmware", help="MicroPython .bin to write first (erases the ESP32)")
    ap.add_argument("--wifi", nargs=2, metavar=("NAME", "PASSWORD"))
    ap.add_argument("--pin", help="PIN for the phone page, 4 to 8 digits")
    ap.add_argument("--bit", help="FPGA bitstream to copy and load")
    ap.add_argument("--flash", action="store_true", help="with --bit: write it into the FPGA's configuration memory")
    ap.add_argument("--user", help="a page of your own, stored as fcl_user.py")
    a = ap.parse_args()
    return 0 if install(a.port, a.firmware, a.wifi, a.pin, a.bit, a.flash, a.user) else 1


if __name__ == "__main__":
    sys.exit(main())
