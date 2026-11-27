#!/usr/bin/env python3
"""LCD overlay in Python: the same text grid, down dot and pixels as the hub (common/osd.c, app.c) and the FPGA
(fpga/osd/fcl_osd.v), used by the simulator, the documentation pictures and the tests.

    from fcl_osd import osd_compose, down_dot, render
    img = render(t)            # t: telemetry dict (fcl_hub / fcl_usb field names) -> 480 x 480 PIL image
"""
import math
import os

OSD_COLS, OSD_ROWS = 30, 15
CELL_W, CELL_H = 16, 32
LCD = 480
CAM_HFOV_DEG, LCD_HALF_PX, DOT_RIM_PX = 40.0, 240, 226
TF_RECORDING, TF_CELL_LOW, TF_CUTOFF, TF_TOF_VALID, TF_HOT, TF_DOT_INSIDE = 1, 2, 4, 8, 16, 32
OV_DOT, OV_HEADING, OV_ATTITUDE, OV_BARO, OV_DIST, OV_BATT = 1, 2, 4, 8, 16, 32
SOC_NO_CELL = 255
SOC_TABLE = ((3300, 0), (3450, 5), (3600, 10), (3680, 20), (3720, 30), (3760, 40), (3800, 50), (3850, 60), (3920, 70),
             (4000, 80), (4100, 90), (4200, 100))
CARD = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
FONT_HEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fpga", "osd", "font16x32.hex")


def soc_from_mv(mv):
    if mv < 2500:
        return SOC_NO_CELL
    if mv <= SOC_TABLE[0][0]:
        return 0
    for (m0, p0), (m1, p1) in zip(SOC_TABLE, SOC_TABLE[1:]):
        if mv <= m1:
            return p0 + (p1 - p0) * (mv - m0) // (m1 - m0)
    return 100


def down_dot(pitch_deg, roll_deg):
    """-> (x, y, inside): where straight down appears, pixels from the screen centre (+x right, +y down)"""
    sp, cp = math.sin(math.radians(pitch_deg)), math.cos(math.radians(pitch_deg))
    sr, cr = math.sin(math.radians(roll_deg)), math.cos(math.radians(roll_deg))
    dx, dy, dz = -sp, -cp * sr, -cp * cr
    f = LCD_HALF_PX / math.tan(math.radians(CAM_HFOV_DEG / 2))
    u, v = -dy, -dz
    if dx > 0.05:
        px, py = f * u / dx, f * v / dx
        if px * px + py * py <= DOT_RIM_PX * DOT_RIM_PX:
            return int(round(px)), int(round(py)), True
    m = math.hypot(u, v)
    if m < 1e-6:
        u, v, m = 0.0, 1.0, 1.0
    return int(round(DOT_RIM_PX * u / m)), int(round(DOT_RIM_PX * v / m)), False


def _trunc(x):
    return int(x)                      # C integer division truncates toward zero


def _round10(v):
    return _trunc((v + (-5 if v < 0 else 5)) / 10)


def _fix1(v10, plus):
    a = abs(v10)
    return "%s%d.%d" % ("-" if v10 < 0 else ("+" if plus else ""), a // 10, a % 10)


def osd_compose(t):
    """telemetry dict -> list of OSD_ROWS strings of OSD_COLS characters (same layout as common/osd.c)"""
    grid = [" " * OSD_COLS for _ in range(OSD_ROWS)]

    def centre(row, s):
        s = s[:OSD_COLS]
        c = (OSD_COLS - len(s)) // 2
        grid[row] = grid[row][:c] + s + grid[row][c + len(s):]

    ov, fl = t["overlay"], t["flags"]
    if ov & OV_HEADING:
        h = (int(round(t["heading"] * 100)) + 36000) % 36000
        centre(1, "%03d %s" % (((h + 50) // 100) % 360, CARD[((h + 2250) // 4500) % 8]))
    if fl & TF_RECORDING:
        centre(2, "REC")
    if ov & OV_ATTITUDE:
        centre(3, "P" + _fix1(_round10(int(round(t["pitch"] * 100))), True) + "  R" + _fix1(_round10(int(round(t["roll"] * 100))), True))
    if ov & OV_DIST:
        d = t["tof_mm"] if "tof_mm" in t else t["dist_mm"]
        centre(10, "D %d.%02dm" % (d // 1000, (d % 1000) // 10) if fl & TF_TOF_VALID else "D ---")
    if ov & OV_BARO:
        pa = t["press_pa"] if "press_pa" in t else int(round(t["press_hpa"] * 100))
        centre(11, "ALT " + _fix1(_round10(int(round(t["alt_m"] * 100))), True) + "m %dhPa" % ((pa + 50) // 100))
    if ov & OV_BATT:
        soc = [t["soc1"], t["soc2"], t["soc3"]]
        s = " ".join("--" if x == SOC_NO_CELL else "%d%%" % x for x in soc)
        s += " OFF" if fl & TF_CUTOFF else (" LOW" if fl & TF_CELL_LOW else "")
        centre(12, s)
        tc = [int(round(t["temp%d_c" % i] * 10)) for i in (1, 2, 3)]
        s = " ".join("--" if x == SOC_NO_CELL else "%d" % _round10(c) for x, c in zip(soc, tc))
        centre(13, s + "C" + (" HOT" if fl & TF_HOT else ""))
    return grid


# ---------------------------------------------------------------- pixels
_font = None


def font():
    """96 glyphs (ASCII 32..127), each 32 rows of 16 bits, MSB = left pixel: the FPGA's font ROM"""
    global _font
    if _font is None:
        words = [int(x, 16) for x in open(FONT_HEX).read().split()]
        assert len(words) == 96 * CELL_H, len(words)
        _font = [words[i * CELL_H:(i + 1) * CELL_H] for i in range(96)]
    return _font


DOT_INSIDE_RGB, DOT_RIM_RGB = (40, 255, 80), (255, 176, 0)


def overlay_pixel(x, y, rgb, grid, dot):
    """one output pixel, exactly as fcl_osd.v computes it. dot = (x, y, on, inside) in screen pixels (0..479)"""
    col, row = x >> 4, y >> 5
    ch = ord(grid[row][col]) if row < OSD_ROWS and col < OSD_COLS else 32
    if ch < 32 or ch > 127:
        ch = 32
    if ch != 32:
        if font()[ch - 32][y & 31] >> (15 - (x & 15)) & 1:
            rgb = (255, 255, 255)
        else:
            rgb = (rgb[0] >> 1, rgb[1] >> 1, rgb[2] >> 1)        # darken the cell behind a character
    dx, dy, on, inside = dot
    if on:
        d2 = (x - dx) * (x - dx) + (y - dy) * (y - dy)
        if d2 <= 9 or 64 <= d2 <= 121:
            rgb = DOT_INSIDE_RGB if inside else DOT_RIM_RGB
        elif d2 <= 169:
            rgb = (0, 0, 0)                                       # black edge so it shows on any picture
    return rgb


def scene(t, x, y):
    """a stand-in camera picture: sky, horizon and ground for the present pitch / roll (documentation only)"""
    f = LCD_HALF_PX / math.tan(math.radians(CAM_HFOV_DEG / 2))
    u, v = (x - 240) / f, (y - 240) / f
    p, r = math.radians(t["pitch"]), math.radians(t["roll"])
    # ray in the device frame (x forward, y left, z up), then to the world: z component decides sky / ground
    bx, by, bz = 1.0, -u, -v
    n = math.sqrt(bx * bx + by * by + bz * bz)
    bx, by, bz = bx / n, by / n, bz / n
    y2, z2 = by * math.cos(r) - bz * math.sin(r), by * math.sin(r) + bz * math.cos(r)
    x3, z3 = bx * math.cos(p) - z2 * math.sin(p), bx * math.sin(p) + z2 * math.cos(p)
    if z3 > 0:
        k = min(1.0, z3 * 2.5)
        return (int(150 - 70 * k), int(190 - 60 * k), int(235 - 20 * k))
    h = 1.6 / max(1e-3, -z3)                                      # ground: a 1 m grid seen from 1.6 m
    gx, gy = x3 * h, y2 * h
    hd = math.radians(t["heading"])
    wx, wy = gx * math.cos(hd) + gy * math.sin(hd), -gx * math.sin(hd) + gy * math.cos(hd)
    line = min(abs(wx - round(wx)), abs(wy - round(wy))) < 0.02 * max(1.0, h / 3)
    fade = max(0.35, min(1.0, 3.0 / h))
    base = (88, 120, 70) if not line else (200, 205, 190)
    return tuple(int(c * fade + 110 * (1 - fade)) for c in base)


def render(t, grid=None, background=None, round_mask=True):
    """-> PIL image 480 x 480. background: None = synthetic scene, or an (r, g, b) tuple for a flat colour."""
    from PIL import Image
    if grid is None:
        grid = osd_compose(t)
    on = bool(t["overlay"] & OV_DOT)
    dot = (240 + t["dot_x"], 240 + t["dot_y"], on, bool(t["flags"] & TF_DOT_INSIDE))
    img = Image.new("RGB", (LCD, LCD))
    px = img.load()
    for y in range(LCD):
        for x in range(LCD):
            if round_mask and (x - 239.5) ** 2 + (y - 239.5) ** 2 > 240 * 240:
                px[x, y] = (20, 20, 20)
                continue
            bg = background if background is not None else scene(t, x, y)
            px[x, y] = overlay_pixel(x, y, bg, grid, dot)
    return img


if __name__ == "__main__":
    demo = {"heading": 123.4, "pitch": -78.0, "roll": 4.0, "alt_m": 2.96, "press_pa": 101290, "tof_mm": 1870,
            "soc1": 87, "soc2": 85, "soc3": 23, "temp1_c": 25.0, "temp2_c": 26.1, "temp3_c": 31.4, "overlay": 0x3F,
            "flags": TF_TOF_VALID | TF_RECORDING}
    x, y, inside = down_dot(demo["pitch"], demo["roll"])
    demo.update(dot_x=x, dot_y=y, flags=demo["flags"] | (TF_DOT_INSIDE if inside else 0))
    print("\n".join(osd_compose(demo)))
    render(demo).save("osd_demo.png")
    print("osd_demo.png written")
