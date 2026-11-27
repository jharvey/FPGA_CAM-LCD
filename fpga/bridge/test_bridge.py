#!/usr/bin/env python3
"""Test fcl_bridge.v in Icarus Verilog against the Python model (firmware/sim/bridge_model.py).

Both get the same command script; every frame the Verilog sends must equal the model's (time stamps apart), and the
outputs (servo pulses, LEDs, overlay writes) must be what was commanded.  Also reports the logic size from Yosys.

    python fpga/bridge/test_bridge.py [--no-synth]
"""
import os
import re
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "firmware", "sim"))
sys.path.insert(0, os.path.join(HERE, "..", "osd"))
import bridge_model as bm        # noqa: E402
import fcl_hub                   # noqa: E402
from test_osd import tool, env   # noqa: E402

fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


def script():
    """-> list of (time_us, kind, value): kind 'frame' bytes | 'btn' mask"""
    f = fcl_hub.frame
    cfg = 1 << 13 | 7 << 10 | 1 << 6 | 1 << 3 | 1
    cmds = [
        f(bm.PING, b""),
        f(bm.I2C, bytes((0x68, 1, 0, 1, 0x75))),                       # read 1 register
        f(bm.I2C, bytes((0x68, 1, 1, 0, 0x4E, 0x0F))),                 # write 1 register
        f(bm.I2C, bytes((0x68, 1, 0, 2, 0x4E))),                       # read it back, and the next one
        f(bm.I2C, bytes((0x29, 2, 0, 1, 0x01, 0x0F))),                 # 16-bit register address
        f(bm.I2C, bytes((0x29, 2, 1, 0, 0x00, 0x87, 0x40))),
        f(bm.I2C, bytes((0x29, 2, 0, 2, 0x00, 0x86))),
        f(bm.I2C, bytes((0x50, 1, 0, 3, 0x00))),                       # nobody at this address
        f(bm.I2C, bytes((0x5C, 1, 4, 0, 0x10, 1, 2, 3, 4))),           # write 4 bytes
        f(bm.I2C, bytes((0x5C, 1, 0, 16, 0x0F))),                      # read 16
        f(bm.I2C, bytes((0x1E, 0, 0, 0))),                             # address probe only
        f(bm.SERVO, struct.pack("<BH", 1, 1500)),
        f(bm.SERVO, struct.pack("<BH", 4, 2000)),
        f(bm.SERVO, struct.pack("<BH", 9, 1000)),                      # no such channel
        f(bm.OUT, bytes((0xAF, 0xA5))),             # LED0, ranger on; aux bits 1 and 3 (mask 0xA0)
        f(bm.OSD_TEXT, struct.pack("<H", 45) + b"HELLO 123"),
        f(bm.OSD_DOT, struct.pack("<HHB", 250, 380, 3)),
        f(0x2A, b"\x01\x02"),                                          # unknown command
        f(bm.PING, b"")[:-1] + b"\x00",                                # broken CRC: must be ignored
        f(bm.SCHED, struct.pack("<BHBBBBB", 0, 50, 0x68, 1, 0x00, 0x1D, 14)),      # IMU every 5 ms
        f(bm.SCHED, struct.pack("<BHBBBBB", 1, 100, 0x1E, 1, 0x00, 0x68, 6)),      # compass every 10 ms
        f(bm.SCHED, struct.pack("<BHBBBBB", 2, 200, 0x29, 2, 0x00, 0x96, 2)),      # ranger every 20 ms
        f(bm.ADC, struct.pack("<HH", 150, cfg)),                                   # ADC every 15 ms
        f(bm.INPUTS, b""),
    ]
    ev, t = [], 300
    for c in cmds:
        ev.append((t, "frame", c))
        t += 1600
    ev.append((t + 4000, "btn", 2))
    ev.append((t + 12000, "btn", 0))
    ev.append((t + 20000, "frame", f(bm.I2C, bytes((0x68, 1, 0, 1, 0x75)))))        # a command between scheduled reads
    ev.append((t + 30000, "frame", f(bm.SCHED, struct.pack("<BHBBBBB", 0, 0, 0, 0, 0, 0, 0))))   # stop slot 0
    return ev, t + 45000


def frames_of(data):
    p = fcl_hub.Parser()
    before = fcl_hub.crc_errors
    out = p.feed(data)
    return out, fcl_hub.crc_errors - before


def strip(typ, p):
    """payload without its time stamp"""
    if typ == bm.SAMPLE:
        return p[:1] + p[5:]
    if typ in (bm.ADC_DATA, bm.INPUT_DATA):
        return p[4:]
    if typ == bm.PING:
        return p[:1]
    return p


def main():
    build = os.path.join(HERE, "build")
    os.makedirs(build, exist_ok=True)
    ev, end = script()
    # ---- Verilog
    with open(os.path.join(build, "tb_stim.txt"), "w") as f:
        t = 0
        for at, kind, v in ev:
            if kind == "frame":
                f.write("D %x\n" % (at - t))
                t = at
                for b in v:
                    f.write("B %02x\n" % b)
                t += int(len(v) * 10 * 1e6 / 921600)
            else:
                f.write("D %x\n" % (at - t))
                t = at
                f.write("P %x\n" % v)
        f.write("D %x\nE 0\n" % (end - t))
    subprocess.check_call([tool("iverilog"), "-g2005", "-o", os.path.join(build, "bridge.vvp"),
                           os.path.join(HERE, "fcl_bridge_tb.v"), os.path.join(HERE, "fcl_bridge.v")], env=env())
    log = subprocess.check_output([tool("vvp"), "-n", "bridge.vvp"], cwd=build, env=env()).decode()
    hw = bytes(int(x, 16) for x in open(os.path.join(build, "tb_out.txt")).read().split())
    hw_frames, hw_bad = frames_of(hw)
    # ---- model
    m = bm.BridgeModel(bm.TbDevices())
    sw = b""
    t = 0
    for at, kind, v in ev:
        sw += m.advance(at - t)
        t = at
        if kind == "frame":
            m.feed(v)
        else:
            sw += m.advance(5000, buttons=v)        # the Verilog debounces for 5 ms
            t += 5000
    sw += m.advance(end - t)
    sw_frames, _ = frames_of(sw)

    check(hw_bad == 0 and len(hw_frames) > 40, "Verilog sent %d frames, %d with a bad CRC" % (len(hw_frames), hw_bad))
    types = sorted(set(t for t, _ in hw_frames) | set(t for t, _ in sw_frames))
    for typ in types:
        a = [strip(t, p) for t, p in hw_frames if t == typ]
        b = [strip(t, p) for t, p in sw_frames if t == typ]
        if typ == bm.SAMPLE:
            for slot in sorted(set(x[0] for x in a + b)):
                a2, b2 = [x for x in a if x[0] == slot], [x for x in b if x[0] == slot]
                n = min(len(a2), len(b2))
                check(n > 0 and abs(len(a2) - len(b2)) <= 1 and a2[:n] == b2[:n],
                      "scheduled read slot %d: %d frames (model %d), contents equal" % (slot, len(a2), len(b2)))
        else:
            n = min(len(a), len(b))
            ok = n > 0 and abs(len(a) - len(b)) <= (1 if typ == bm.ADC_DATA else 0) and a[:n] == b[:n]
            check(ok, "frames of type 0x%02X: %d (model %d), contents equal" % (typ, len(a), len(b)))
            if not ok:
                for x, y in zip(a, b):
                    if x != y:
                        print("      verilog", x.hex(), "\n      model  ", y.hex())
                        break
    # ---- specifics
    rep = [p for t, p in hw_frames if t == bm.I2C]
    check(rep[0] == bytes((0x75 * 3 + 1 & 0xFF, 0)) and rep[2] == bytes((0x0F, (0x4F * 3 + 1) & 0xFF, 0)),
          "I2C: WHO_AM_I register read, a written register reads back (0x%02X)" % rep[2][0])
    check(rep[6] == bytes((0, 0, 0, 1)), "I2C: missing device reports status 1 with zero data")
    check(rep[3] == bytes(((0x01 * 5 + 0x0F * 7 + 41) & 0xFF, 0)) and rep[5] == bytes(((0x86 * 7 + 41) & 0xFF, 0x40, 0)),
          "I2C: 16-bit register addresses (read, write, read back 0x%02X)" % rep[5][1])
    t0 = [struct.unpack("<I", p[1:5])[0] for t, p in hw_frames if t == bm.SAMPLE and p[0] == 0]
    d = [b - a for a, b in zip(t0, t0[1:])]
    check(len(d) > 4 and all(abs(x - 5000) <= 120 for x in d),
          "IMU read every 5 ms: periods %d..%d us from the time stamps" % (min(d), max(d)))
    adc = [p for t, p in hw_frames if t == bm.ADC_DATA]
    check(len(adc) >= 2 and struct.unpack("<8H", adc[-1][4:]) == tuple(ch << 12 | 0x123 for ch in range(8)),
          "ADC scan: the 8 inputs arrive in order (%s)" % " ".join("%04X" % v for v in struct.unpack("<8H", adc[-1][4:])))
    inp = [p[4:] for t, p in hw_frames if t == bm.INPUT_DATA]
    check(inp == [b"\x00\x00", b"\x02\x00", b"\x00\x00"], "buttons: asked once, then B1 pressed and released reported")
    servo = re.findall(r"SERVO (\d) (\d+)", log)
    w1 = [int(u) for c, u in servo if c == "1"]
    w4 = [int(u) for c, u in servo if c == "4"]
    check(w1 and w4 and all(abs(u - 1500) <= 1 for u in w1) and all(abs(u - 2000) <= 1 for u in w4) and
          not [c for c, u in servo if c not in "14"], "servo pulses: channel 2 %s us, channel 5 %s us, others off" % (w1[:1], w4[:1]))
    outs = re.findall(r"OUT \d+ (\d) (\d) (\d)", log)
    check(outs and outs[-1] == ("1", "1", "0"), "outputs: LED0 on, LED1 off, ranger enabled, shutdown low")
    aux = re.findall(r"AUX (\d+)", log)
    check(aux and aux[-1] == "10" and m.aux == 10, "aux outputs (video keys in the full design): bits 1 and 3 set, as in the model")
    osd = re.findall(r"OSD (\d+) (\d+)", log)
    text = "".join(chr(int(c)) for a, c in osd)
    check(text == "HELLO 123" and [int(a) for a, c in osd] == list(range(45, 54)) and "".join(m.osd[45:54]) == "HELLO 123",
          "overlay text written at cells 45..53: '%s'" % text)
    dots = re.findall(r"DOT (\d+) (\d+) (\d) (\d)", log)
    check(dots and dots[-1] == ("250", "380", "1", "1"), "overlay dot set to (250, 380), on, inside")

    if "--no-synth" not in sys.argv:
        try:
            out = subprocess.check_output([tool("yosys"), "-p", "read_verilog %s; synth_ecp5 -top fcl_bridge; stat" %
                                           os.path.join(HERE, "fcl_bridge.v").replace("\\", "/")], env=env(), stderr=subprocess.STDOUT).decode()
            cells = dict((k, int(v)) for v, k in re.findall(r"^\s+(\d+)\s+(LUT4|TRELLIS_FF|DP16KD|TRELLIS_DPR16X4|CCU2C|PFUMX|L6MUX21)\s*$", out, re.M))
            if not cells:
                cells = dict((k, int(v)) for k, v in re.findall(r"^\s+(LUT4|TRELLIS_FF|DP16KD|TRELLIS_DPR16X4|CCU2C|PFUMX|L6MUX21)\s+(\d+)\s*$", out, re.M))
            lut = cells.get("LUT4", 0) + 2 * cells.get("CCU2C", 0) + 4 * cells.get("TRELLIS_DPR16X4", 0)
            check(0 < lut < 4000, "logic size (Yosys, ECP5): about %d LUT4 (%.1f %% of the 85F's 83640), %d flip-flops, %d block RAM" %
                  (lut, 100.0 * lut / 83640, cells.get("TRELLIS_FF", 0), cells.get("DP16KD", 0)))
        except (subprocess.CalledProcessError, SystemExit) as e:
            print("NOTE  Yosys not run:", e)
    print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
