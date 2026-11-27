# The layer above the drivers: what the unit does with its sensors.  Runs on the ESP32 (MicroPython) and on a PC.
#
#   Unit    the calls an app uses: unit.heading(), unit.distance(), unit.servo(2, 1500), unit.say("text") ...
#   App     base class of a page on the LCD.  B1 steps through the pages, B2 is the page's own button.
#   Apps    the pages, the menu (hold B1), and the text they put on the LCD.  The hub (fcl_hubpy.py) calls it.
#
# Pages:  0 Overview (the standard overlay; B2 = recording mark)     2 Height (of an object, from two sightings)
#         1 Level (pitch, roll, slope)                               3 Bearing (mark a direction, come back to it)
#         4 Survey (points from heading, pitch and distance: a room's corners give its plan and area)
# Add your own with apps.add(MyApp()): see doc/DEVELOPER_GUIDE.md and the example at the end of that guide.
#
# Graphics drawn by the FPGA under the text: RETICLE (a cross at the centre), HORIZON (a line that stays level with
# the ground), TAPE (compass ticks at the top).  A page asks for them with its `hud` attribute; the user can switch
# them on for every page (menu "Graphics", command "hud").
import math
import fcl_calc

T_ROW, V_ROW, V2_ROW, H_ROW = 4, 5, 8, 9            # LCD rows a page may use: title, value, second value, hint
MENU_TOP, MENU_ROWS = 3, 7                          # menu: title on row 3, items on rows 4..10, hint on row 11
LONG_MS = 700                                       # B1 held this long opens or closes the menu
RETICLE, HORIZON, TAPE = fcl_calc.HUD_RETICLE, fcl_calc.HUD_HORIZON, fcl_calc.HUD_TAPE


def _wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


class Unit:
    """What an app may read and do.  Angles in degrees, lengths in metres unless the name says otherwise."""

    def __init__(self, hub, plat=None):
        self.hub, self.plat = hub, plat

    # ---- readings (None while there is no telemetry yet)
    def _t(self, k):
        t = self.hub.last
        return t.get(k) if t else None

    def heading(self):
        return self._t("heading")

    def pitch(self):
        return self._t("pitch")

    def roll(self):
        return self._t("roll")

    def height(self):
        """metres above the last zero, from the barometer"""
        return self._t("alt_m")

    def pressure(self):
        p = self._t("press_pa")
        return None if p is None else p / 100.0

    def distance(self):
        """metres to what the ranger sees, or None when it sees nothing (its reach is about 4 m)"""
        t = self.hub.last
        if not t or not t["flags"] & fcl_calc.TF_TOF_VALID:
            return None
        return t["tof_mm"] / 1000.0

    def cells(self):
        """[(millivolts, percent or None, degrees C)] for the three cells"""
        t = self.hub.last
        if not t:
            return []
        return [(t["cell%d_mv" % i], None if t["soc%d" % i] == fcl_calc.SOC_NO_CELL else t["soc%d" % i], t["temp%d_c" % i])
                for i in (1, 2, 3)]

    def time_ms(self):
        return self.hub.now_ms

    # ---- actions
    def servo(self, n, us):
        """servo 1..6, pulse 500..2500 us, 0 = off"""
        self.hub.servo(n - 1, us)

    def follow(self, on):
        self.hub.follow(on)

    def pan(self, heading):
        """servo 2 holds this compass heading; None = stop"""
        self.hub.pan(heading)

    def zero(self):
        self.hub.zero_alt()

    def view(self, edges):
        self.hub.view(edges)

    def overlay(self, mask):
        self.hub.overlay(mask)

    def graphics(self, mask):
        """graphics on every page: RETICLE | HORIZON | TAPE, 0 = only what a page asks for"""
        self.hub.graphics(mask)

    def beep(self, hz=880, ms=80):
        f = getattr(self.plat, "tone", None)
        if f:
            f(hz, ms)

    def say(self, text):
        """one line to the USB stream and the log ($I,...)"""
        if self.hub.on_info:
            self.hub.on_info("$I," + text)

    def line(self, text):
        """a line of your own kind to the USB stream and the log, as it is: start it with $ and a capital letter"""
        if self.hub.on_info:
            self.hub.on_info(text)


class App:
    name = "App"                 # shown on the LCD: 14 characters at most
    hud = 0                      # graphics while this page shows: RETICLE | HORIZON | TAPE

    def start(self, unit):       # the page has been selected
        pass

    def stop(self, unit):        # another page has been selected
        pass

    def button(self, unit):      # B2 pressed while this page shows
        pass

    def draw(self, unit, put):   # 20 times a second: put(row, text) writes a centred line (rows 4, 5, 8, 9)
        pass


class Level(App):
    name = "LEVEL"
    hud = RETICLE | HORIZON

    def draw(self, unit, put):
        p, r = unit.pitch(), unit.roll()
        put(T_ROW, self.name)
        if abs(p) < 0.5 and abs(r) < 0.5:
            put(V_ROW, "== LEVEL ==")
        else:
            put(V_ROW, "%s %.1f  %s %.1f" % ("UP" if p > 0 else "DN", abs(p), "R" if r > 0 else "L", abs(r)))
        if abs(p) < 80:
            put(V2_ROW, "SLOPE %+.1f%%" % (100.0 * math.tan(math.radians(p))))


class Height(App):
    """Height of an object from two sightings: its foot (the ranger must reach it), then its top."""
    name = "HEIGHT"
    hud = RETICLE

    def __init__(self):
        self.base = None         # (horizontal distance, height of the foot relative to the unit)
        self.result = None

    def start(self, unit):
        self.base = self.result = None

    def _now(self, unit):
        p = unit.pitch()
        if self.base is None or abs(p) > 80:
            return None
        return self.base[0] * math.tan(math.radians(p)) - self.base[1]

    def button(self, unit):
        if self.base is None or self.result is not None:
            d = unit.distance()
            self.result = None
            if d is None:
                self.base = None
                unit.beep(220, 200)
                return
            p = math.radians(unit.pitch())
            self.base = (d * math.cos(p), d * math.sin(p))
            unit.beep()
        else:
            h = self._now(unit)
            if h is not None:
                self.result = h
                unit.say("height %.2f m at %.2f m" % (h, self.base[0]))
                unit.beep(1320)

    def draw(self, unit, put):
        put(T_ROW, self.name)
        if self.base is None:
            put(V_ROW, "AIM AT THE FOOT")
            put(H_ROW, "B2 = MARK" if unit.distance() is not None else "OUT OF RANGE")
        elif self.result is None:
            h = self._now(unit)
            put(V_ROW, "H ---" if h is None else "H %.2fm" % h)
            put(V2_ROW, "AT %.2fm" % self.base[0])
            put(H_ROW, "AIM AT TOP, B2")
        else:
            put(V_ROW, "H %.2fm" % self.result)
            put(V2_ROW, "AT %.2fm" % self.base[0])
            put(H_ROW, "B2 = AGAIN")


class Bearing(App):
    """Mark a direction and a height; shows the way back to it."""
    name = "BEARING"
    hud = RETICLE | TAPE

    def __init__(self):
        self.mark = None         # (heading, height)

    def button(self, unit):
        self.mark = (unit.heading(), unit.height())
        unit.say("bearing %.0f marked" % self.mark[0])
        unit.beep()

    def draw(self, unit, put):
        put(T_ROW, self.name)
        if self.mark is None:
            put(V_ROW, "AIM, THEN B2")
            return
        e = _wrap180(self.mark[0] - unit.heading())
        put(V_ROW, "ON MARK" if abs(e) < 2 else "TURN %s %d" % ("R" if e > 0 else "L", int(abs(e) + 0.5)))
        put(V2_ROW, "MARK %03d  %+.1fm" % (int(self.mark[0] + 0.5) % 360, unit.height() - self.mark[1]))
        put(H_ROW, "B2 = NEW MARK")


class Survey(App):
    """Points around you from where you stand: aim at a corner, B2.  Each point is the ranger's distance along the
    compass heading and the pitch; x is east, y north, z up, in metres from the unit.  The points in the order
    taken are the corners of a shape: the page shows its last side, its area on the ground and its perimeter."""
    name = "SURVEY"
    hud = RETICLE | TAPE
    MAX = 60

    def __init__(self):
        self.pts = []            # (heading, pitch, distance, x, y, z)

    def clear(self):
        self.pts = []

    def point_line(self, i):
        return "$P,%d,%.1f,%.1f,%.3f,%.3f,%.3f,%.3f" % ((i + 1,) + self.pts[i])

    def button(self, unit):
        d = unit.distance()
        if d is None or len(self.pts) >= self.MAX:
            unit.beep(220, 200)
            return
        h, p = unit.heading(), unit.pitch()
        hr, pr = math.radians(h), math.radians(p)
        g = d * math.cos(pr)
        self.pts.append((h, p, d, g * math.sin(hr), g * math.cos(hr), d * math.sin(pr)))
        unit.line(self.point_line(len(self.pts) - 1))
        unit.beep()

    def side(self, i):
        """length on the ground from point i - 1 to point i"""
        a, b = self.pts[i - 1], self.pts[i]
        return math.sqrt((b[3] - a[3]) ** 2 + (b[4] - a[4]) ** 2)

    def area(self):
        """(area on the ground of the closed shape, its perimeter)"""
        n = len(self.pts)
        if n < 3:
            return 0.0, 0.0
        s = 0.0
        for i in range(n):
            a, b = self.pts[i - 1], self.pts[i]
            s += a[3] * b[4] - b[3] * a[4]
        return abs(s) / 2.0, sum(self.side(i) for i in range(n))

    def draw(self, unit, put):
        n = len(self.pts)
        put(T_ROW, "%s  %d PT" % (self.name, n))
        d = unit.distance()
        put(V_ROW, ("D %.2fm" % d if d is not None else "D ---") + ("  SIDE %.2fm" % self.side(n - 1) if n >= 2 else ""))
        if n >= 3:
            put(V2_ROW, "AREA %.1fm2  AROUND %.1fm" % self.area())
        put(H_ROW, "MEMORY FULL" if n >= self.MAX else "B2 = POINT" if d is not None else "OUT OF RANGE")


class Apps:
    """Pages, menu and the keys.  The hub calls key(), compose() and report()."""

    def __init__(self, hub, plat=None):
        self.hub, self.plat = hub, plat
        self.unit = Unit(hub, plat)
        self.survey = Survey()
        self.pages = [None, Level(), Height(), Bearing(), self.survey]       # page 0 is the overview: no app
        self.menu_open = False
        self.sel = 0
        self.rows = {}               # LCD rows written by the page or the menu in the last frame
        self._sent = {}
        self._sent_t = -1000
        self._hud_sent = None
        self.log_on = False
        self.items = (
            (lambda: "View: " + ("edges" if hub.edges else "camera"), lambda: hub.view(not hub.edges)),
            (lambda: "Edges +", lambda: hub.threshold(1)),
            (lambda: "Edges -", lambda: hub.threshold(-1)),
            (lambda: "Overlay: " + {0x3F: "all", 0x01: "dot", 0: "off"}.get(hub.overlay_mask, "custom"),
             lambda: hub.overlay({0x3F: 0x01, 0x01: 0}.get(hub.overlay_mask, 0x3F))),
            (lambda: "Level servo: " + ("on" if hub.follow_on else "off"), lambda: hub.follow(not hub.follow_on)),
            (lambda: "Zero height", hub.zero_alt),
            (self._cal_label, self._cal_go),
            (self._wifi_label, self._wifi_go),
            (lambda: "Log: " + ("on" if self.log_on else "off"), lambda: self.log(not self.log_on)),
            (lambda: "Graphics: " + {0: "page", 1: "reticle", 7: "all"}.get(hub.hud_mask, "custom"),
             lambda: hub.graphics({0: 1, 1: 7}.get(hub.hud_mask, 0))),
            (lambda: "Clear points: %d" % len(self.survey.pts), self.survey.clear),
            (lambda: "Exit", self._close),
        )

    def add(self, app):
        """one more page after the built-in ones; returns its number"""
        self.pages.append(app)
        return len(self.pages) - 1

    # ---- menu actions that need more than one line
    def _cal_label(self):
        cal = self.hub.cal
        if cal.manual:
            return "Compass %d/6" % sum(1 for i in range(6) if cal.seen >> i & 1)
        return "Compass cal (%s)" % cal.state

    def _cal_go(self):
        self.hub.magcal(["stop" if self.hub.cal.manual else "start"])

    def _wifi(self):
        f = getattr(self.plat, "wifi_status", None)
        return f() if f else ("off", "", "", 0)

    def _wifi_label(self):
        st = self._wifi()
        return "WiFi " + (st[2] if st[0] == "connected" else st[0])

    def _wifi_go(self):
        f = getattr(self.plat, "wifi_off" if self._wifi()[0] != "off" else "wifi_on", None)
        if f:
            f()

    def _close(self):
        self.menu_open = False

    def log(self, on):
        f = getattr(self.plat, "log_start" if on else "log_stop", None)
        if f is None:
            return None
        r = f()
        self.log_on = bool(on) and r is not None
        return r

    # ---- keys: "B1", "B2", "B1L" (B1 held).  Returns True when the key has been used here.
    def key(self, k):
        hub = self.hub
        if k == "B1L":
            self.menu_open = not self.menu_open
            self.sel = 0
            return True
        if self.menu_open:
            if k == "B1":
                self.sel = (self.sel + 1) % len(self.items)
            elif k == "B2":
                self.items[self.sel][1]()
            return True
        if k == "B1":
            self.select((hub.mode_n + 1) % len(self.pages))
            return True
        app = self.pages[hub.mode_n] if hub.mode_n < len(self.pages) else None
        if k == "B2" and app is not None:
            if hub.last:
                app.button(self.unit)
            return True
        return False                 # B2 on the overview: the hub's recording mark

    def select(self, n):
        hub = self.hub
        old = self.pages[hub.mode_n] if hub.mode_n < len(self.pages) else None
        if old is not None:
            old.stop(self.unit)
        hub.mode_n = n
        if self.pages[n] is not None:
            self.pages[n].start(self.unit)

    def hud_flags(self):
        """graphics for the page that shows now: none under the menu"""
        if self.menu_open:
            return 0
        hub = self.hub
        app = self.pages[hub.mode_n] if hub.mode_n < len(self.pages) else None
        return hub.hud_mask | (app.hud if app is not None else 0)

    # ---- the LCD text for one telemetry frame
    def compose(self, t):
        rows = {}

        def put(row, text):
            rows[row] = text[:fcl_calc.OSD_COLS]

        if self.menu_open:
            grid = [" " * fcl_calc.OSD_COLS] * fcl_calc.OSD_ROWS
            put(MENU_TOP, "MENU")
            first = max(0, min(self.sel - MENU_ROWS // 2, len(self.items) - MENU_ROWS))
            width = 20
            for i in range(MENU_ROWS):
                j = first + i
                if j < len(self.items):
                    s = ((">" if j == self.sel else " ") + " " + self.items[j][0]())[:width]
                    put(MENU_TOP + 1 + i, s + " " * (width - len(s)))      # (MicroPython has no str.ljust)
            put(MENU_TOP + 1 + MENU_ROWS, "B1 NEXT   B2 OK")
        else:
            grid = fcl_calc.osd_compose(t)
            app = self.pages[t["mode"]] if t["mode"] < len(self.pages) else None
            if app is not None:
                app.draw(self.unit, put)
        shown = {}
        for r in rows:
            s = rows[r]
            c = (fcl_calc.OSD_COLS - len(s)) // 2
            grid[r] = " " * c + s + " " * (fcl_calc.OSD_COLS - c - len(s))
            shown[r] = grid[r].rstrip()
        self.rows = shown                # as on the LCD: leading spaces kept, so a reader need not centre again
        return grid

    def report(self, now_ms, out):
        """$L lines for the rows the page or the menu wrote, 5 times a second at most, only when they change;
        an empty text gives the row back to the standard overlay"""
        hud = self.hub.hud
        if now_ms - self._sent_t < 200 or (self.rows == self._sent and hud == self._hud_sent):
            return
        self._sent_t = now_ms
        if hud != self._hud_sent:        # $H,flags,a,b,c,tape: the graphics as the FPGA has them
            self._hud_sent = hud
            out("$H,%d,%d,%d,%d,%d" % hud)
        for r in sorted(set(self.rows) | set(self._sent)):
            a, b = self._sent.get(r, ""), self.rows.get(r, "")
            if a != b:
                out("$L,%d,%s" % (r, b))
        self._sent = dict(self.rows)
