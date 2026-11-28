#!/usr/bin/env python3
"""Build the FPGA bitstreams and keep the outputs in the repository (fpga/prebuilt/), with checksums.

    python fpga/make_prebuilt.py            build both designs, run the tests, refresh fpga/prebuilt/
    python fpga/make_prebuilt.py --check    build again and compare with what is stored: tells you whether your
                                            tools produce the same bitstreams as the stored ones
    python fpga/make_prebuilt.py --no-tests skip the test logs

Stored per design: the bitstream, the pin file, the generated Verilog (camera design), nextpnr's report, and a zip
with the intermediates (Yosys netlist .json, nextpnr .config, Yosys log) so a difference can be traced stage by stage.
MANIFEST.md lists the tool versions, the source commit and a SHA-256 for every file.

Designs:  full    fpga/full (fcl_top.v): camera to TFT + LCD overlay + sensor bridge: the unit's bitstream
          bridge  fpga/bridge (fcl_bridge_top.v): the sensor bridge alone, for bring-up
          camera  fpga/CameraToTFTSobel_FCL.ice: camera to TFT with the Sobel view alone (no bridge, no overlay)
"""
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "prebuilt")
sys.path.insert(0, os.path.join(HERE, "osd"))
from test_osd import tool, env        # noqa: E402

TESTS = [("firmware/sim/test_usb.py", []), ("firmware/sim/test_filter.py", []), ("firmware/sim/test_magcal.py", []),
         ("firmware/sim/test_app.py", []), ("firmware/sim/test_web.py", []), ("firmware/sim/test_calibrate.py", []),
         ("firmware/sim/test_tools.py", []), ("firmware/sim/test_lessons.py", []), ("firmware/sim/test_mpy.py", []),
         ("fpga/bridge/test_bridge.py", []), ("fpga/osd/test_osd.py", []), ("fpga/check_pins.py", [])]
# fpga/full/test_full.py (the whole design, about an hour) is run by hand; its output is kept as fpga/prebuilt/test_full.txt


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)
    return r.returncode, r.stdout.decode(errors="replace")


def build(work):
    """-> {design: {name: path}} of fresh outputs"""
    code, out = run([sys.executable, "fpga/bridge/build_bridge.py"])
    if code:
        raise SystemExit("bridge build failed:\n" + out[-2000:])
    b = os.path.join(HERE, "bridge", "build")
    cam = os.path.join(work, "camera")
    code, out2 = run([sys.executable, "fpga/build.py", "--out", cam])
    if code:
        raise SystemExit("camera build failed:\n" + out2[-2000:])
    open(os.path.join(cam, "build_summary.txt"), "w", newline="\n").write(
        "\n".join(x for x in out2.replace("\r\n", "\n").split("\n") if x.startswith("clock ") or "TRELLIS_" in x) + "\n")
    full = os.path.join(work, "full")
    code, out3 = run([sys.executable, "fpga/full/build_full.py", "--out", full])
    if code and not os.path.isfile(os.path.join(full, "fcl_full.bit")):
        raise SystemExit("full build failed:\n" + out3[-2000:])
    open(os.path.join(full, "build_summary.txt"), "w", newline="\n").write(out3.replace("\r\n", "\n").replace(work, "<build>"))
    f87 = os.path.join(work, "full87")
    code, out4 = run([sys.executable, "fpga/full/build_full.py", "--mem-mhz", "87.5", "--out", f87])
    if code and not os.path.isfile(os.path.join(f87, "fcl_full.bit")):
        raise SystemExit("full build at 87.5 MHz failed:\n" + out4[-2000:])
    shutil.copyfile(os.path.join(f87, "fcl_full.bit"), os.path.join(f87, "fcl_full_87.bit"))
    open(os.path.join(f87, "build_summary.txt"), "w", newline="\n").write(out4.replace("\r\n", "\n").replace(work, "<build>"))
    return {
        "full87": {"fcl_full_87.bit": os.path.join(f87, "fcl_full_87.bit"), "nextpnr.log": os.path.join(f87, "nextpnr.log"),
                   "build_summary.txt": os.path.join(f87, "build_summary.txt"),
                   "_zip": {"fcl_full.json": os.path.join(f87, "fcl_full.json"), "fcl_full.config": os.path.join(f87, "fcl_full.config")}},
        "full": {"fcl_full.bit": os.path.join(full, "fcl_full.bit"), "fcl_top.lpf": os.path.join(full, "fcl_top.lpf"),
                 "main.v": os.path.join(full, "main.v"), "fcl_cam.v": os.path.join(full, "fcl_cam.v"),
                 "nextpnr.log": os.path.join(full, "nextpnr.log"), "build_summary.txt": os.path.join(full, "build_summary.txt"),
                 "_zip": {"fcl_full.json": os.path.join(full, "fcl_full.json"), "fcl_full.config": os.path.join(full, "fcl_full.config"),
                          "yosys.log": os.path.join(full, "yosys.log")}},
        "bridge": {"fcl_bridge.bit": os.path.join(b, "fcl_bridge.bit"), "fcl_bridge_top.lpf": os.path.join(b, "fcl_bridge_top.lpf"),
                   "nextpnr.log": os.path.join(b, "nextpnr.log"),
                   "_zip": {"fcl_bridge.json": os.path.join(b, "fcl_bridge.json"), "fcl_bridge.config": os.path.join(b, "fcl_bridge.config"),
                            "yosys.log": os.path.join(b, "yosys.log")}},
        "camera": {"main.bit": os.path.join(cam, "main.bit"), "main.lpf": os.path.join(cam, "main.lpf"), "main.v": os.path.join(cam, "main.v"),
                   "nextpnr.log": os.path.join(cam, "nextpnr.log"), "build_summary.txt": os.path.join(cam, "build_summary.txt"),
                   "_zip": {"main.json": os.path.join(cam, "main.json"), "main.config": os.path.join(cam, "main.config"),
                            "yosys.log": os.path.join(cam, "yosys.log")}},
    }


def versions():
    v = []
    for t, arg in (("yosys", "-V"), ("nextpnr-ecp5", "--version"), ("ecppack", "--version"), ("iverilog", "-V")):
        try:
            o = subprocess.run([tool(t), arg], env=env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode(errors="replace")
            v.append((t, o.strip().splitlines()[0].strip('" ')))
        except (SystemExit, OSError, IndexError):
            v.append((t, "not found"))
    v.append(("python", sys.version.split()[0]))
    return v


def main():
    check = "--check" in sys.argv
    work = tempfile.mkdtemp(prefix="fcl_prebuilt_")
    fresh = build(work)
    hashes = {}
    for design, files in fresh.items():
        for name, path in list(files.items()) + list(files["_zip"].items()):
            if name != "_zip":
                hashes["%s/%s" % (design, name)] = sha(path)
    if check:
        stored = {}
        for line in open(os.path.join(OUT, "MANIFEST.md"), encoding="utf-8"):
            p = [x.strip(" `") for x in line.strip().strip("|").split("|")]
            if len(p) == 3 and len(p[2]) == 64:
                stored[p[0]] = p[2]
        bad = 0
        for k in sorted(hashes):
            if k.endswith(".log") or k.endswith("build_summary.txt"):
                continue                                   # logs carry run times and paths
            same = stored.get(k) == hashes[k]
            print("%s  %s" % ("SAME     " if same else "DIFFERENT", k))
            bad += not same
        print("Your build matches the stored one." if not bad else
              "%d file(s) differ. Compare the tool versions in fpga/prebuilt/MANIFEST.md with yours, then the stages in order:\n"
              "  main.v (camera only: Icestudio's code generator) -> .json (Yosys) -> .config (nextpnr) -> .bit (ecppack)." % bad)
        shutil.rmtree(work, ignore_errors=True)
        return 1 if bad else 0

    for design, files in fresh.items():
        d = os.path.join(OUT, design)
        os.makedirs(d, exist_ok=True)
        for name, path in files.items():
            if name != "_zip":
                shutil.copyfile(path, os.path.join(d, name))
        with zipfile.ZipFile(os.path.join(d, "intermediates.zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, path in sorted(files["_zip"].items()):
                zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))       # fixed date: the zip itself repeats
                zi.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(zi, open(path, "rb").read())
    logs = []
    if "--no-tests" not in sys.argv:
        with open(os.path.join(OUT, "test_results.txt"), "w", encoding="utf-8", newline="\n") as f:
            for t, args in TESTS:
                code, out = run([sys.executable, t] + args, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                f.write("===== python %s   (exit code %d)\n%s\n" % (t, code, out.replace("\r\n", "\n")))
                logs.append((t, code, out.strip().splitlines()[-1] if out.strip() else ""))
                print(t, "->", logs[-1][2])
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, stdout=subprocess.PIPE).stdout.decode().strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "-uno", "--", "fpga", "firmware", ":(exclude)fpga/prebuilt"], cwd=ROOT, stdout=subprocess.PIPE).stdout.decode().strip()
    with open(os.path.join(OUT, "MANIFEST.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Stored build outputs\n\n")
        f.write("Written by `python fpga/make_prebuilt.py` on %s. Check your own build against these with "
                "`python fpga/make_prebuilt.py --check`.\n\n" % datetime.date.today().isoformat())
        f.write("Built from commit `%s`%s.\n\n" % (commit, " plus uncommitted changes in fpga/ or firmware/" if dirty else ""))
        f.write("| Design | Bitstream | What it is |\n|---|---|---|\n")
        f.write("| full | `full/fcl_full.bit` | camera to TFT with the LCD overlay and the sensor bridge (`fpga/full/fcl_top.v`): the bitstream the unit runs. Timing and size: `full/build_summary.txt`. |\n")
        f.write("| full87 | `full87/fcl_full_87.bit` | the same with the memory clock at 87.5 MHz instead of 100 (`build_full.py --mem-mhz 87.5`): the fallback if the first board shows wrong pixels. |\n")
        f.write("| bridge | `bridge/fcl_bridge.bit` | the sensor bridge alone (`fpga/bridge/fcl_bridge_top.v`): sensors, ADC, buttons, servos from the ESP32. No camera or LCD. For first bring-up. |\n")
        f.write("| camera | `camera/main.bit` | camera to TFT with the Sobel view alone (`fpga/CameraToTFTSobel_FCL.ice`): no bridge, no overlay. |\n\n")
        f.write("None has been loaded into a real board. nextpnr runs with a fixed seed, so the same tool versions should give the same files.\n\n")
        f.write("## Timing\n\nFrom nextpnr, after routing. A FAIL is the tool's estimate for the slowest path, not a measurement.\n\n"
                "| Design | Clock | Result |\n|---|---|---|\n")
        for design in ("full", "full87", "camera"):
            for line in open(fresh[design]["build_summary.txt"]):
                if line.startswith("clock "):
                    p = line.split()
                    f.write("| %s | `%s` | %s |\n" % (design, p[1], " ".join(p[2:])))
        fails = [d for d in ("full", "full87", "camera") for line in open(fresh[d]["build_summary.txt"]) if line.startswith("clock ") and "FAIL" in line]
        f.write("\n%s Builds before 2026-11-27 did not tell nextpnr the clock frequencies, so it checked every clock against "
                "12 MHz; with the frequencies given, the camera design's memory clock failed at 142.9 MHz, and the project was "
                "changed (`fpga/IO_REMAP.md`, section Clocks).\n\n" %
                ("**A clock does not meet timing in: %s.**" % ", ".join(sorted(set(fails))) if fails else
                 "All clocks pass by this estimate; the memory clock (100 MHz) has the smallest margin."))
        full_sim = os.path.join(OUT, "test_full.txt")
        if os.path.exists(full_sim):
            last = [x for x in open(full_sim, encoding="utf-8").read().strip().split("\n") if x.strip()]
            f.write("## Whole-design simulation\n\n`python fpga/full/test_full.py` takes about an hour and is run by hand, not by this "
                    "script. Its last stored output is `test_full.txt`: first line `%s`, last line `%s`. Check that the commit named "
                    "there is the one these bitstreams were built from, or that no FPGA source changed in between.\n\n" % (last[0], last[-1]))
        f.write("## Tools\n\n| Tool | Version |\n|---|---|\n")
        for t, v in versions():
            f.write("| %s | %s |\n" % (t, v))
        f.write("\n## Files\n\n`intermediates.zip` holds the Yosys netlist (.json), the nextpnr result (.config) and the Yosys log; "
                "their checksums below are of the files inside the zip.\n\n| File | Bytes | SHA-256 |\n|---|---|---|\n")
        for design, files in fresh.items():
            for name, path in list(files.items()) + list(files["_zip"].items()):
                if name != "_zip":
                    f.write("| `%s/%s` | %d | `%s` |\n" % (design, name, os.path.getsize(path), hashes["%s/%s" % (design, name)]))
        if logs:
            f.write("\n## Tests at build time\n\nFull output in `test_results.txt`.\n\n| Test | Exit code | Last line |\n|---|---|---|\n")
            for t, code, last in logs:
                f.write("| `%s` | %d | %s |\n" % (t, code, last))
    shutil.rmtree(work, ignore_errors=True)
    print("stored in", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
