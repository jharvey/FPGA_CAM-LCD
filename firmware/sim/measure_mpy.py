#!/usr/bin/env python3
"""Precompiled .mpy files against plain .py on the emulated ESP32: the heap the unit's modules take once imported,
and how long importing them takes.  Two fresh boards: one gets the .py files, the other the .mpy files made by
mpy-cross for the ESP32 (-march=xtensawin, so the viper code is compiled ahead too).

    python3 firmware/sim/measure_mpy.py --qemu ~/fpga-cases/esp32qemu --mpy-cross PATH/mpy-cross
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ESP = os.path.join(HERE, "..", "esp32")
sys.path.insert(0, HERE)
import esp_raw      # noqa: E402

MODS = ("fcl_bridge", "fcl_calc", "fcl_cfg", "fcl_fix", "fcl_magcal", "fcl_app", "fcl_hubpy", "fcl_usb", "fcl_web")
MEASURE = """import gc, time
gc.collect()
free0 = gc.mem_free()
t0 = time.ticks_ms()
import fcl_hubpy, fcl_usb, fcl_web
t1 = time.ticks_ms()
gc.collect()
print("RESULT", time.ticks_diff(t1, t0), free0 - gc.mem_free())
"""


def board(qdir, files, port):
    work = tempfile.mkdtemp(prefix="mpyq_", dir=qdir)
    shutil.copy(os.path.join(qdir, "flash32.bin"), os.path.join(work, "flash.bin"))
    env = dict(os.environ, LD_LIBRARY_PATH=os.path.join(qdir, "lib"))
    q = subprocess.Popen([os.path.join(qdir, "qemu", "bin", "qemu-system-xtensa"), "-nographic", "-machine", "esp32", "-m", "4M",
                          "-drive", "file=flash.bin,if=mtd,format=raw", "-serial", "tcp:127.0.0.1:%d,server=on,wait=on" % port,
                          "-monitor", "none"], cwd=work, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        b = esp_raw.Board(port)
        b.read(10)
        b.raw()
        for local, remote in files:
            b.put(local, remote)
        out, err = b.exec(MEASURE, timeout=900)
        return out, err
    finally:
        q.kill()
        q.wait()
        shutil.rmtree(work, ignore_errors=True)


def main():
    qdir = os.path.abspath(sys.argv[sys.argv.index("--qemu") + 1])
    cross = sys.argv[sys.argv.index("--mpy-cross") + 1]
    tmp = tempfile.mkdtemp()
    py, mpy = [], []
    for m in MODS:
        src = os.path.join(ESP, m + ".py")
        py.append((src, m + ".py"))
        dst = os.path.join(tmp, m + ".mpy")
        subprocess.check_call([cross, "-march=xtensawin", "-o", dst, src])
        mpy.append((dst, m + ".mpy"))
    res = {}
    for name, files, port in ((".py", py, 5557), (".mpy", mpy, 5558)):
        out, err = board(qdir, files, port)
        line = [x for x in out.splitlines() if x.startswith("RESULT")]
        res[name] = (int(line[0].split()[1]), int(line[0].split()[2])) if line else None
        print("%-5s files: %s" % (name, "import %d ms (emulated), heap taken %d bytes" % res[name] if res[name] else "ERROR " + err.strip()[-300:]))
        sys.stdout.flush()
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if all(res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
