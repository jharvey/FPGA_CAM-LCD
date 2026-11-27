#!/usr/bin/env python3
"""Check fcl_osd.v against the Python overlay (firmware/sim/fcl_osd.py), pixel for pixel, with Icarus Verilog.

    python fpga/osd/test_osd.py          (iverilog / vvp on the PATH, or in Icestudio's oss-cad-suite)
Exit code 0 = every pixel of every test frame is identical.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "firmware", "sim"))
import fcl_osd      # noqa: E402

BG = (0x58, 0x64, 0x78)


def tool(name):
    p = shutil.which(name)
    if p:
        return p
    for base in (os.path.expanduser("~/.icestudio/apio/packages/tools-oss-cad-suite/bin"),):
        for ext in ("", ".exe"):
            q = os.path.join(base, name + ext)
            if os.path.isfile(q):
                return q
    raise SystemExit(name + " not found: install Icarus Verilog or Icestudio's toolchain")


def env():
    """Icestudio's tools need their own bin and lib folders on the PATH (DLLs)"""
    e = dict(os.environ)
    base = os.path.expanduser("~/.icestudio/apio/packages/tools-oss-cad-suite")
    if os.path.isdir(base):
        e["PATH"] = os.pathsep.join([os.path.join(base, "bin"), os.path.join(base, "lib"), e.get("PATH", "")])
    return e


def frame(build, t):
    grid = fcl_osd.osd_compose(t)
    with open(os.path.join(build, "tb_text.hex"), "w") as f:
        f.write("\n".join("%02x" % ord(c) for row in grid for c in row) + "\n")
    inside = 1 if t["flags"] & fcl_osd.TF_DOT_INSIDE else 0
    on = 1 if t["overlay"] & fcl_osd.OV_DOT else 0
    subprocess.check_call([tool("vvp"), "-n", "tb.vvp", "+dx=%d" % (240 + t["dot_x"]), "+dy=%d" % (240 + t["dot_y"]),
                           "+on=%d" % on, "+inside=%d" % inside], cwd=build, stdout=subprocess.DEVNULL, env=env())
    v = open(os.path.join(build, "tb_frame.ppm")).read().split()[4:]
    hw = [(int(v[i]), int(v[i + 1]), int(v[i + 2])) for i in range(0, len(v), 3)]
    dot = (240 + t["dot_x"], 240 + t["dot_y"], bool(on), bool(inside))
    sw = [fcl_osd.overlay_pixel(x, y, BG, grid, dot) for y in range(480) for x in range(480)]
    return hw, sw


def main():
    build = os.path.join(HERE, "build")
    os.makedirs(build, exist_ok=True)
    shutil.copy(os.path.join(HERE, "font16x32.hex"), build)
    subprocess.check_call([tool("iverilog"), "-g2005", "-o", os.path.join(build, "tb.vvp"),
                           os.path.join(HERE, "fcl_osd_tb.v"), os.path.join(HERE, "fcl_osd.v")], env=env())
    base = {"heading": 123.4, "pitch": -78.0, "roll": 4.0, "alt_m": 2.96, "press_pa": 101290, "tof_mm": 1870,
            "soc1": 87, "soc2": 85, "soc3": 23, "temp1_c": 25.0, "temp2_c": 26.1, "temp3_c": 31.4, "overlay": 0x3F,
            "flags": fcl_osd.TF_TOF_VALID | fcl_osd.TF_RECORDING}
    cases = []
    for name, ch in (("all items, dot in view", {}),
                     ("level, dot on the rim, low cell", {"pitch": 2.0, "roll": -12.0, "flags": 8 | 2, "soc3": 4}),
                     ("dot over the text, empty slot", {"pitch": -82.0, "roll": 0.0, "soc2": 255}),
                     ("dot off, text only", {"overlay": 0x3E}),
                     ("dot only", {"overlay": 0x01, "pitch": -90.0, "roll": 0.0})):
        t = dict(base, **ch)
        x, y, inside = fcl_osd.down_dot(t["pitch"], t["roll"])
        t.update(dot_x=x, dot_y=y, flags=(t["flags"] & ~32) | (32 if inside else 0))
        cases.append((name, t))
    fail = 0
    for name, t in cases:
        hw, sw = frame(build, t)
        bad = sum(1 for a, b in zip(hw, sw) if a != b) + abs(len(hw) - len(sw))
        changed = sum(1 for p in sw if p != BG)
        print("%s  %-34s %d pixels, %d drawn by the overlay, %d differ" % ("PASS" if not bad and len(hw) == 230400 else "FAIL",
                                                                          name, len(hw), changed, bad))
        fail += bool(bad) or len(hw) != 230400
    print("ALL FRAMES IDENTICAL" if not fail else "MISMATCH")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
