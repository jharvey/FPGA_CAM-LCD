#!/usr/bin/env python3
"""Video of the simulated unit: the dashboard (USB serial stream) beside the LCD with its overlay, through a
scripted tour: level to the north-east, pan to the south-east, tilt, point straight down, climb, buttons, a low cell.

    python firmware/tools/make_video.py [out.mp4]        (needs numpy, Pillow, matplotlib's fonts and ffmpeg)

Everything shown comes from the simulator (firmware/sim/fcl_sim.py, bridge path): the same ESP32 files the unit
will run, a model of the FPGA bridge, and modelled sensors.  The camera picture is a stand-in scene.
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(0, os.path.join(HERE, "..", "esp32"))
import fcl_dash     # noqa: E402
import fcl_osd      # noqa: E402
import fcl_sim      # noqa: E402

W, H, FPS = 1600, 900, 10
BG = (16, 20, 26)


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# time, heading, pitch, roll, height, caption
KEYS = [
    (0.0, 45, 0, 0, 0.0, "Level, pointing north-east. The dot sits on the rim at the bottom: down is below the picture."),
    (5.0, 45, 0, 0, 0.0, "Panning right to the south-east."),
    (11.0, 135, 0, 0, 0.0, "South-east. Tilting up, then rolling to the right."),
    (13.5, 135, 18, 0, 0.0, ""),
    (16.0, 135, 0, 12, 0.0, "Rolled right: the dot moves round the rim toward down."),
    (18.5, 135, 0, 0, 0.0, "Tilting down toward the ground."),
    (23.0, 150, -70, 0, 0.0, "70 degrees down: still outside the picture."),
    (26.0, 150, -82, 0, 0.0, "The dot turns green and enters the picture: 8 degrees short of straight down."),
    (29.0, 150, -90, 0, 0.0, "Dot on the centre cross: the lens points straight down."),
    (31.0, 150, -90, 0, 0.0, "Moving a few degrees off and around: the dot follows."),
    (36.0, 150, -90, 0, 0.0, "Back up to level, turning to the north-west."),
    (42.0, 315, 0, 0, 0.0, "North-west, level. Raising the unit 2 m: height and pressure change."),
    (47.0, 315, 0, 0, 2.0, "Button B2: recording mark (REC). Button B1: next page, Level."),
    (51.0, 315, 0, 0, 2.0, "Commands over USB: servo 2 to 1800 us, then the overlay reduced to dot and charge."),
    (56.0, 330, 0, 0, 2.0, "Cell 3 runs low and warm: LOW on the LCD and in the dashboard."),
    (62.0, 330, 0, 0, 2.0, ""),
]
COMMANDS = [(47.5, "sim press B2 400"), (49.0, "sim press B1 400"), (51.5, "servo 2 1800"), (53.0, "overlay dot batt"),
            (55.5, "overlay all"), (56.0, "sim set cell3 3.36"), (56.0, "sim set temp3 41"), (1.0, "wifi HomeNet secretpass")]
END = 62.0


class Tour(fcl_sim.Scenario):
    def at(self, t):
        k = 0
        while k + 2 < len(KEYS) and t >= KEYS[k + 1][0]:
            k += 1
        a, b = KEYS[k], KEYS[k + 1]
        f = smooth((t - a[0]) / (b[0] - a[0]))
        s = {"heading": a[1] + (b[1] - a[1]) * f, "pitch": a[2] + (b[2] - a[2]) * f, "roll": a[3] + (b[3] - a[3]) * f,
             "alt": a[4] + (b[4] - a[4]) * f, "dist": 1500 + 700 * math.sin(2 * math.pi * t / 9.0),
             "cell1": 4.02, "cell2": 3.95, "cell3": 3.74, "temp1": 25.0, "temp2": 26.0, "temp3": 28.0}
        if 31.0 <= t < 36.0:                         # a small circle round straight down
            u = (t - 31.0) / 5.0
            s["pitch"] = -90 + 5.0 * math.sin(math.pi * u) ** 2
            s["roll"] = 360.0 * u
        if s["pitch"] < -60:                         # the ranger sees the ground when pointed at it
            s["dist"] = (1.4 + s["alt"]) * 1000
        self.caption = a[5] or getattr(self, "caption", "")
        dt = max(0.0, t - self.last_t)
        self.last_t = t
        for key, target in self.hold.items():
            self.cur[key] = s[key] = target
        btn = 0
        for i, until in list(self.press.items()):
            if t < until:
                btn |= 1 << i
            else:
                del self.press[i]
        return s, btn


# ---------------------------------------------------------------- LCD, with numpy
FONT = np.array([[[(row >> (15 - x)) & 1 for x in range(16)] for row in g] for g in fcl_osd.font()], dtype=bool)
YY, XX = np.mgrid[0:480, 0:480]
F_PX = 240 / math.tan(math.radians(fcl_osd.CAM_HFOV_DEG / 2))
U, V = (XX - 240) / F_PX, (YY - 240) / F_PX
NRM = np.sqrt(1 + U * U + V * V)
BX, BY, BZ = 1 / NRM, -U / NRM, -V / NRM
ROUND = (XX - 239.5) ** 2 + (YY - 239.5) ** 2 > 240 * 240


def lcd(t, grid):
    p, r, hd = math.radians(t["pitch"]), math.radians(t["roll"]), math.radians(t["heading"])
    y2 = BY * math.cos(r) - BZ * math.sin(r)
    z2 = BY * math.sin(r) + BZ * math.cos(r)
    x3 = BX * math.cos(p) - z2 * math.sin(p)
    z3 = BX * math.sin(p) + z2 * math.cos(p)
    img = np.zeros((480, 480, 3), dtype=np.float32)
    k = np.clip(z3 * 2.5, 0, 1)
    sky = np.stack([150 - 70 * k, 190 - 60 * k, 235 - 20 * k], axis=-1)
    h = 1.6 / np.maximum(1e-3, -z3)
    gx, gy = x3 * h, y2 * h
    wx, wy = gx * math.cos(hd) + gy * math.sin(hd), -gx * math.sin(hd) + gy * math.cos(hd)
    line = np.minimum(np.abs(wx - np.round(wx)), np.abs(wy - np.round(wy))) < 0.02 * np.maximum(1.0, h / 3)
    fade = np.clip(3.0 / h, 0.35, 1.0)[..., None]
    base = np.where(line[..., None], np.array([200, 205, 190], dtype=np.float32), np.array([88, 120, 70], dtype=np.float32))
    ground = base * fade + 110 * (1 - fade)
    img = np.where((z3 > 0)[..., None], sky, ground).astype(np.uint8)
    for row in range(15):                                         # text: glyph white, the rest of the cell at half brightness
        for col in range(30):
            ch = ord(grid[row][col])
            if ch != 32 and 32 < ch < 128:
                cell = img[row * 32:row * 32 + 32, col * 16:col * 16 + 16]
                cell >>= 1
                cell[FONT[ch - 32]] = 255
    if t["overlay"] & 1:
        d2 = (XX - 240 - t["dot_x"]) ** 2 + (YY - 240 - t["dot_y"]) ** 2
        img[d2 <= 169] = 0
        img[(d2 <= 9) | ((d2 >= 64) & (d2 <= 121))] = fcl_osd.DOT_INSIDE_RGB if t["flags"] & 32 else fcl_osd.DOT_RIM_RGB
    img[240, 232:249] = np.maximum(img[240, 232:249], 150)      # centre cross of the picture (not part of the overlay)
    img[232:249, 240] = np.maximum(img[232:249, 240], 150)
    img[ROUND] = (20, 20, 20)
    return Image.fromarray(img)


# ---------------------------------------------------------------- dashboard text with cached glyphs
def fonts():
    import matplotlib
    d = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    return ImageFont.truetype(os.path.join(d, "DejaVuSansMono.ttf"), 14), ImageFont.truetype(os.path.join(d, "DejaVuSans.ttf"), 24), \
        ImageFont.truetype(os.path.join(d, "DejaVuSans-Bold.ttf"), 20)


MONO, CAP, HEAD = fonts()
CW, CH = int(round(MONO.getlength("M"))), 18
_glyph = {}


def glyph(c):
    if c not in _glyph:
        col = (120, 200, 255) if c in "█●◆▲" else ((95, 105, 120) if c in "─│┌┐└┘├┤┬┴┼░·" else (225, 230, 235))
        im = Image.new("RGB", (CW, CH), BG)
        ImageDraw.Draw(im).text((0, 0), c, font=MONO, fill=col)
        _glyph[c] = im
    return _glyph[c]


def frame(dash, sim, caption):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((30, 18), "USB serial stream: dashboard (fcl_dash.py)", font=HEAD, fill=(150, 170, 190))
    d.text((1045, 18), "LCD with overlay (simulated)", font=HEAD, fill=(150, 170, 190))
    for i, line in enumerate(dash.render()[:-1]):
        for j, c in enumerate(line):
            if c != " ":
                im.paste(glyph(c), (30 + j * CW, 60 + i * CH))
    if sim.last:
        im.paste(lcd(sim.last, sim.state["osd"]).resize((560, 560), Image.LANCZOS), (1010, 70))
    d.text((1010, 650), "Camera picture: a stand-in scene (sky, ground with a 1 m grid).", font=MONO, fill=(120, 130, 140))
    d.text((1010, 672), "Text and dot: the overlay as the unit composes it.", font=MONO, fill=(120, 130, 140))
    d.rectangle((0, H - 130, W, H), fill=(28, 34, 44))
    d.text((30, H - 112), "t = %4.1f s" % sim.t, font=MONO, fill=(120, 200, 255))
    d.text((30, H - 86), caption, font=CAP, fill=(240, 240, 240))
    d.text((30, H - 40), "Simulation: the ESP32's MicroPython files, a model of the FPGA bridge, modelled sensors. Not measured on hardware.",
           font=MONO, fill=(140, 150, 160))
    return im


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "doc", "fw", "fcl_sim_tour.mp4")
    sim = fcl_sim.Sim("bridge")
    tour = Tour()
    tour.caption = ""
    sim.scenario = tour
    sim.world.sc = tour
    dash = fcl_dash.Dash()
    dash.source = "simulator"
    todo = sorted(COMMANDS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE)
    sim.command("status")
    n = 0
    stills = {4.0: "tour_ne_level", 12.0: "tour_se_level", 29.5: "tour_down", 50.0: "tour_nw_rec", 59.0: "tour_low_cell"}
    while sim.t < END:
        for _ in range(int(round(1.0 / FPS / fcl_sim.STEP_S))):
            while todo and todo[0][0] <= sim.t:
                sim.command(todo.pop(0)[1])
            for line in sim.step():
                dash.feed(line)
        dash.rate = float(sim.bridge.rate)
        im = frame(dash, sim, tour.caption)
        ff.stdin.write(im.tobytes())
        for ts in list(stills):
            if sim.t >= ts:
                im.save(os.path.join(ROOT, "doc", "fw", stills.pop(ts) + ".png"))
        n += 1
        if n % 100 == 0:
            print("frame", n, "t", round(sim.t, 1))
    ff.stdin.close()
    ff.wait()
    sim.close()
    print("wrote", out, os.path.getsize(out) // 1024, "kB,", n, "frames")


if __name__ == "__main__":
    main()
