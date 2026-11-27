#!/usr/bin/env python3
"""Build the FPGA bitstreams and keep the outputs in the repository (fpga/prebuilt/), with checksums.

    python fpga/make_prebuilt.py            build both designs, run the tests, refresh fpga/prebuilt/
    python fpga/make_prebuilt.py --check    build again and compare with what is stored: tells you whether your
                                            tools produce the same bitstreams as the stored ones
    python fpga/make_prebuilt.py --no-tests skip the test logs

Stored per design: the bitstream, the pin file, the generated Verilog (camera design), nextpnr's report, and a zip
with the intermediates (Yosys netlist .json, nextpnr .config, Yosys log) so a difference can be traced stage by stage.
MANIFEST.md lists the tool versions, the source commit and a SHA-256 for every file.

Designs:  bridge  fpga/bridge (fcl_bridge_top.v): the sensor bridge alone, for bring-up
          camera  fpga/CameraToTFTSobel_FCL.ice: camera to TFT with the Sobel view (no bridge, no overlay yet)
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
         ("fpga/bridge/test_bridge.py", []), ("fpga/osd/test_osd.py", [])]


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
    return {
        "bridge": {"fcl_bridge.bit": os.path.join(b, "fcl_bridge.bit"), "fcl_bridge_top.lpf": os.path.join(b, "fcl_bridge_top.lpf"),
                   "nextpnr.log": os.path.join(b, "nextpnr.log"),
                   "_zip": {"fcl_bridge.json": os.path.join(b, "fcl_bridge.json"), "fcl_bridge.config": os.path.join(b, "fcl_bridge.config"),
                            "yosys.log": os.path.join(b, "yosys.log")}},
        "camera": {"main.bit": os.path.join(cam, "main.bit"), "main.lpf": os.path.join(cam, "main.lpf"), "main.v": os.path.join(cam, "main.v"),
                   "nextpnr.log": os.path.join(cam, "nextpnr.log"),
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
            if k.endswith(".log"):
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
    dirty = subprocess.run(["git", "status", "--porcelain", "-uno", "--", "fpga", "firmware"], cwd=ROOT, stdout=subprocess.PIPE).stdout.decode().strip()
    with open(os.path.join(OUT, "MANIFEST.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Stored build outputs\n\n")
        f.write("Written by `python fpga/make_prebuilt.py` on %s. Check your own build against these with "
                "`python fpga/make_prebuilt.py --check`.\n\n" % datetime.date.today().isoformat())
        f.write("Built from commit `%s`%s.\n\n" % (commit, " plus uncommitted changes in fpga/ or firmware/" if dirty else ""))
        f.write("| Design | Bitstream | What it is |\n|---|---|---|\n")
        f.write("| bridge | `bridge/fcl_bridge.bit` | the sensor bridge alone (`fpga/bridge/fcl_bridge_top.v`): sensors, ADC, buttons, servos from the ESP32. No camera or LCD. For first bring-up. |\n")
        f.write("| camera | `camera/main.bit` | camera to TFT with the Sobel view (`fpga/CameraToTFTSobel_FCL.ice`). No bridge and no overlay yet. |\n\n")
        f.write("Neither has been loaded into a real board. nextpnr runs with a fixed seed, so the same tool versions should give the same files.\n\n")
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
