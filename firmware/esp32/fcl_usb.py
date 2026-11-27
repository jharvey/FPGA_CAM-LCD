# FCL USB serial protocol: text lines over the ESP32-S3's USB serial port (or a TCP socket from the simulator).
# The same file runs on the ESP32 (MicroPython, driven by fcl_usbdev.py) and on a PC (simulator, dashboard, tests).
#
# Device -> PC, one record per line:
#   $T,<fields>            telemetry, see T_FIELDS (default 10 lines per second)
#   $E,<name>              hub event: B1, B2, PWR_SHORT, PWR_OFF, CELL_LOW, CELL_CUTOFF
#   $B,<button>,<0|1>      button released / pressed: PWR, B1, B2
#   $S,<us1>,...,<us6>     servo pulse widths last commanded over USB (0 = off / not set)
#   $W,<state>,<ssid>,<ip>,<rssi>     Wi-Fi: off | connecting | connected | failed
#   $A,<seq>,<rate>,<base64>          microphone audio, 16-bit little-endian mono PCM
#   $M,<state>,<x>,<y>,<z>,<field>,<error %>,<readings>,<directions>,<auto|fixed>     compass calibration:
#                          state none | auto | manual | manual-running | stored; offset and field in milligauss
#   $R,ok|err,<text>       reply to a command
#   $I,<text>              information (help text, scan results, version)
#
# PC -> device, one command per line (see HELP).
try:
    from ubinascii import b2a_base64, a2b_base64
except ImportError:
    from binascii import b2a_base64, a2b_base64

VERSION = "FCL USB protocol 1"
T_FIELDS = ("t_ms", "heading", "pitch", "roll", "alt_m", "press_hpa", "dist_mm", "cell1_mv", "cell2_mv", "cell3_mv",
            "vsys_mv", "temp1_c", "temp2_c", "temp3_c", "soc1", "soc2", "soc3", "buttons", "dot_x", "dot_y", "mode",
            "overlay", "flags", "sensors")
T_FLOAT = ("heading", "pitch", "roll", "alt_m", "press_hpa", "temp1_c", "temp2_c", "temp3_c")
BUTTONS = ("PWR", "B1", "B2")
OVERLAY = {"dot": 0x01, "heading": 0x02, "attitude": 0x04, "baro": 0x08, "dist": 0x10, "batt": 0x20, "all": 0x3F, "none": 0}
HELP = (
    "help                      this list",
    "status                    one $T line, $S, $W and the version",
    "stream on|off|<hz>        telemetry lines per second (1-20), default 10",
    "servo <1-6> <us|off>      servo pulse 500-2500 us; servo 1 stops following pitch",
    "follow on|off             servo 1 holds the camera level (pitch)",
    "mode <0-3>                display mode (same as B1)",
    "overlay <items>|<mask>    LCD overlay: dot heading attitude baro dist batt | all | none | number",
    "zero                      make the present height 0",
    "magcal                    compass calibration status ($M line)",
    "magcal start | stop       calibrate by hand: point the unit up, down and to the four sides",
    "magcal auto on|off        keep refining the calibration in use (default on);  magcal reset",
    "wifi <ssid> <password>    save the network and connect;  wifi status | scan | off",
    "mic on|off [rate]         microphone to $A lines (8000 or 16000 Hz)",
    "spk <rate> <base64>       play 16-bit mono PCM on the speaker;  spk off",
    "tone <hz> <ms>            test tone on the speaker",
    "repl                      leave the stream and go back to the MicroPython prompt",
)


def telemetry_line(t):
    out = []
    for k in T_FIELDS:
        if k == "press_hpa":
            out.append("%.2f" % (t["press_pa"] / 100.0))
        elif k == "dist_mm":
            out.append("%d" % t["tof_mm"])
        elif k in ("heading", "pitch", "roll", "alt_m"):
            out.append("%.2f" % t[k])
        elif k in T_FLOAT:
            out.append("%.1f" % t[k])
        else:
            out.append("%d" % t[k])
    return "$T," + ",".join(out)


def parse_line(line):
    """PC side: ('T', dict) for telemetry, else (letter, [fields]); None for anything else (boot text, REPL)."""
    line = line.strip()
    if len(line) < 3 or line[0] != "$" or line[2] != ",":
        return None
    kind, rest = line[1], line[3:]
    if kind == "T":
        v = rest.split(",")
        if len(v) != len(T_FIELDS):
            return None
        try:
            return "T", dict((k, float(x) if k in T_FLOAT else int(x)) for k, x in zip(T_FIELDS, v))
        except ValueError:
            return None
    if kind in "RI":
        return kind, rest.split(",", 1) if kind == "R" else [rest]
    return kind, rest.split(",")


class Bridge:
    """Glue between the hub link (fcl_hub), the USB text port and the platform (Wi-Fi, audio).

    hub   module or object with last, servo(ch, us), mode(m), overlay(mask), zero_alt(), follow(on)
    out   function(str): send one line to the PC
    plat  object with wifi_set(ssid, pw), wifi_status(), wifi_scan(), wifi_off(), mic(on, rate), spk(rate, pcm),
          tone(hz, ms), and optionally extra(cmd, args) for more commands; any method may be missing
    """

    def __init__(self, hub, out, plat=None):
        self.hub, self.out, self.plat = hub, out, plat
        self.rate = 10
        self.streaming = True
        self.exit = False
        self.servos = [0] * 6
        self._div = 0
        self._btn = 0
        self._aseq = 0

    # ---- hub -> USB
    def on_telemetry(self, t):
        b = t.get("buttons", 0)
        if b != self._btn:
            for i, name in enumerate(BUTTONS):
                if (b ^ self._btn) >> i & 1:
                    self.out("$B,%s,%d" % (name, b >> i & 1))
            self._btn = b
        self._div += self.rate
        if self.streaming and self._div >= 20:          # the hub sends 20 frames per second
            self._div -= 20
            self.out(telemetry_line(t))
        elif self._div >= 20:
            self._div -= 20

    def on_event(self, name):
        self.out("$E," + name)

    def audio(self, rate, pcm):
        self._aseq = (self._aseq + 1) & 0xFFFF
        self.out("$A,%d,%d,%s" % (self._aseq, rate, b2a_base64(pcm).decode().strip()))

    # ---- USB -> hub / platform
    def _ok(self, text=""):
        self.out("$R,ok," + text)

    def _err(self, text):
        self.out("$R,err," + text)

    def _plat(self, name):
        f = getattr(self.plat, name, None) if self.plat is not None else None
        if f is None:
            self._err(name.split("_")[0] + " not available here")
        return f

    def wifi_line(self):
        f = getattr(self.plat, "wifi_status", None) if self.plat is not None else None
        st = f() if f else ("off", "", "", 0)
        self.out("$W,%s,%s,%s,%d" % st)

    def command(self, line):
        a = line.strip().split()
        if not a:
            return
        c, a = a[0].lower(), a[1:]
        try:
            self._command(c, a, line)
        except (ValueError, IndexError):
            self._err("bad arguments: " + c + " (try help)")

    def _command(self, c, a, line):
        hub = self.hub
        if c == "help":
            for h in HELP:
                self.out("$I," + h)
            self._ok("help")
        elif c == "ping":
            self._ok("pong")
        elif c == "status":
            self.out("$I," + VERSION)
            if hub.last:
                self.out(telemetry_line(hub.last))
            self.out("$S," + ",".join("%d" % u for u in self.servos))
            self.wifi_line()
            self._ok("status")
        elif c == "stream":
            if a[0] == "on":
                self.streaming = True
            elif a[0] == "off":
                self.streaming = False
            else:
                r = int(a[0])
                if not 1 <= r <= 20:
                    return self._err("stream rate 1-20")
                self.rate, self.streaming = r, True
            self._ok("stream %s %d" % ("on" if self.streaming else "off", self.rate))
        elif c == "servo":
            ch = int(a[0])
            us = 0 if a[1] == "off" else int(a[1])
            if not 1 <= ch <= 6 or (us and not 500 <= us <= 2500):
                return self._err("servo 1-6, 500-2500 us or off")
            hub.servo(ch - 1, us)
            self.servos[ch - 1] = us
            self.out("$S," + ",".join("%d" % u for u in self.servos))
            self._ok("servo %d %d" % (ch, us))
        elif c == "follow":
            on = a[0] == "on"
            hub.follow(on)
            self._ok("follow " + ("on" if on else "off"))
        elif c == "mode":
            m = int(a[0])
            if not 0 <= m <= 3:
                return self._err("mode 0-3")
            hub.mode(m)
            self._ok("mode %d" % m)
        elif c == "overlay":
            mask = 0
            for w in a:
                w = w.lower()
                mask |= OVERLAY[w] if w in OVERLAY else int(w, 0)
            hub.overlay(mask & 0x3F)
            self._ok("overlay 0x%02X" % (mask & 0x3F))
        elif c == "zero":
            hub.zero_alt()
            self._ok("zero")
        elif c == "magcal":
            f = getattr(hub, "magcal", None)
            if f is None:
                return self._err("magcal not available with this hub")
            self._ok(f(a))
        elif c == "wifi":
            if not a or a[0] == "status":
                self.wifi_line()
                self._ok("wifi")
            elif a[0] == "scan":
                f = self._plat("wifi_scan")
                if f:
                    for ssid, rssi in f():
                        self.out("$I,wifi %d dBm %s" % (rssi, ssid))
                    self._ok("wifi scan")
            elif a[0] == "off":
                f = self._plat("wifi_off")
                if f:
                    f()
                    self.wifi_line()
                    self._ok("wifi off")
            else:
                f = self._plat("wifi_set")
                if f:
                    # the password is everything after the SSID, so it may contain spaces
                    rest = line.strip().split(None, 2)
                    f(a[0], rest[2] if len(rest) > 2 else "")
                    self.wifi_line()
                    self._ok("wifi saved " + a[0])
        elif c == "mic":
            f = self._plat("mic")
            if f:
                on = a[0] == "on"
                rate = int(a[1]) if len(a) > 1 else 16000
                if rate not in (8000, 16000):
                    return self._err("mic rate 8000 or 16000")
                f(on, rate)
                self._ok("mic %s %d" % ("on" if on else "off", rate))
        elif c == "spk":
            f = self._plat("spk")
            if f:
                if a[0] == "off":
                    f(0, b"")
                    return self._ok("spk off")
                pcm = a2b_base64(a[1])
                f(int(a[0]), pcm)             # no reply per chunk: keeps the stream light
        elif c == "tone":
            f = self._plat("tone")
            if f:
                f(int(a[0]), int(a[1]))
                self._ok("tone %s Hz %s ms" % (a[0], a[1]))
        elif c == "repl":
            self.exit = True
            self._ok("repl")
        else:
            f = getattr(self.plat, "extra", None) if self.plat is not None else None
            r = f(c, a) if f else None
            if r is None:
                self._err("unknown command: " + c + " (try help)")
            else:
                self._ok(r)
