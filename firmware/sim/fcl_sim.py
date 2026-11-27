#!/usr/bin/env python3
"""FCL simulator: a whole unit on the PC, speaking the USB serial protocol (firmware/esp32/fcl_usb.py).

    python firmware/sim/fcl_sim.py                 serve the stream on TCP 127.0.0.1:7007
    python firmware/tools/fcl_dash.py --sim        or run it inside the dashboard, no socket

What is real and what is simulated
    hub        the real hub firmware (firmware/common, built as sim/fcl_sim_live by `make -C firmware/sim all`)
               running against register-level sensor models, when that program exists;
               otherwise a Python stand-in (PyHub) that produces the same link frames from the truth directly
    ESP32      the real protocol code (fcl_hub.py, fcl_usb.py); Wi-Fi and audio are stand-ins
    the world  a 60 s demo loop: pan, look straight down, tilt, climb 3 m, button presses, cells running down

Extra commands (simulator only):
    sim set <heading|pitch|roll|alt|dist|cell1|cell2|cell3|temp1|temp2|temp3> <value>     hold a value
    sim auto                                          back to the demo loop
    sim press <PWR|B1|B2> [ms]                        press a button (default 300 ms)
"""
import math
import os
import select
import socket
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "esp32"))
sys.path.insert(0, HERE)
import fcl_hub      # noqa: E402
import fcl_usb      # noqa: E402
import fcl_osd      # noqa: E402

TICKS_PER_STEP = 10         # 200 Hz hub ticks -> 20 steps (telemetry frames) per second
STEP_S = TICKS_PER_STEP / 200.0
KEYS = ("heading", "pitch", "roll", "alt", "dist", "cell1", "cell2", "cell3", "temp1", "temp2", "temp3")


RATE = {"heading": 90.0, "pitch": 90.0, "roll": 90.0, "alt": 1.0, "dist": 2000.0}    # per second, for held values


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


class Scenario:
    """the truth as a function of time, with values that can be held by hand"""

    def __init__(self):
        self.hold = {}          # values held by hand (targets)
        self.cur = {}           # where the held values are now: they move at a hand's speed, not in one step
        self.press = {}         # button index -> release time
        self.last_t = 0.0

    def at(self, t):
        m = t % 60.0
        s = {"heading": 30.0 + 12.0 * t}
        if m < 10:
            pitch, roll = 5 * math.sin(2 * math.pi * m / 5), 3 * math.sin(2 * math.pi * m / 3.3)
        elif m < 16:
            pitch, roll = -90 * _smooth((m - 10) / 6), 0.0
        elif m < 20:
            pitch, roll = -90 + 3 * math.sin(2 * math.pi * (m - 16) / 2), 3 * math.sin(2 * math.pi * (m - 16) / 1.5)
        elif m < 26:
            pitch, roll = -90 * (1 - _smooth((m - 20) / 6)), 0.0
        else:
            k = _smooth((m - 26) / 2) * _smooth((60 - m) / 2)
            pitch, roll = 12 * k * math.sin(2 * math.pi * (m - 26) / 7), 15 * k * math.sin(2 * math.pi * (m - 26) / 5)
        s["pitch"], s["roll"] = pitch, roll
        s["alt"] = 3.0 * (_smooth((m - 40) / 8) - _smooth((m - 52) / 6))
        s["dist"] = 1500 + 900 * math.sin(2 * math.pi * t / 13)
        s["cell1"] = max(3.3, 4.05 - 0.0004 * t)
        s["cell2"] = max(3.3, 3.98 - 0.0004 * t)
        s["cell3"] = max(3.25, 3.70 - 0.002 * t)
        s["temp1"], s["temp2"], s["temp3"] = 25.0, 26.0, min(45.0, 27.0 + 0.03 * t)
        dt = max(0.0, t - self.last_t)
        self.last_t = t
        for k in list(self.cur):
            if k not in self.hold:
                del self.cur[k]
        for k, target in self.hold.items():
            rate = RATE.get(k)
            c = self.cur.get(k, s[k])
            if rate is None:
                c = target
            else:
                c += max(-rate * dt, min(rate * dt, target - c))
            self.cur[k] = s[k] = c
        btn = 0
        for i, (a, b) in enumerate(((45.0, 45.2), (5.0, 5.3), (30.0, 30.3))):       # PWR short, B1, B2
            if a <= m < b:
                btn |= 1 << i
        for i, until in list(self.press.items()):
            if t < until:
                btn |= 1 << i
            else:
                del self.press[i]
        return s, btn


class CHub:
    """the real hub firmware, stepped through sim/fcl_sim_live"""
    name = "hub firmware (C)"

    def __init__(self, exe):
        self.p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, bufsize=1)

    def step(self, s, btn, rx):
        self.p.stdin.write("S %d %s %d %s\n" % (TICKS_PER_STEP, " ".join("%.5f" % s[k] for k in KEYS), btn,
                                               rx.hex() if rx else "-"))
        self.p.stdin.flush()
        r = self.p.stdout.readline().split()
        o = self.p.stdout.readline()
        tx = b"" if r[1] == "-" else bytes.fromhex(r[1])
        v = [int(x) for x in r[2:]]
        return tx, {"servo": v[0:6], "led": v[6:8], "power_hold": v[8], "dot": (v[9], v[10], v[11]),
                    "osd": [row.replace("_", " ") for row in o[2:].rstrip("\r\n").split("|")]}

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=2)
        except Exception:
            self.p.kill()


class PyHub:
    """stand-in for the hub when the C program is not built: the same frames, made from the truth directly
    (no sensor models, no fusion filter)"""
    name = "Python stand-in"

    def __init__(self):
        self.t = 0.0
        self.mode, self.overlay, self.rec, self.follow = 0, 0x3F, False, True
        self.servo = [0] * 6
        self.alt0 = None
        self.btn = 0
        self.pwr_t = None
        self.off = False
        self.low = False
        self.parser = fcl_hub.Parser()

    def step(self, s, btn, rx):
        self.t += STEP_S
        tx = b""
        for typ, p in self.parser.feed(rx or b""):
            if typ == fcl_hub.MSG_CMD_SERVO and len(p) == 3:
                self.follow = False
                ch, us = struct.unpack("<BH", p)
                if ch < 6:
                    self.servo[ch] = us
            elif typ == fcl_hub.MSG_CMD_MODE:
                self.mode = p[0]
            elif typ == fcl_hub.MSG_CMD_OVERLAY:
                self.overlay = p[0] & 0x3F
            elif typ == fcl_hub.MSG_CMD_ZERO_ALT:
                self.alt0 = s["alt"]
            elif typ == fcl_hub.MSG_CMD_FOLLOW:
                self.follow = bool(p[0])
                if not self.follow:
                    self.servo[0] = 0
        ch = btn ^ self.btn
        if ch & 2 and btn & 2:
            self.mode = (self.mode + 1) % 4
            tx += fcl_hub.frame(fcl_hub.MSG_EVENT, b"\x01")
        if ch & 4 and btn & 4:
            self.rec = not self.rec
            tx += fcl_hub.frame(fcl_hub.MSG_EVENT, b"\x02")
        if ch & 1:
            if btn & 1:
                self.pwr_t = self.t
            elif not self.off:
                tx += fcl_hub.frame(fcl_hub.MSG_EVENT, b"\x03")
        if btn & 1 and not self.off and self.pwr_t is not None and self.t - self.pwr_t >= 2.0:
            self.off = True
            tx += fcl_hub.frame(fcl_hub.MSG_EVENT, b"\x04")
        self.btn = btn
        if self.off:
            return tx, {"servo": [0] * 6, "led": [0, 0], "power_hold": 0, "dot": (0, 0, 0), "osd": [" " * 30] * 15}
        if self.alt0 is None:
            self.alt0 = s["alt"]
        if self.follow:
            self.servo[0] = int(min(2000, max(1000, 1500 - 10 * s["pitch"])))
        mv = [int(round(s["cell%d" % i] * 1000)) for i in (1, 2, 3)]
        flags = (1 if self.rec else 0) | (8 if 0 < s["dist"] < 4000 else 0)
        live = [m for m in mv if m > 2500]
        low = any(m < 3400 for m in live)
        if low:
            flags |= 2
        if any(m < 3200 for m in live):
            flags |= 4
        if max(s["temp1"], s["temp2"], s["temp3"]) > 55:
            flags |= 16
        if low and not self.low:
            tx += fcl_hub.frame(fcl_hub.MSG_EVENT, b"\x05")
        self.low = low
        dx, dy, inside = fcl_osd.down_dot(s["pitch"], s["roll"])
        if inside:
            flags |= 32
        hd = s["heading"] % 360.0
        hcd = int(round(hd * 100))
        alt = s["alt"] - self.alt0
        press = 101325.0 * (1 - s["alt"] / 44330.0) ** 5.255
        p = struct.pack("<IhhhiIHHHHHhhhBBBBBBhhBB", int(self.t * 1000) & 0xFFFFFFFF, hcd - 36000 if hcd > 32767 else hcd,
                        int(round(s["pitch"] * 100)), int(round(s["roll"] * 100)), int(round(alt * 100)), int(round(press)),
                        int(s["dist"]), mv[0], mv[1], mv[2], int(round((max(mv) - 50))),
                        int(round(s["temp1"] * 10)), int(round(s["temp2"] * 10)), int(round(s["temp3"] * 10)),
                        self.mode, flags, fcl_osd.soc_from_mv(mv[0]), fcl_osd.soc_from_mv(mv[1]), fcl_osd.soc_from_mv(mv[2]),
                        btn & 7, dx, dy, self.overlay, 0x1F)
        tx += fcl_hub.frame(fcl_hub.MSG_TELEMETRY, p)
        t = fcl_hub.decode_telemetry(p)
        return tx, {"servo": list(self.servo), "led": [1, int(self.rec)], "power_hold": 1,
                    "dot": (dx, dy, self.overlay & 1), "osd": fcl_osd.osd_compose(t)}

    def close(self):
        pass


class SimPlat:
    """stand-ins for the ESP32's Wi-Fi and audio"""

    def __init__(self, sim):
        self.sim = sim
        self.wifi = ["off", "", "", 0]
        self.wifi_t = None
        self.mic_on, self.mic_rate, self.phase = False, 16000, 0.0
        self.spk_bytes, self.spk_rate, self.spk_level = 0, 0, 0
        self.tone_log = []

    def wifi_set(self, ssid, pw):
        self.wifi = ["connecting", ssid, "", 0]
        self.wifi_t = self.sim.t + (2.0 if len(pw) >= 8 or not pw else 1e9)

    def wifi_status(self):
        if self.wifi[0] == "connecting" and self.wifi_t is not None and self.sim.t >= self.wifi_t:
            self.wifi = ["connected", self.wifi[1], "192.168.1.57", -52]
        return tuple(self.wifi)

    def wifi_scan(self):
        return [("HomeNet", -48), ("Workshop", -63), ("Guest", -80)]

    def wifi_off(self):
        self.wifi = ["off", "", "", 0]

    def mic(self, on, rate):
        self.mic_on, self.mic_rate = on, rate

    def spk(self, rate, pcm):
        self.spk_rate = rate
        self.spk_bytes += len(pcm)
        if pcm:
            v = struct.unpack("<%dh" % (len(pcm) // 2), pcm[:len(pcm) // 2 * 2])
            self.spk_level = max(abs(x) for x in v) if v else 0

    def tone(self, hz, ms):
        self.tone_log.append((hz, ms))

    def pump(self, bridge):
        if not self.mic_on:
            return
        n = int(self.mic_rate * STEP_S)
        out = bytearray()
        for _ in range(n):                                   # a 440 Hz tone that swells once a second
            self.phase += 2 * math.pi * 440 / self.mic_rate
            amp = 4000 * (0.6 + 0.4 * math.sin(self.phase / 440))
            out += struct.pack("<h", int(amp * math.sin(self.phase)))
        bridge.audio(self.mic_rate, bytes(out))

    def extra(self, c, a):
        if c != "sim":
            return None
        sc = self.sim.scenario
        if a[0] == "auto":
            sc.hold.clear()
            return "sim auto"
        if a[0] == "set" and a[1] in KEYS:
            sc.hold[a[1]] = float(a[2])
            return "sim set %s %s" % (a[1], a[2])
        if a[0] == "press" and a[1].upper() in fcl_usb.BUTTONS:
            ms = int(a[2]) if len(a) > 2 else 300
            sc.press[fcl_usb.BUTTONS.index(a[1].upper())] = self.sim.t + ms / 1000.0
            return "sim press %s %d" % (a[1].upper(), ms)
        raise ValueError


def find_live():
    for n in ("fcl_sim_live.exe", "fcl_sim_live"):
        p = os.path.join(HERE, n)
        if os.path.isfile(p):
            return p
    return None


class Sim:
    def __init__(self, backend="auto"):
        exe = find_live() if backend in ("auto", "c") else None
        if backend == "c" and not exe:
            raise SystemExit("fcl_sim_live not built: make -C firmware/sim all")
        self.hub = CHub(exe) if exe else PyHub()
        self.scenario = Scenario()
        self.t = 0.0
        self.rx = bytearray()
        self.lines = []
        self.state = {"servo": [0] * 6, "led": [0, 0], "power_hold": 1, "dot": (0, 0, 0), "osd": [" " * 30] * 15}
        self.plat = SimPlat(self)
        # fcl_hub keeps its state in the module, as on the ESP32: one simulator per process
        fcl_hub.last, fcl_hub.frames, fcl_hub.crc_errors = {}, 0, 0
        del fcl_hub.events[:]
        fcl_hub._parser = fcl_hub.Parser()
        fcl_hub.send_raw = self.rx.extend
        self.bridge = fcl_usb.Bridge(fcl_hub, self.lines.append, self.plat)
        fcl_hub.on_telemetry = self.bridge.on_telemetry
        fcl_hub.on_event = self.bridge.on_event
        self.lines.append("$I," + fcl_usb.VERSION + " (simulator, " + self.hub.name + ")")
        self._w = 0.0

    def command(self, line):
        self.bridge.command(line)

    def step(self):
        """advance 50 ms; returns the lines the device sent"""
        self.t += STEP_S
        s, btn = self.scenario.at(self.t)
        rx = bytes(self.rx)
        del self.rx[:]
        tx, self.state = self.hub.step(s, btn, rx)
        fcl_hub.handle(tx)
        self.plat.pump(self.bridge)
        if self.t - self._w >= 5.0:
            self._w = self.t
            self.bridge.wifi_line()
        out = self.lines[:]
        del self.lines[:]
        return out

    def close(self):
        self.hub.close()


def serve(port, backend):
    sim = Sim(backend)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    print("FCL simulator (%s) on tcp 127.0.0.1:%d   Ctrl-C stops" % (sim.hub.name, port))
    print("connect with:  python firmware/tools/fcl_dash.py --tcp 127.0.0.1:%d" % port)
    client, buf = None, b""
    nxt = time.time()
    try:
        while True:
            wait = max(0.0, nxt - time.time())
            r, _, _ = select.select([srv] + ([client] if client else []), [], [], wait)
            for s in r:
                if s is srv:
                    if client:
                        client.close()
                    client, _ = srv.accept()
                    buf = b""
                    print("client connected")
                else:
                    try:
                        d = client.recv(65536)
                    except OSError:
                        d = b""
                    if not d:
                        client.close()
                        client = None
                        print("client gone")
                        continue
                    buf += d
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        sim.command(line.decode("utf-8", "replace"))
            if time.time() >= nxt:
                nxt += STEP_S
                if nxt < time.time() - 1:
                    nxt = time.time()
                lines = sim.step()
                if client and lines:
                    try:
                        client.sendall(("\r\n".join(lines) + "\r\n").encode())
                    except OSError:
                        client.close()
                        client = None
    except KeyboardInterrupt:
        pass
    finally:
        sim.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=7007)
    ap.add_argument("--hub", choices=("auto", "c", "python"), default="auto", help="hub back end (auto: C if built)")
    a = ap.parse_args()
    serve(a.port, a.hub)
