#!/usr/bin/env python3
"""The whole FPGA design in one simulation: fcl_top.v (camera design + overlay + bridge) in Icarus Verilog, with
a camera model in front, an SDRAM model beside it and a script playing the ESP32 on the UART.

    python fpga/full/test_full.py [--ms N] [--keep]        75 minutes or more; exit code 0 = all checks pass
    python fpga/full/test_full.py --analyse                check the files of the last run again (kept with --keep)

What is checked
    clocks     the pixel clock, SDRAM clock and camera clock as the design really makes them
    camera     the 78 set-up registers arrive at the camera model, in order, as in the project's list
    panel      the ST7701S set-up bytes are sent; every picture is 480 x 480 with the expected sync
    picture    camera pixels -> SDRAM -> TFT pins, every pixel of a whole picture, with the overlay text, the
               graphics (reticle, horizon, compass tape) and the down dot on top (the same pixel rules as
               fpga/osd/test_osd.py)
    edges      the view key, pressed by the bridge on the ESP32's command, switches to the edge picture
    bridge     answers on the UART while the video runs: ping, I2C read, scheduled samples, a button report

What is changed for the simulation (in a copy, main_sim.v; nothing else is touched)
    the camera design's start-up waits (0.5 s before and after the camera set-up, the panel's reset and sleep-out
    waits, 120 test-pattern frames -> 2) are shortened, as they would take hours to simulate; fcl_top's 42 ms
    power-on reset is 10 us (its POR_BITS parameter).  The camera's register list is rewritten as plain
    hexadecimal numbers: the project writes it as 16'h12_80; with comments, which Yosys reads (it skips what is
    not a hex digit, so that entry becomes 16_12_80 and the design uses the low 16 bits) and Icarus Verilog does not.
    Two outputs are written as one expression each instead of being set inside a larger always @* block: the
    camera bus's "ack" and the SDRAM controller's "ready".  Same values at every clock; but as written, each of
    those blocks first clears the signal and then sets it, the block that reads it answers with a signal the first
    block reads, and an event-driven simulator goes round that for ever at one instant.  Hardware has no such loop.
    The test bench also drives the two bidirectional pins at their buffers (see fcl_top_tb.v).
What it cannot show: timing (the models have no delays), the real camera, panel and SDRAM, and the clock speeds
the FPGA can reach.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FPGA = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FPGA, "..", "firmware", "sim"))
sys.path.insert(0, os.path.join(FPGA, "..", "firmware", "esp32"))
sys.path.insert(0, os.path.join(FPGA, "osd"))
sys.path.insert(0, HERE)
import bridge_model as bm        # noqa: E402
import fcl_hub                   # noqa: E402
import fcl_osd                   # noqa: E402
import build_full                # noqa: E402
from test_osd import tool, env   # noqa: E402

SPEEDUPS = (        # (text in main.v, replacement, how often it must occur, what it is)
    ("delay_q[26]", "delay_q[12]", 2, "0.47 s before and after the camera set-up -> 29 us"),
    ("delay_q[16]", "delay_q[11]", 1, "0.46 ms between camera registers -> 14 us"),
    ("localparam [7:0] TEST_FRAMES = 8'd120;", "localparam [7:0] TEST_FRAMES = 8'd2;", 1, "120 test-pattern frames -> 2"),
    ("RESET_LOW_TICKS  = 24'd1800000;", "RESET_LOW_TICKS  = 24'd1800;", 1, "panel reset low, 1/1000"),
    ("RESET_WAIT_TICKS = 24'd360000;", "RESET_WAIT_TICKS = 24'd360;", 1, "panel reset wait, 1/1000"),
    ("DELAY_120MS      = 24'd2160000;", "DELAY_120MS      = 24'd2160;", 1, "panel sleep-out wait, 1/1000"),
    ("DELAY_10MS       = 24'd180000;", "DELAY_10MS       = 24'd180;", 1, "panel 10 ms waits, 1/1000"),
    ("assign ack_q=ack;", "assign ack_q=(state_q==ack_servant && scl_hi)? {1'b1,!sda_in}:2'b00;", 1, "ack as one expression"),
    ("assign ready_q=ready;", "assign ready_q=(state_q==idle) && !rw_en_q;", 1, "ready as one expression"),
)
PALETTE = (0xF800, 0x07E0, 0x001F, 0xFFFF, 0x0000, 0xFFE0, 0xF81F, 0x07FF, 0x8410, 0x4208, 0xA145, 0x39C7, 0x5ACB, 0xC618,
           0x2D7F, 0xD2A6)                                  # as in sim_models.v
TEXT = {1: "FULL DESIGN", 5: "CAMERA + OVERLAY + BRIDGE", 9: "0123456789 %+-./:", 13: "ROW 13"}
DOT = (300, 200, 1, 1)
HUD = (7, 175, 481, -160, 10)                               # reticle, horizon (roll 20, pitch 5 at 60 deg), compass tape
T_KEY_US = 78000                                            # the view key
fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    sys.stdout.flush()
    fail += not ok


def cam_word(x, y):
    return PALETTE[(3 * (x // 40) + 5 * (y // 40)) % 16]


def cam_rgb6(w):
    r, g, b = w >> 11, w >> 5 & 63, w & 31
    return (r << 1 | r >> 4, g, b << 1 | b >> 4)


def test_rgb6(x, y):
    if x == 240 or y == 240:
        return (0, 0, 0)
    return ((63, 0, 0), (0, 63, 0), (0, 0, 63), (63, 63, 63))[(x >= 240) + 2 * (y >= 240)]


def overlay6(x, y, rgb, grid, dot):
    """fcl_osd.v with BITS = 6: the pixel model of firmware/sim/fcl_osd.py with 63 as white"""
    return fcl_osd.overlay_pixel(x, y, rgb, grid, dot, HUD, white=63)


def plain(x, y, grid, dot):
    """this pixel shows the picture itself: no text cell, no dot, no graphics"""
    return grid[y >> 5][x >> 4] == " " and (x - dot[0]) ** 2 + (y - dot[1]) ** 2 > 169 and \
        fcl_osd.hud_pixel(x, y, (1, 2, 3), HUD, 63) == (1, 2, 3)


def luma(w):
    """brightness of an RGB565 colour, 0..255"""
    r, g, b = (w >> 11) << 3, ((w >> 5) & 63) << 2, (w & 31) << 3
    return (77 * r + 150 * g + 29 * b) >> 8


def edge_check(px, grid, dot, shift):
    """The edge view is a thresholded edge filter, so a border between two blocks must be white along its length when
    their brightness differs a lot, and black when it differs little; and nothing away from a border may be white.
    -> (ok, text) for check().  Lines are looked for 1..4 columns right of a vertical border (the filter's output is
    2 pixels late) and 2 rows either side of a horizontal one."""
    white = [p == (63, 63, 63) for p in px]
    blk = lambda bx, by: luma(PALETTE[(3 * bx + 5 * by) % 16])          # noqa: E731
    o = 80 + (shift or 0)                                                # camera column of panel column 0
    seg = []                                                             # (brightness difference, part of the border lit)
    for k in range(3, 14):                                               # vertical borders at camera column 40 k
        for by in range(12):
            xs = [40 * k - o + d for d in range(1, 5)]
            ys = [y for y in range(by * 40 + 3, by * 40 + 37) if all(plain(x, y, grid, dot) for x in xs)]
            if len(ys) >= 10:
                seg.append((abs(blk(k - 1, by) - blk(k, by)), sum(any(white[y * 480 + x] for x in xs) for y in ys) / len(ys)))
    for j in range(1, 12):                                               # horizontal borders at row 40 j
        for bx in range(2, 14):
            ys = [40 * j + d for d in range(-2, 3)]
            xs = [x for x in range(bx * 40 - o + 3, bx * 40 - o + 37) if 0 <= x < 480 and all(plain(x, y, grid, dot) for y in ys)]
            if len(xs) >= 10:
                seg.append((abs(blk(bx, j - 1) - blk(bx, j)), sum(any(white[y * 480 + x] for y in ys) for x in xs) / len(xs)))
    lit = [d for d, f in seg if f >= 0.9]
    dark = [d for d, f in seg if f <= 0.1]
    unclear = len(seg) - len(lit) - len(dark)
    stray = 0
    for y in range(480):
        for x in range(480):
            if white[y * 480 + x] and plain(x, y, grid, dot):
                cx, cy = (x + o) % 40, y % 40
                if not (1 <= cx <= 4 or min(cy, 40 - cy) <= 2):
                    stray += 1
    ok = lit and dark and not unclear and min(lit) > max(dark) and stray == 0
    return ok, ("edge picture: %d block borders white along their length (brightness difference %d or more), %d black (%d or less), "
                "%d half lit; %d white pixels away from a border" % (len(lit), min(lit) if lit else -1, len(dark),
                                                                     max(dark) if dark else -1, unclear, stray))


def stimulus(end_us):
    f = fcl_hub.frame
    grid = [" " * 30] * 15
    ev = [(300, f(bm.PING, b"")), (900, f(bm.OUT, bytes((0x81, 0x81)))), (1500, f(bm.I2C, bytes((0x68, 1, 0, 1, 0x75))))]
    t = 2500
    for row, s in sorted(TEXT.items()):
        s = s.center(30)
        grid[row] = s
        ev.append((t, f(bm.OSD_TEXT, struct.pack("<H", row * 30) + s.encode())))
        t += 1500
    ev.append((t, f(bm.OSD_DOT, struct.pack("<HHB", DOT[0], DOT[1], 3))))
    ev.append((t + 800, f(bm.OSD_HUD, struct.pack("<BhhhB", *HUD))))
    ev.append((t + 1500, f(bm.SCHED, struct.pack("<BHBBBBB", 0, 100, 0x68, 1, 0x00, 0x1D, 14))))        # every 10 ms
    ev.append((t + 3000, f(bm.INPUTS, b"")))
    ev.append((30000, "P 4"))                                # B2 down for 12 ms (the bridge debounces for 5)
    ev.append((42000, "P 0"))
    ev.append((T_KEY_US, f(bm.OUT, bytes((0x10, 0x10)))))    # the view key, as the hub presses it
    ev.append((T_KEY_US + 4000, f(bm.OUT, bytes((0x10, 0x00)))))
    lines, now = [], 0
    for t, what in sorted((e for e in ev if e[0] < end_us), key=lambda e: e[0]):
        lines.append("D %x" % (t - now))
        now = t
        if isinstance(what, str):
            lines.append(what)
        else:
            lines += ["B %02x" % b for b in what]
            now += int(len(what) * 10e6 / 921600) + 1
    lines += ["D %x" % (end_us - now), "E 0"]
    return lines, grid


def read_frame(path):
    out = []
    for line in open(path):
        try:
            v = int(line, 16)
            out.append((v >> 12, v >> 6 & 63, v & 63))
        except ValueError:
            out.append(None)                                 # an undefined pin
    return out


def main():
    end_ms = int(sys.argv[sys.argv.index("--ms") + 1]) if "--ms" in sys.argv else 113
    build = os.path.join(HERE, "sim")
    os.makedirs(build, exist_ok=True)
    again = "--analyse" in sys.argv
    for n in os.listdir(build):
        if n.startswith("tb_") and not again:
            os.remove(os.path.join(build, n))
    r = subprocess.run([sys.executable, os.path.join(FPGA, "build.py"), "--gen-only", "--out", build],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode:
        raise SystemExit("code generation failed:\n" + r.stdout.decode(errors="replace")[-2000:])
    build_full.write_sources(build)
    shutil.copy(os.path.join(FPGA, "osd", "font16x32.hex"), build)
    v = open(os.path.join(build, "main.v"), encoding="utf-8").read()
    for a, b, n, _ in SPEEDUPS:
        if v.count(a) != n:
            raise SystemExit("main.v has changed: '%s' occurs %d times, expected %d" % (a, v.count(a), n))
        v = v.replace(a, b)
    open(os.path.join(build, "main_sim.v"), "w", encoding="utf-8", newline="\n").write(v)
    listed = re.findall(r"16'h([0-9a-fA-F]{2})_([0-9a-fA-F]{2})", open(os.path.join(build, "v15a1ce.list")).read())
    want = [(int(a, 16), int(b, 16)) for a, b in listed][:78]
    if not again:
        open(os.path.join(build, "v15a1ce.list"), "w", newline="\n").write("".join("16%s%s\n" % ab for ab in listed))  # as Yosys reads it
    stim, grid = stimulus(end_ms * 1000)
    if again:
        out = open(os.path.join(build, "tb_stdout.txt")).read()
        return analyse(build, out, grid, want, end_ms)
    open(os.path.join(build, "tb_stim.txt"), "w", newline="\n").write("\n".join(stim) + "\n")
    src = [os.path.join(HERE, "fcl_top_tb.v"), os.path.join(HERE, "sim_models.v"), "main_sim.v", "fcl_cam.v",
           os.path.join(HERE, "fcl_top.v"), os.path.join(FPGA, "bridge", "fcl_bridge.v"), os.path.join(FPGA, "osd", "fcl_osd.v"),
           os.path.join(FPGA, "osd", "fcl_osd_stream.v")]
    subprocess.check_call([tool("iverilog"), "-g2005", "-o", "tb_full.vvp"] + src, cwd=build, env=env())
    t0 = time.time()
    out = subprocess.run([tool("vvp"), "-n", "tb_full.vvp"], cwd=build, env=env(), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT).stdout.decode(errors="replace").replace("\r\n", "\n")
    open(os.path.join(build, "tb_stdout.txt"), "w", newline="\n").write(out)
    print("simulated %d ms in %.0f s" % (end_ms, time.time() - t0))
    sys.stdout.flush()
    return analyse(build, out, grid, want, end_ms)


def analyse(build, out, grid, want, end_ms):

    # ---- clocks
    m = re.search(r"CLOCKS us (\d+) pix (\d+) sdram (\d+) xclk (\d+) lcd_pclk (\d+)", out)
    if not m:
        print(out[-3000:])
        raise SystemExit("the simulation did not finish")
    us, pix, ram, xclk, _ = [int(x) for x in m.groups()]
    f_pix, f_ram, f_x = pix / us, ram / us, xclk / us
    print("clocks: pixel %.2f MHz, SDRAM %.2f MHz, camera %.2f MHz" % (f_pix, f_ram, f_x))
    check(abs(f_ram - 100.0) < 0.5 and abs(f_x - 25.0) < 0.1 and abs(f_pix - 17.857) < 0.1,
          "pixel clock 17.86 MHz, SDRAM clock 100 MHz, camera clock 25 MHz")
    frames = [dict(zip(("n", "pixels", "lines", "hsync", "at", "period"), [int(x) for x in g])) for g in
              re.findall(r"FRAME (\d+) pixels (\d+) lines (\d+) hsync (\d+) at_us (\d+) period_us (\d+)", out)]
    rate = 1e6 / frames[-1]["period"] if frames else 0
    print("pictures: %d, one every %.1f ms (%.1f per second)" % (len(frames), frames[-1]["period"] / 1000.0 if frames else 0, rate))

    # ---- camera set-up
    got = [tuple(int(x, 16) for x in line.split()) for line in open(os.path.join(build, "tb_sccb.txt")) if line.strip()]
    check(got == want and len(got) == 78, "camera set-up: %d register writes reach the camera model, equal to the project's list" % len(got))

    # ---- panel set-up
    spi = [tuple(int(x, 16) for x in line.split()) for line in open(os.path.join(build, "tb_spi.txt")) if line.strip()]
    cmds = [b for dc, b in spi if dc == 0]
    check(len(spi) > 100 and 0x11 in cmds and 0x29 in cmds and cmds.index(0x11) < cmds.index(0x29),
          "panel set-up: %d bytes on the SPI pins, %d commands, sleep-out (11) before display-on (29)" % (len(spi), len(cmds)))
    sd = re.search(r"SDRAM mode_set (\d+) reads (\d+) writes (\d+) words (\d+) refreshes (\d+) bad_rows (\d+)", out)
    cam = re.search(r"CAMERA frames (\d+) backlight (\d+) lcd_reset_n (\d+)", out)
    check(sd and sd.group(1) == "1" and sd.group(6) == "0", "SDRAM set to CAS latency 3, full-page bursts; %s read and %s write bursts, %s refreshes"
          % (sd.group(2), sd.group(3), sd.group(5)))
    check(all(f["pixels"] == 230400 and f["lines"] == 480 and f["hsync"] == 506 for f in frames[1:]) and len(frames) >= 2,
          "every picture after the first is 480 lines of 480 pixels in 506 lines (%d pictures)" % len(frames))

    # ---- pictures
    dot = DOT
    exact_cam, edge_frames, shift = [], [], None
    for f in frames:
        px = read_frame(os.path.join(build, "tb_lcd_%d.txt" % f["n"]))
        if len(px) != 230400:
            continue
        undefined = sum(p is None for p in px)
        if f["n"] == 0:
            continue                                         # drawn while the script was still writing the text
        if f["n"] == 1:
            bad = sum(px[y * 480 + x] != overlay6(x, y, test_rgb6(x, y), grid, dot) for y in range(480) for x in range(480))
            check(bad == 0, "picture 1, the design's own test pattern with text, graphics and dot on top: %d of 230400 pixels differ" % bad)
            continue
        best = None
        for dx in ((shift,) if shift is not None else range(-2, 3)):
            bad = 0
            for y in range(480):
                for x in range(480):
                    sx = min(639, max(0, x + 80 + dx))
                    if px[y * 480 + x] != overlay6(x, y, cam_rgb6(cam_word(sx, y)), grid, dot):
                        bad += 1
            if best is None or bad < best[0]:
                best = (bad, dx)
        mono = sum(1 for y in range(480) for x in range(480) if plain(x, y, grid, dot) and px[y * 480 + x] not in ((0, 0, 0), (63, 63, 63)))
        kind = "camera" if best[0] == 0 else "edges" if mono == 0 and not undefined else "mixed"
        print("   picture %d at %3d ms: %-6s  (%d pixels differ from the camera picture at shift %+d, %d undefined, %d not black or white)"
              % (f["n"], f["at"] // 1000, kind, best[0], best[1], undefined, mono))
        sys.stdout.flush()
        if kind == "camera":
            exact_cam.append(f["n"])
            shift = best[1]
        if kind == "edges":
            edge_frames.append((f["n"], px))
    before_key = [n for n in exact_cam if frames[n]["at"] < T_KEY_US]
    check(len(before_key) >= 1, "camera -> SDRAM -> TFT: picture %s is exact in all 230400 pixels, text, graphics and dot included "
          "(camera column = panel column + %s)" % (before_key[:1], "?" if shift is None else 80 + shift))
    if end_ms * 1000 > T_KEY_US + 30000:
        check(len(edge_frames) >= 1, "the view key (OUT bit 4 from the ESP32) switches to the edge picture: picture %s is black and white only"
              % [n for n, _ in edge_frames][:1])
        if edge_frames:
            check(*edge_check(edge_frames[-1][1], grid, dot, shift))

    # ---- bridge
    data = bytes(int(x, 16) for x in open(os.path.join(build, "tb_out.txt")).read().split())
    before = fcl_hub.crc_errors
    fr = fcl_hub.Parser().feed(data)
    kinds = [t for t, p in fr]
    i2c = [p for t, p in fr if t == bm.I2C]
    samples = [p for t, p in fr if t == bm.SAMPLE]
    inputs = [p for t, p in fr if t == bm.INPUT_DATA]
    check(fcl_hub.crc_errors == before and bm.PING in kinds, "bridge: %d frames on the UART, no CRC error, ping answered" % len(fr))
    check(i2c and bytes(i2c[0])[-2:-1] == bytes(((0x75 * 3 + 1) & 255,)), "bridge: I2C register read returns the device's value")
    want_s = (end_ms * 1000 - 12000) // 10000
    check(abs(len(samples) - want_s) <= 2 and all(len(p) == 20 for p in samples),
          "bridge: %d scheduled sensor samples while the video runs (one every 10 ms)" % len(samples))
    check(any(p[-2] & 4 for p in inputs) and inputs[-1][-2] == 0, "bridge: B2 press and release reported (%d input frames)" % len(inputs))
    check(kinds.count(bm.OUT) >= (3 if end_ms * 1000 > T_KEY_US + 5000 else 1) and kinds.count(bm.OSD_TEXT) == len(TEXT)
          and kinds.count(bm.OSD_HUD) == 1, "bridge: overlay text, graphics and output commands acknowledged")
    if "--keep" not in sys.argv and "--analyse" not in sys.argv:
        for n in os.listdir(build):
            if n.startswith("tb_lcd_"):
                os.remove(os.path.join(build, n))
    print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
