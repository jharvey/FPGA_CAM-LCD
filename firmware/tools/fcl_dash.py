#!/usr/bin/env python3
"""FCL dashboard: a full-screen text view of the USB serial stream (firmware/esp32/fcl_usb.py).

    python firmware/tools/fcl_dash.py --sim                 built-in simulator, no hardware
    python firmware/tools/fcl_dash.py --port COM7           the unit on USB (Linux: /dev/ttyACM0); needs pyserial
    python firmware/tools/fcl_dash.py --tcp 127.0.0.1:7007  a running firmware/sim/fcl_sim.py
    python firmware/tools/fcl_dash.py --replay trip.log     play a recorded stream again (--speed 4: four times as fast)

Type a command and press Enter (help lists them); Esc or Ctrl-C quits.  Local commands start with "!":
    !wav <file.wav>     record the microphone stream to a WAV file (send "mic on" first); !wav stops
    !play <file.wav>    send a 16-bit mono WAV file to the speaker
    !log <file.csv>     write every telemetry line to a CSV file; !log stops
    !log <file.log>     write the whole stream as it is (telemetry, events, buttons, LCD rows): this can be
                        replayed with --replay and read with firmware/tools/fcl_log.py

No curses needed: it draws with ANSI escape codes (Windows Terminal, PowerShell, cmd on Windows 10+, any
Linux / macOS terminal).  --snapshot prints one frame as plain text and exits (used for the documentation).
"""
import base64
import collections
import os
import queue
import sys
import threading
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "esp32"))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
import fcl_usb      # noqa: E402

W1, W2, W3 = 38, 25, 41                 # inner widths of the three columns
FULL = W1 + W2 + W3 + 2
CARD = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
FLAGS = ((1, "REC"), (2, "LOW"), (4, "CUTOFF"), (16, "HOT"), (64, "EDGES"), (128, "MENU"), (256, "LOG"))
PAGES = ("overview", "level", "height", "bearing", "survey")
SENSORS = ("IMU", "compass", "baro", "dist", "ADC")
OVERLAY = ("dot", "heading", "attitude", "baro", "dist", "batt")


def gauge(v, lo, hi, n):
    k = 0 if hi <= lo else int(round(n * min(1.0, max(0.0, (v - lo) / float(hi - lo)))))
    return "█" * k + "░" * (n - k)


def slider(v, lo, hi, n):
    k = int(round((n - 1) * min(1.0, max(0.0, (v - lo) / float(hi - lo)))))
    return "─" * k + "●" + "─" * (n - 1 - k)


def compass(hd, n=35):
    """a tape of n characters, 5 degrees each, centred on the heading"""
    out = []
    for i in range(n):
        d = int(round((hd + (i - n // 2) * 5) / 5.0)) * 5 % 360
        out.append("·" if d % 45 else None)
        if d % 45 == 0:
            out[-1] = CARD[d // 45]
    s = ""
    skip = 0
    for c in out:                        # two-letter marks take the next cell too
        if skip:
            skip -= 1
            continue
        s += c
        skip = len(c) - 1
    return s[:n].ljust(n)


class Dash:
    def __init__(self):
        self.t = None
        self.log = collections.deque(maxlen=7)
        self.servos = [0] * 6
        self.wifi = ["off", "", "", "0"]
        self.mag = None
        self.info = ""
        self.buttons = 0
        self.lines = 0
        self.rate = 0.0
        self._rt, self._rn = time.time(), 0
        self.audio_n = self.audio_rate = self.audio_peak = self.audio_lost = 0
        self._aseq = None
        self.input = ""
        self.wav = None
        self.csv = None
        self.raw = None                  # !log <file.log>: the stream as it is
        self.lcd = {}                    # LCD rows written by the unit's page or menu ($L lines)
        self.source = ""

    def note(self, text):
        self.log.append(text)

    def feed(self, line):
        r = fcl_usb.parse_line(line)
        if not r:
            return
        kind, v = r
        self.lines += 1
        if self.raw and kind in "TEBLMSWCHP":
            self.raw.write(line.strip() + "\n")
        if kind == "T":
            self.t = v
            self.buttons = v["buttons"]
            self._rn += 1
            now = time.time()
            if now - self._rt >= 1.0:
                self.rate, self._rt, self._rn = self._rn / (now - self._rt), now, 0
            if self.csv:
                self.csv.write(line.strip()[3:] + "\n")
        elif kind == "E":
            self.note("event   " + v[0])
        elif kind == "B":
            self.note("button  %s %s" % (v[0], "pressed" if v[1] == "1" else "released"))
        elif kind == "R":
            self.note(("ok      " if v[0] == "ok" else "ERROR   ") + (v[1] if len(v) > 1 else ""))
        elif kind == "I":
            if v[0].startswith("FCL USB"):
                self.info = v[0]
            else:
                self.note("        " + v[0])
        elif kind == "S":
            self.servos = [int(x) for x in v[:6]]
        elif kind == "L":
            text = line.strip().split(",", 2)[2] if line.count(",") >= 2 else ""
            try:
                if text.strip():
                    self.lcd[int(v[0])] = text
                else:
                    self.lcd.pop(int(v[0]), None)
            except ValueError:
                pass
        elif kind == "C":
            self.note("cal     " + " ".join(v))
        elif kind == "H":
            try:
                self.hud = int(v[0])
            except ValueError:
                pass
        elif kind == "P" and len(v) == 7:
            self.note("point   %s: heading %s, pitch %s, %s m  ->  east %s, north %s, up %s m" % tuple(v))
        elif kind == "M":
            self.mag = v
        elif kind == "W":
            self.wifi = (v + ["", "", "", "0"])[:4]
        elif kind == "A":
            try:
                seq, rate, pcm = int(v[0]), int(v[1]), base64.b64decode(v[2])
            except (ValueError, IndexError):
                return
            if self._aseq is not None and seq != (self._aseq + 1) & 0xFFFF:
                self.audio_lost += 1
            self._aseq = seq
            self.audio_n += len(pcm) // 2
            self.audio_rate = rate
            pk = 0
            for i in range(0, len(pcm) - 1, 2):
                s = pcm[i] | pcm[i + 1] << 8
                s = s - 65536 if s > 32767 else s
                pk = max(pk, abs(s))
            self.audio_peak = pk
            if self.wav:
                if self.wav.getnframes() == 0:
                    self.wav.setframerate(rate)
                self.wav.writeframes(pcm)

    def lcd_grid(self):
        """the 15 LCD text rows as the unit shows them: the standard overlay (empty while the menu is open)
        with the rows of the page or the menu on top"""
        import fcl_calc
        t = dict(self.t, press_pa=int(self.t["press_hpa"] * 100 + 0.5), tof_mm=self.t["dist_mm"])
        grid = [" " * 30] * 15 if t["flags"] & 128 else fcl_calc.osd_compose(t)
        for r, text in self.lcd.items():
            if 0 <= r < 15:
                grid[r] = text[:30].ljust(30)
        return grid

    # ---------------------------------------------------------------- drawing
    def _attitude(self):
        t = self.t
        hd = t["heading"] % 360
        return ["Heading  %5.1f°  %s" % (hd, CARD[int((hd + 22.5) // 45) % 8]),
                " " + compass(hd),
                " " + " " * 17 + "▲",
                "Pitch  %+6.1f°  %s" % (t["pitch"], slider(t["pitch"], -90, 90, 21)),
                "Roll   %+6.1f°  %s" % (t["roll"], slider(t["roll"], -90, 90, 21)),
                "               -90       0      +90",
                "",
                "Sensors  " + " ".join(n if t["sensors"] >> i & 1 else n.upper() + "!" for i, n in enumerate(SENSORS))]

    def _dot(self):
        t = self.t
        import math
        rows = [[" "] * 23 for _ in range(7)]            # the round LCD as 23 x 7 characters
        for k in range(120):
            a = math.radians(k * 3)
            rows[3 + int(round(3 * math.sin(a)))][11 + int(round(11 * math.cos(a)))] = "·"
        rows[3][11] = "+"
        on = t["overlay"] & 1
        if on:
            x = 11 + int(round(t["dot_x"] / 240.0 * 11))
            y = 3 + int(round(t["dot_y"] / 240.0 * 3))
            rows[max(0, min(6, y))][max(0, min(22, x))] = "●" if t["flags"] & 32 else "◆"
        state = "off" if not on else ("in view" if t["flags"] & 32 else "on the rim")
        return [" " + "".join(r) for r in rows] + [" %+4d,%+4d  %s" % (t["dot_x"], t["dot_y"], state)]

    def _battery(self):
        t = self.t
        out = []
        for i in (1, 2, 3):
            soc, mv, c = t["soc%d" % i], t["cell%d_mv" % i], t["temp%d_c" % i]
            if soc == 255:
                out.append("Cell %d  %s   --   no cell" % (i, "░" * 10))
            else:
                out.append("Cell %d  %s %3d%%  %.2f V  %4.1f°C" % (i, gauge(soc, 0, 100, 10), soc, mv / 1000.0, c))
        fl = [n for b, n in FLAGS[1:] if t["flags"] & b]
        out += ["", "VSYS    %.2f V" % (t["vsys_mv"] / 1000.0), "Status  " + (" ".join(fl) if fl else "ok"),
                "(charge estimated from cell voltage)", ""]
        return out

    def _env(self):
        t = self.t
        d = t["dist_mm"] / 1000.0
        valid = t["flags"] & 8
        return ["Height    %+7.2f m   (zero: 'zero')" % t["alt_m"],
                "Pressure  %7.2f hPa" % t["press_hpa"],
                "Distance  %s  %s" % (("%5.2f m" % d) if valid else "  ---  ", gauge(d if valid else 0, 0, 4, 14)),
                "                     0            4 m"]

    def _buttons(self):
        b = self.buttons
        names = ("PWR", "B1", "B2")
        top = " ".join("┌─────┐" for _ in names)
        mid = " ".join("│%s│" % (("█%s█" if b >> i & 1 else " %s ") % n.center(3)) for i, n in enumerate(names))
        bot = " ".join("└─────┘" for _ in names)
        held = [n for i, n in enumerate(names) if b >> i & 1]
        return [" " + top, " " + mid, " " + bot, " " + ("held: " + " ".join(held) if held else "none pressed")]

    def _servos(self):
        out = []
        for i in range(0, 6, 2):
            cell = []
            for j in (i, i + 1):
                us = self.servos[j]
                cell.append("%d %s %s" % (j + 1, ("%4d" % us) if us else " off", slider(us, 500, 2500, 9) if us else "─" * 9))
            out.append("  ".join(cell))
        out.append("us: 500 ─ 2500   servo <n> <us|off>")
        return out

    def render(self, ascii_only=False):
        """-> list of text lines (no colour codes)"""
        t = self.t
        if t is None:
            lines = ["FCL dashboard: waiting for telemetry from " + (self.source or "the device") + " ...", ""] + list(self.log)
            return lines + ["", "> " + self.input]

        def row3(a, b, c):
            return "│" + a[:W1].ljust(W1) + "│" + b[:W2].ljust(W2) + "│" + c[:W3].ljust(W3) + "│"

        def rule(l, m, r, t1, t2, t3):
            def seg(title, w):
                s = ("─ " + title + " ") if title else ""
                return s + "─" * (w - len(s))
            return l + seg(t1, W1) + m + seg(t2, W2) + m + seg(t3, W3) + r

        fl = [n for b, n in FLAGS if t["flags"] & b]
        ov = [n for i, n in enumerate(OVERLAY) if t["overlay"] >> i & 1]
        page = PAGES[t["mode"]] if t["mode"] < len(PAGES) else "page %d" % t["mode"]
        head = " FCL monocular   %s   t %.1f s   %.0f lines/s   page %d %s   %s" % (
            self.source, t["t_ms"] / 1000.0, self.rate, t["mode"], page, " ".join(fl) if fl else "")
        out = ["┌" + "─" * FULL + "┐", "│" + head[:FULL].ljust(FULL) + "│",
               rule("├", "┬", "┤", "ATTITUDE", "DOWN DOT (LCD view)", "BATTERY")]
        for a, b, c in zip(self._attitude(), self._dot(), self._battery()):
            out.append(row3(" " + a, b, " " + c))
        out.append(rule("├", "┼", "┤", "ENVIRONMENT", "BUTTONS", "SERVOS"))
        for a, b, c in zip(self._env(), self._buttons(), self._servos()):
            out.append(row3(" " + a, b, " " + c))
        out.append("├" + "─" * W1 + "┴" + "─" * W2 + "┴" + "─" * W3 + "┤")
        w = self.wifi
        wifi = "Wi-Fi  %s" % w[0] + ("  %s  %s  %s dBm" % (w[1], w[2], w[3]) if w[0] == "connected" else ("  " + w[1] if w[1] else ""))
        audio = "Audio  mic %d Hz, %d samples, peak %d%s" % (self.audio_rate, self.audio_n, self.audio_peak,
                                                             ", %d lost" % self.audio_lost if self.audio_lost else "") \
            if self.audio_n else "Audio  mic off  (mic on | tone <hz> <ms>)"
        m = self.mag
        if not m or len(m) < 9:
            mag = "Compass  calibration: no report yet (magcal)"
        elif m[0] == "none":
            mag = "Compass  not calibrated yet: it calibrates itself as the unit is turned (%s readings so far)" % m[6]
        elif m[0] == "manual-running":
            mag = "Compass  calibrating by hand: %s of 6 directions seen (up, down, 4 sides), %s readings" % (m[7], m[6])
        else:
            mag = "Compass  calibrated (%s): offset %s, %s, %s mG, field %s mG, fit error %s %%, %s" % (m[0], m[1], m[2], m[3], m[4], m[5], m[8])
        shown = "  |  ".join(self.lcd[r].strip() for r in sorted(self.lcd))
        lcd = "LCD    " + (("menu: " if t["flags"] & 128 else page + ": ") + shown if shown else
                         page + " (B1 or 'key B1': next page; hold B1 or 'key B1L': menu)")
        gfx = [n for i, n in enumerate(("reticle", "horizon", "tape")) if getattr(self, "hud", 0) >> i & 1]
        for s in (wifi + "    LCD overlay: " + (" ".join(ov) if ov else "none") + ("    graphics: " + " ".join(gfx) if gfx else ""), audio, mag, lcd):
            out.append("│ " + s[:FULL - 1].ljust(FULL - 1) + "│")
        out.append("├─ LOG " + "─" * (FULL - 6) + "┤")
        log = list(self.log)
        for i in range(self.log.maxlen):
            s = log[i] if i < len(log) else ""
            out.append("│ " + s[:FULL - 1].ljust(FULL - 1) + "│")
        out.append("└" + "─" * FULL + "┘")
        out.append("> " + self.input)
        if ascii_only:
            tr = {"┌": "+", "┐": "+", "└": "+", "┘": "+", "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+", "─": "-", "│": "|",
                  "█": "#", "░": ".", "●": "O", "◆": "X", "·": ".", "▲": "^", "°": " "}
            out = ["".join(tr.get(c, c) for c in s) for s in out]
        return out

    # ---------------------------------------------------------------- local commands
    def local(self, line, send):
        a = line.split()
        try:
            if a[0] == "!wav":
                if self.wav:
                    self.wav.close()
                    self.wav = None
                    self.note("local   WAV closed")
                if len(a) > 1:
                    self.wav = wave.open(a[1], "wb")
                    self.wav.setnchannels(1)
                    self.wav.setsampwidth(2)
                    self.wav.setframerate(16000)
                    self.note("local   recording the microphone stream to " + a[1])
            elif a[0] == "!log":
                for f in (self.csv, self.raw):
                    if f:
                        f.close()
                        self.note("local   log closed")
                self.csv = self.raw = None
                if len(a) > 1 and a[1].lower().endswith(".log"):
                    self.raw = open(a[1], "w")
                    self.note("local   recording the stream to " + a[1])
                elif len(a) > 1:
                    self.csv = open(a[1], "w")
                    self.csv.write(",".join(fcl_usb.T_FIELDS) + "\n")
                    self.note("local   logging telemetry to " + a[1])
            elif a[0] == "!play":
                w = wave.open(a[1], "rb")
                if w.getnchannels() != 1 or w.getsampwidth() != 2:
                    raise ValueError("need a 16-bit mono WAV")
                rate, n = w.getframerate(), 0
                while True:
                    pcm = w.readframes(rate // 25)              # 40 ms per line
                    if not pcm:
                        break
                    send("spk %d %s" % (rate, base64.b64encode(pcm).decode()))
                    n += len(pcm)
                    time.sleep(0.038)
                send("spk off")
                self.note("local   sent %d bytes of audio at %d Hz" % (n, rate))
            else:
                self.note("local   unknown: " + a[0])
        except (OSError, ValueError, IndexError, wave.Error) as e:
            self.note("local   error: %s" % e)


# -------------------------------------------------------------------- sources
class SimSource:
    def __init__(self, backend="auto", realtime=True):
        import fcl_sim
        self.sim = fcl_sim.Sim(backend)
        self.name = "simulator"
        self.step_s = fcl_sim.STEP_S
        self.q = queue.Queue()
        self.cmd = queue.Queue()
        self.run = True
        if realtime:
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        nxt = time.time()
        while self.run:
            while not self.cmd.empty():
                self.sim.command(self.cmd.get())
            for line in self.sim.step():
                self.q.put(line)
            nxt += self.step_s
            time.sleep(max(0.0, nxt - time.time()))

    def send(self, line):
        self.cmd.put(line)

    def close(self):
        self.run = False
        time.sleep(0.1)
        self.sim.close()


class StreamSource:
    """serial port or TCP socket"""

    def __init__(self, name, read, write, close):
        self.name, self._read, self._write, self._close = name, read, write, close
        self.q = queue.Queue()
        self.run = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        buf = b""
        while self.run:
            try:
                d = self._read()
            except Exception as e:
                self.q.put("$I,connection lost: %s" % e)
                return
            if not d:
                time.sleep(0.01)
                continue
            buf += d
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self.q.put(line.decode("utf-8", "replace"))

    def send(self, line):
        self._write((line + "\n").encode())

    def close(self):
        self.run = False
        self._close()


class ReplaySource:
    """a recorded stream (.log) played back at the speed it was recorded, or faster"""

    def __init__(self, path, speed=1.0):
        self.name = "replay " + os.path.basename(path)
        self.lines = [x.rstrip("\r\n") for x in open(path, encoding="utf-8", errors="replace")]
        self.q = queue.Queue()
        self.run = True
        self.speed = max(0.01, speed)
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        t0 = w0 = None
        for line in self.lines:
            if not self.run:
                return
            r = fcl_usb.parse_line(line)
            if r and r[0] == "T":
                t = r[1]["t_ms"] / 1000.0
                if t0 is None:
                    t0, w0 = t, time.time()
                time.sleep(max(0.0, min(2.0, (t - t0) / self.speed - (time.time() - w0))))
            self.q.put(line)
        self.q.put("$I,end of the recording")

    def send(self, line):
        self.q.put("$R,err,this is a recording: commands go nowhere")

    def close(self):
        self.run = False


def open_source(a):
    if a.replay:
        return ReplaySource(a.replay, a.speed)
    if a.sim:
        return SimSource(a.hub)
    if a.tcp:
        import socket
        host, port = a.tcp.rsplit(":", 1)
        s = socket.create_connection((host, int(port)))
        s.settimeout(0.2)

        def rd():
            try:
                d = s.recv(65536)
                if not d:
                    raise OSError("closed by the simulator")
                return d
            except socket.timeout:
                return b""
        return StreamSource("tcp " + a.tcp, rd, s.sendall, s.close)
    import serial
    ser = serial.Serial(a.port, 115200, timeout=0.05)
    return StreamSource(a.port, lambda: ser.read(4096), ser.write, ser.close)


# -------------------------------------------------------------------- keyboard
class Keys:
    def __init__(self):
        self.win = os.name == "nt"
        if self.win:
            import msvcrt
            self.m = msvcrt
        else:
            import termios
            import tty
            self.termios, self.fd = termios, sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)

    def get(self):
        """-> list of characters typed since the last call"""
        out = []
        if self.win:
            while self.m.kbhit():
                c = self.m.getwch()
                if c in ("\x00", "\xe0"):
                    self.m.getwch()
                else:
                    out.append(c)
        else:
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                out.append(sys.stdin.read(1))
        return out

    def close(self):
        if not self.win:
            self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.old)


def interactive(a):
    src = open_source(a)
    dash = Dash()
    dash.source = src.name
    if os.name == "nt":
        os.system("")                               # switches the Windows console to ANSI mode
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    keys = Keys()
    sys.stdout.write("\x1b[2J\x1b[?25l")
    src.send("status")
    try:
        while True:
            while not src.q.empty():
                dash.feed(src.q.get())
            for c in keys.get():
                if c in ("\x1b", "\x03"):
                    return
                if c in ("\r", "\n"):
                    line, dash.input = dash.input.strip(), ""
                    if line.startswith("!"):
                        dash.local(line, src.send)
                    elif line:
                        src.send(line)
                elif c in ("\x08", "\x7f"):
                    dash.input = dash.input[:-1]
                elif c.isprintable():
                    dash.input += c
            lines = dash.render(a.ascii)
            sys.stdout.write("\x1b[H" + "".join(s + "\x1b[K\n" for s in lines[:-1]) + lines[-1] + "\x1b[K\x1b[J")
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        keys.close()
        sys.stdout.write("\x1b[?25h\n")
        src.close()
        for f in (dash.wav, dash.csv, dash.raw):
            if f:
                f.close()


def snapshot(seconds, commands=(), backend="auto", ascii_only=False):
    """run the simulator without waiting and return (dash, sim) after `seconds`.
    commands: iterable of (time_s, text)"""
    src = SimSource(backend, realtime=False)
    dash = Dash()
    dash.source = src.name
    todo = sorted(commands)
    src.sim.command("status")
    while src.sim.t < seconds:
        while todo and todo[0][0] <= src.sim.t:
            src.sim.command(todo.pop(0)[1])
        for line in src.sim.step():
            dash.feed(line)
        dash.rate = 20.0 * src.sim.bridge.rate / 20.0 if src.sim.bridge.streaming else 0.0
    return dash, src.sim


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sim", action="store_true", help="run the built-in simulator")
    g.add_argument("--port", help="serial port of the unit, e.g. COM7 or /dev/ttyACM0")
    g.add_argument("--tcp", help="host:port of a running fcl_sim.py")
    g.add_argument("--replay", metavar="FILE", help="a recorded stream (.log) to play back")
    ap.add_argument("--speed", type=float, default=1.0, help="with --replay: playback speed")
    ap.add_argument("--hub", choices=("auto", "bridge", "c", "python"), default="auto", help="simulator hub back end")
    ap.add_argument("--ascii", action="store_true", help="plain ASCII frame characters")
    ap.add_argument("--snapshot", type=float, metavar="SECONDS", help="with --sim: print one frame after this time and exit")
    ap.add_argument("--cmd", action="append", default=[], metavar="T:COMMAND", help="with --snapshot: send COMMAND at time T")
    a = ap.parse_args()
    if a.snapshot is not None:
        if not a.sim:
            ap.error("--snapshot needs --sim")
        cmds = [(float(c.split(":", 1)[0]), c.split(":", 1)[1]) for c in a.cmd]
        d, s = snapshot(a.snapshot, cmds, a.hub)
        s.close()
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
        print("\n".join(d.render(a.ascii)))
    else:
        interactive(a)
