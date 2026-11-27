# FCL calculations shared by the ESP32 (MicroPython) and the PC tools: charge from cell voltage, the down dot,
# the LCD overlay text.  Pure Python, no imports beyond math.  The layout matches firmware/common/osd.c.
import math

OSD_COLS, OSD_ROWS = 30, 15
CAM_HFOV_DEG, LCD_HALF_PX, DOT_RIM_PX = 40.0, 240, 226      # CHECK the lens angle on the real camera
TF_RECORDING, TF_CELL_LOW, TF_CUTOFF, TF_TOF_VALID, TF_HOT, TF_DOT_INSIDE = 1, 2, 4, 8, 16, 32
TF_EDGES, TF_MENU, TF_LOG = 64, 128, 256            # edge view on the LCD, menu open, logging
OV_DOT, OV_HEADING, OV_ATTITUDE, OV_BARO, OV_DIST, OV_BATT = 1, 2, 4, 8, 16, 32
SOC_NO_CELL = 255
SOC_TABLE = ((3300, 0), (3450, 5), (3600, 10), (3680, 20), (3720, 30), (3760, 40), (3800, 50), (3850, 60), (3920, 70),
             (4000, 80), (4100, 90), (4200, 100))
CARD = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def soc_from_mv(mv):
    """Li-ion rest voltage -> percent; SOC_NO_CELL below 2.5 V (empty slot)"""
    if mv < 2500:
        return SOC_NO_CELL
    if mv <= SOC_TABLE[0][0]:
        return 0
    m0, p0 = SOC_TABLE[0]
    for m1, p1 in SOC_TABLE[1:]:
        if mv <= m1:
            return p0 + (p1 - p0) * (mv - m0) // (m1 - m0)
        m0, p0 = m1, p1
    return 100


def down_dot(pitch_deg, roll_deg, hfov_deg=CAM_HFOV_DEG):
    """-> (x, y, inside): where straight down appears, pixels from the screen centre (+x right, +y down)"""
    p, r = math.radians(pitch_deg), math.radians(roll_deg)
    sp, cp, sr, cr = math.sin(p), math.cos(p), math.sin(r), math.cos(r)
    dx, u, v = -sp, cp * sr, cp * cr
    f = LCD_HALF_PX / math.tan(math.radians(hfov_deg / 2))
    if dx > 0.05:
        px, py = f * u / dx, f * v / dx
        if px * px + py * py <= DOT_RIM_PX * DOT_RIM_PX:
            return int(round(px)), int(round(py)), True
    m = math.sqrt(u * u + v * v)
    if m < 1e-6:
        u, v, m = 0.0, 1.0, 1.0
    return int(round(DOT_RIM_PX * u / m)), int(round(DOT_RIM_PX * v / m)), False


def _round10(v):
    return int((v + (-5 if v < 0 else 5)) / 10)       # as C integer division: toward zero


def _fix1(v10, plus):
    a = abs(v10)
    return "%s%d.%d" % ("-" if v10 < 0 else ("+" if plus else ""), a // 10, a % 10)


def osd_compose(t):
    """telemetry dict -> list of OSD_ROWS strings of OSD_COLS characters"""
    grid = [" " * OSD_COLS] * OSD_ROWS

    def centre(row, s):
        s = s[:OSD_COLS]
        c = (OSD_COLS - len(s)) // 2
        grid[row] = " " * c + s + " " * (OSD_COLS - c - len(s))

    ov, fl = t["overlay"], t["flags"]
    if ov & OV_HEADING:
        h = (int(round(t["heading"] * 100)) + 36000) % 36000
        centre(1, "%03d %s" % (((h + 50) // 100) % 360, CARD[((h + 2250) // 4500) % 8]))
    if fl & TF_RECORDING:
        centre(2, "REC")
    if ov & OV_ATTITUDE:
        centre(3, "P" + _fix1(_round10(int(round(t["pitch"] * 100))), True) + "  R" + _fix1(_round10(int(round(t["roll"] * 100))), True))
    if ov & OV_DIST:
        d = t["tof_mm"]
        centre(10, "D %d.%02dm" % (d // 1000, (d % 1000) // 10) if fl & TF_TOF_VALID else "D ---")
    if ov & OV_BARO:
        centre(11, "ALT " + _fix1(_round10(int(round(t["alt_m"] * 100))), True) + "m %dhPa" % ((t["press_pa"] + 50) // 100))
    if ov & OV_BATT:
        soc = (t["soc1"], t["soc2"], t["soc3"])
        s = " ".join(["--" if x == SOC_NO_CELL else "%d%%" % x for x in soc])
        s += " OFF" if fl & TF_CUTOFF else (" LOW" if fl & TF_CELL_LOW else "")
        centre(12, s)
        tc = (t["temp1_c"], t["temp2_c"], t["temp3_c"])
        s = " ".join(["--" if x == SOC_NO_CELL else "%d" % _round10(int(round(c * 10))) for x, c in zip(soc, tc)])
        centre(13, s + "C" + (" HOT" if fl & TF_HOT else ""))
    return grid
