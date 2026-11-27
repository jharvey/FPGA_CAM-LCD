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
sys.path.insert(0, os.path.join(HERE, "..", "..", "firmware", "esp32"))
import fcl_osd      # noqa: E402
import fcl_calc     # noqa: E402

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


def hud_of(t):
    """(flags, a, b, c, tape) for a test case: t["hud"] = flags, the line and the tape from its heading / pitch / roll"""
    ok, a, b, c, tape = fcl_calc.hud_values(t["heading"], t["pitch"], t["roll"])
    return (t.get("hud", 0), a, b, c, tape)


def frame(build, t, vvp="tb.vvp"):
    grid = fcl_osd.osd_compose(t)
    hud = hud_of(t)
    with open(os.path.join(build, "tb_text.hex"), "w") as f:
        f.write("\n".join("%02x" % ord(c) for row in grid for c in row) + "\n")
    inside = 1 if t["flags"] & fcl_osd.TF_DOT_INSIDE else 0
    on = 1 if t["overlay"] & fcl_osd.OV_DOT else 0
    out = subprocess.check_output([tool("vvp"), "-n", vvp, "+dx=%d" % (240 + t["dot_x"]), "+dy=%d" % (240 + t["dot_y"]),
                                   "+on=%d" % on, "+inside=%d" % inside, "+hf=%d" % hud[0], "+ha=%d" % (hud[1] & 0x7FF),
                                   "+hb=%d" % (hud[2] & 0x7FF), "+hc=%d" % (hud[3] & 0x7FF), "+ht=%d" % hud[4]],
                                  cwd=build, env=env()).decode(errors="replace")
    if "sync errors" in out and "sync errors: 0" not in out:
        raise SystemExit("hs / vs are not delayed by 3 clocks: " + out.strip())
    v = open(os.path.join(build, "tb_frame.ppm")).read().split()[4:]
    hw = [(int(v[i]), int(v[i + 1]), int(v[i + 2])) for i in range(0, len(v), 3)]
    dot = (240 + t["dot_x"], 240 + t["dot_y"], bool(on), bool(inside))
    sw = [fcl_osd.overlay_pixel(x, y, BG, grid, dot, hud) for y in range(480) for x in range(480)]
    return hw, sw


def main():
    build = os.path.join(HERE, "build")
    os.makedirs(build, exist_ok=True)
    shutil.copy(os.path.join(HERE, "font16x32.hex"), build)
    subprocess.check_call([tool("iverilog"), "-g2005", "-o", os.path.join(build, "tb.vvp"),
                           os.path.join(HERE, "fcl_osd_tb.v"), os.path.join(HERE, "fcl_osd.v")], env=env())
    # the same overlay behind fcl_osd_stream.v: position recovered from de / vs, text written from another clock
    subprocess.check_call([tool("iverilog"), "-g2005", "-o", os.path.join(build, "tbs.vvp"), os.path.join(HERE, "fcl_osd_stream_tb.v"),
                           os.path.join(HERE, "fcl_osd_stream.v"), os.path.join(HERE, "fcl_osd.v")], env=env())
    base = {"heading": 123.4, "pitch": -78.0, "roll": 4.0, "alt_m": 2.96, "press_pa": 101290, "tof_mm": 1870,
            "soc1": 87, "soc2": 85, "soc3": 23, "temp1_c": 25.0, "temp2_c": 26.1, "temp3_c": 31.4, "overlay": 0x3F,
            "flags": fcl_osd.TF_TOF_VALID | fcl_osd.TF_RECORDING}
    cases = []
    for name, ch in (("all items, dot in view", {}),
                     ("level, dot on the rim, low cell", {"pitch": 2.0, "roll": -12.0, "flags": 8 | 2, "soc3": 4}),
                     ("dot over the text, empty slot", {"pitch": -82.0, "roll": 0.0, "soc2": 255}),
                     ("dot off, text only", {"overlay": 0x3E}),
                     ("dot only", {"overlay": 0x01, "pitch": -90.0, "roll": 0.0}),
                     ("graphics: reticle, horizon, compass tape", {"hud": 7, "pitch": 3.0, "roll": 12.0}),
                     ("graphics: steep horizon, text over it", {"hud": 6, "pitch": -5.0, "roll": -70.0, "heading": 7.3}),
                     ("graphics: reticle under the dot", {"hud": 1, "pitch": -89.0, "roll": 0.0}),
                     ("graphics: upright line, horizon low", {"hud": 3, "pitch": 14.0, "roll": 90.0, "heading": 359.9})):
        t = dict(base, **ch)
        x, y, inside = fcl_osd.down_dot(t["pitch"], t["roll"])
        t.update(dot_x=x, dot_y=y, flags=(t["flags"] & ~32) | (32 if inside else 0))
        cases.append((name, t))
    fail = 0
    runs = [(n, t, "tb.vvp") for n, t in cases] + [("video stream: " + n, t, "tbs.vvp") for n, t in cases[:3] + cases[5:7]]
    for name, t, vvp in runs:
        hw, sw = frame(build, t, vvp)
        bad = sum(1 for a, b in zip(hw, sw) if a != b) + abs(len(hw) - len(sw))
        changed = sum(1 for p in sw if p != BG)
        print("%s  %-48s %d pixels, %d drawn by the overlay, %d differ" % ("PASS" if not bad and len(hw) == 230400 else "FAIL",
                                                                          name, len(hw), changed, bad))
        fail += bool(bad) or len(hw) != 230400
    print("ALL FRAMES IDENTICAL" if not fail else "MISMATCH")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
