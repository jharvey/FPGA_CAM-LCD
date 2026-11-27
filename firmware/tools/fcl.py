#!/usr/bin/env python3
"""The FCL unit from a Python script or notebook on a PC.

    import fcl
    u = fcl.connect("COM7")                    # the unit on USB (Linux: "/dev/ttyACM0"); needs pyserial
    u = fcl.connect("sim")                     # the simulator, in real time
    u = fcl.connect("sim", realtime=False)     # the simulator as fast as the PC goes: time passes only in wait()
    u = fcl.connect("tcp:127.0.0.1:7007")      # a running firmware/sim/fcl_sim.py
    u = fcl.connect("replay:trip.log")         # a recorded stream

    u.wait(2)                                  # let two seconds pass
    print(u.heading, u.pitch, u.roll, u.height, u.distance)        # distance is None when nothing is in reach
    u.command("zero")                          # any command of the USB protocol; returns the reply, raises fcl.Error
    u.page("level"); u.key("B2"); u.servo(3, 1700); u.hud("reticle", "tape")
    for t in u.telemetry(seconds=10):          # every telemetry frame as a dictionary
        print(t["t_ms"], t["alt_m"])
    u.points()                                 # the Survey page's points: [{"n", "heading", "pitch", "dist", "x", "y", "z"}]
    u.close()                                  # or:  with fcl.connect("sim") as u: ...

Field names of a telemetry frame: fcl.FIELDS.  The protocol itself: firmware/esp32/fcl_usb.py, doc/FIRMWARE_GUIDE.md.
"""
import os
import queue
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "esp32"))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(0, HERE)
import fcl_usb      # noqa: E402

FIELDS = fcl_usb.T_FIELDS
PAGES = ("overview", "level", "height", "bearing", "survey")
TF_TOF_VALID = 8


class Error(Exception):
    """the unit answered $R,err,... or did not answer"""


class _Stepped:
    """the simulator without a clock of its own: it moves 50 ms each time step() is called"""

    def __init__(self, user=None):
        import fcl_sim
        self.sim = fcl_sim.Sim("bridge", user=user)
        self.sim.command("sim buttons off")
        self.name, self.step_s = "simulator (stepped)", fcl_sim.STEP_S
        self.q = queue.Queue()
        self._drain()

    def _drain(self):
        for line in self.sim.lines:
            self.q.put(line)
        del self.sim.lines[:]

    def step(self):
        for line in self.sim.step():
            self.q.put(line)

    def send(self, line):
        self.sim.command(line)
        self._drain()

    def close(self):
        self.sim.close()


def connect(where, realtime=True, user=None):
    """where: "sim", a serial port name, "tcp:host:port" or "replay:file.log" -> Unit"""
    import fcl_dash
    if where == "sim" and not realtime:
        return Unit(_Stepped(user))
    if where == "sim":
        src = fcl_dash.SimSource("bridge")
        src.send("sim buttons off")
        return Unit(src)
    if where.startswith("replay:"):
        return Unit(fcl_dash.ReplaySource(where[7:], 1.0))

    class A:
        replay, sim, hub, speed = None, False, "auto", 1.0
        tcp = where[4:] if where.startswith("tcp:") else None
        port = None if where.startswith("tcp:") else where
    return Unit(fcl_dash.open_source(A))


class Unit:
    def __init__(self, source):
        self.src = source
        self.t = {}                  # the last telemetry frame
        self.frames = 0
        self.rows = {}               # LCD rows written by the page or the menu ($L lines)
        self.events = []             # event names ($E lines), oldest first
        self.info = []               # $I lines
        self.cal = {}                # calibration values, after command("cal")
        self.graphics = (0, 0, 0, 0, 0)
        self._points, self._replies, self._new = [], [], []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        self.src.close()

    # ---- the stream
    def _line(self, line):
        r = fcl_usb.parse_line(line)
        if not r:
            return
        k, v = r
        if k == "T":
            self.t = v
            self.frames += 1
            self._new.append(v)
        elif k == "R":
            self._replies.append(v)
        elif k == "L":
            text = line.split(",", 2)[2] if line.count(",") >= 2 else ""
            if text:
                self.rows[int(v[0])] = text
            else:
                self.rows.pop(int(v[0]), None)
        elif k == "E":
            self.events.append(v[0])
        elif k == "I":
            self.info.append(v[0])
        elif k == "C":
            for item in v:
                name, _, val = item.partition("=")
                self.cal[name] = float(val)
        elif k == "H" and len(v) == 5:
            self.graphics = tuple(int(x) for x in v)
        elif k == "P" and len(v) == 7:
            p = dict(zip(("heading", "pitch", "dist", "x", "y", "z"), (float(x) for x in v[1:])))
            p["n"] = int(v[0])
            self._points = [q for q in self._points if q["n"] != p["n"]] + [p]

    def _pump(self):
        while True:
            try:
                self._line(self.src.q.get_nowait())
            except queue.Empty:
                return

    def wait(self, seconds):
        """let time pass (the unit's own time with a stepped simulator, the clock's otherwise)"""
        if hasattr(self.src, "step"):
            for _ in range(int(round(seconds / self.src.step_s))):
                self.src.step()
            return self._pump()
        end = time.time() + seconds
        while time.time() < end:
            self._pump()
            time.sleep(0.01)
        self._pump()

    def telemetry(self, seconds=None, count=None):
        """yield telemetry frames as they come: for `seconds`, or `count` frames, or without end"""
        self._pump()
        del self._new[:]
        t0, n = None, 0
        idle = 0
        while True:
            if not self._new:
                self.wait(0.05)
                idle += 1
                if idle > 200:
                    raise Error("no telemetry for 10 s")
                continue
            idle = 0
            t = self._new.pop(0)
            t0 = t["t_ms"] if t0 is None else t0
            if seconds is not None and t["t_ms"] - t0 > seconds * 1000:
                return
            yield t
            n += 1
            if count is not None and n >= count:
                return

    def command(self, line, timeout=3.0):
        """send one command; -> the text of its reply.  Raises Error on $R,err or when no reply comes."""
        self._pump()
        del self._replies[:]
        self.src.send(line)
        waited = 0.0
        while not self._replies:
            if waited >= timeout:
                raise Error("no reply to '%s'" % line)
            self._pump()
            if not self._replies:
                if hasattr(self.src, "step"):
                    self.src.step()
                    waited += self.src.step_s
                else:
                    time.sleep(0.01)
                    waited += 0.01
        ok, text = (self._replies[0] + [""])[:2]
        if ok != "ok":
            raise Error(text)
        return text

    # ---- readings
    def _v(self, k):
        return self.t.get(k)

    heading = property(lambda self: self._v("heading"))
    pitch = property(lambda self: self._v("pitch"))
    roll = property(lambda self: self._v("roll"))
    height = property(lambda self: self._v("alt_m"))
    pressure = property(lambda self: None if not self.t else self.t["press_hpa"])
    flags = property(lambda self: self._v("flags"))

    @property
    def distance(self):
        """metres, or None when the ranger sees nothing"""
        if not self.t or not self.t["flags"] & TF_TOF_VALID:
            return None
        return self.t["dist_mm"] / 1000.0

    @property
    def cells(self):
        """[(volts, percent or None, degrees C)]"""
        if not self.t:
            return []
        return [(self.t["cell%d_mv" % i] / 1000.0, None if self.t["soc%d" % i] == 255 else self.t["soc%d" % i], self.t["temp%d_c" % i])
                for i in (1, 2, 3)]

    @property
    def page_name(self):
        m = self.t.get("mode", 0)
        return PAGES[m] if m < len(PAGES) else "page %d" % m

    # ---- actions
    def key(self, name):
        """"B1" next page, "B2" the page's action, "B1L" menu"""
        return self.command("key " + name)

    def page(self, which):
        """a page by number or name: overview, level, height, bearing, survey"""
        n = PAGES.index(which) if which in PAGES else int(which)
        return self.command("mode %d" % n)

    def servo(self, n, us):
        return self.command("servo %d %s" % (n, us if us else "off"))

    def zero(self):
        return self.command("zero")

    def view(self, edges):
        return self.command("view " + ("edges" if edges else "camera"))

    def hud(self, *items):
        """graphics on every page: "reticle", "horizon", "tape", "all"; nothing = off"""
        return self.command("hud " + (" ".join(items) if items else "off"))

    def points(self, clear=False):
        """the Survey page's points, in the order taken"""
        self._points = []
        self.command("points clear" if clear else "points")
        return sorted(self._points, key=lambda p: p["n"])

    def calibration(self):
        self.command("cal")
        return dict(self.cal)


if __name__ == "__main__":
    with connect(sys.argv[1] if len(sys.argv) > 1 else "sim") as u:
        u.wait(2)
        print("heading %.1f  pitch %.1f  roll %.1f  height %+.2f m  distance %s  page %s" %
              (u.heading, u.pitch, u.roll, u.height, "%.2f m" % u.distance if u.distance is not None else "out of range", u.page_name))
