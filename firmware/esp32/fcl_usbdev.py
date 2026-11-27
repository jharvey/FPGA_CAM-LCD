# FCL USB serial stream on the ESP32-S3 (MicroPython).  DRAFT: written against the MicroPython ESP32 port's
# documented API and tested only through the PC simulator (the protocol half, fcl_usb.py); not yet run on hardware.
#
#   import fcl_usbdev; fcl_usbdev.run()      # main.py does this at the end of boot
#
# While it runs, the USB serial port carries the line protocol of fcl_usb.py instead of the Python prompt
# (Ctrl-C is disabled so binary-looking text cannot interrupt it).  The command "repl" returns to the prompt.
# The FTP server and the ECP5 programmer of esp32ecp5 keep working over Wi-Fi the whole time.
#
# Audio is carried inside the serial stream as base64 PCM lines.  It is not a USB sound card: MicroPython has no
# USB audio class.  The microphone and the amplifier share the I2S clock pins, and MicroPython's I2S is one
# direction per instance, so only one of them runs at a time (mic on stops the speaker and the other way round).
import sys
import select
import time
import math
import micropython
from machine import Pin, I2S, UART
import network
import fcl_bridge
import fcl_hubpy
import fcl_usb

I2S_BCLK, I2S_WS, I2S_SPK, I2S_MIC, AMP_SD = 35, 36, 37, 38, 47
CONF = "wifiman.conf"
LOG_FLASH_MAX = 2000000


@micropython.viper
def _s32_to_s16(src, dst, n: int):
    """n samples: 32-bit I2S words (24-bit mic data, left justified) -> 16-bit PCM"""
    s = ptr8(src)
    d = ptr8(dst)
    i = 0
    while i < n:
        d[2 * i] = s[4 * i + 2]
        d[2 * i + 1] = s[4 * i + 3]
        i += 1


class CalStore:
    """a small JSON file on the ESP32's flash: magcal.json (compass), cal.json (fcl_cfg.py)"""

    def __init__(self, name="magcal.json"):
        self.name = name

    def load(self):
        import json
        with open(self.name) as f:
            return json.load(f)

    def save(self, d):
        import json
        with open(self.name, "w") as f:
            json.dump(d, f)


class Plat:
    def __init__(self):
        self.sta = network.WLAN(network.STA_IF)
        self.ssid = ""
        self.i2s = None
        self.dir = None          # "rx" | "tx"
        self.rate = 16000
        self.amp = Pin(AMP_SD, Pin.OUT, value=0)
        self.raw = bytearray(4 * 320)       # 20 ms at 16 kHz
        self.pcm = bytearray(2 * 320)
        self.usb = None                     # fcl_usb.Bridge, set by run()
        self.logf, self.log_name, self.log_bytes = None, "", 0

    # ---- Wi-Fi
    def wifi_set(self, ssid, pw):
        lines = []
        try:
            with open(CONF) as f:
                lines = [x for x in f.read().split("\n") if x and not x.startswith(ssid + ":")]
        except OSError:
            pass
        lines.insert(0, ssid + ":" + pw)                  # same file and format as esp32ecp5's wifiman.py
        with open(CONF, "w") as f:
            f.write("\n".join(lines) + "\n")
        self.ssid = ssid
        self.sta.active(True)
        self.sta.disconnect()
        self.sta.connect(ssid, pw)

    def wifi_status(self):
        if not self.sta.active():
            return ("off", "", "", 0)
        if self.sta.isconnected():
            try:
                rssi = self.sta.status("rssi")
            except (ValueError, OSError):
                rssi = 0
            return ("connected", self.sta.config("essid"), self.sta.ifconfig()[0], rssi)
        st = self.sta.status()
        bad = st in (network.STAT_WRONG_PASSWORD, network.STAT_NO_AP_FOUND)
        return ("failed" if bad else "connecting", self.ssid, "", 0)

    def wifi_scan(self):
        self.sta.active(True)
        return [(s[0].decode(), s[3]) for s in sorted(self.sta.scan(), key=lambda x: -x[3])]

    def wifi_off(self):
        self.sta.active(False)

    def wifi_on(self):
        """connect to the first network saved in wifiman.conf"""
        try:
            with open(CONF) as f:
                ssid, pw = f.readline().strip().split(":", 1)
        except (OSError, ValueError):
            return
        self.ssid = ssid
        self.sta.active(True)
        self.sta.connect(ssid, pw)

    # ---- log: the stream's telemetry, events and buttons into a file.  On the SD card when it is mounted at /sd,
    # else in the ESP32's flash, where it stops at LOG_FLASH_MAX bytes (the flash is small and wears).
    def log_start(self):
        import os
        self.log_stop()
        self.log_bytes = self.log_n = 0
        try:
            base = "/sd/" if "sd" in os.listdir("/") else ""
            n = 1
            names = os.listdir(base or ".")
            while "fcl%03d.log" % n in names:
                n += 1
            self.log_name = "%sfcl%03d.log" % (base, n)
            self.log_max = 0 if base else LOG_FLASH_MAX
            self.logf = open(self.log_name, "w")
        except OSError as e:             # no room, card gone: the unit carries on without a log
            self.logf = None
            if self.usb:
                self.usb.out("$I,log not started: %s" % e)
            return None
        if self.usb:
            self.usb.log = self.log_write
        return self.log_name

    def log_write(self, line):
        if self.logf is None:
            return
        try:
            self.logf.write(line)
            self.logf.write("\n")
            self.log_bytes += len(line) + 1
            self.log_n += 1
            if self.log_n % 50 == 0:
                self.logf.flush()        # at most 5 s are lost if the power goes
        except OSError as e:             # flash or card full, card pulled out
            self.logf = None
            self.usb.log = None
            self.usb.hub.apps.log_on = False
            self.usb.out("$I,log stopped: %s" % e)
            return
        if self.log_max and self.log_bytes >= self.log_max:
            self.log_stop()
            if self.usb:
                self.usb.hub.apps.log_on = False
                self.usb.out("$I,log stopped: %d bytes in the flash is the limit; put an SD card in for long logs" % self.log_bytes)

    def log_stop(self):
        if self.usb:
            self.usb.log = None
        if self.logf is not None:
            try:
                self.logf.close()
            except OSError:
                pass
            self.logf = None
        return "%s %d bytes" % (self.log_name, self.log_bytes)

    # ---- restart, FPGA
    def reboot(self):
        import machine
        self.log_stop()
        machine.reset()

    def fpga(self, name, to_flash=False):
        """load a bitstream file into the FPGA over JTAG (esp32ecp5's ecp5.py).  The sensors stop until the bridge
        in the new bitstream is set up again: restart the ESP32 afterwards (command reboot)."""
        import ecp5
        ok = ecp5.flash(name) if to_flash else ecp5.prog(name)
        return ("written to the configuration memory" if to_flash else "loaded") if ok else "failed"

    # ---- audio
    def _i2s(self, direction, rate):
        if self.i2s and (self.dir != direction or self.rate != rate):
            self.i2s.deinit()
            self.i2s = None
        self.amp.value(1 if direction == "tx" else 0)
        if direction and not self.i2s:
            if direction == "rx":
                self.i2s = I2S(0, sck=Pin(I2S_BCLK), ws=Pin(I2S_WS), sd=Pin(I2S_MIC), mode=I2S.RX, bits=32,
                               format=I2S.MONO, rate=rate, ibuf=8 * len(self.raw))
            else:
                self.i2s = I2S(0, sck=Pin(I2S_BCLK), ws=Pin(I2S_WS), sd=Pin(I2S_SPK), mode=I2S.TX, bits=16,
                               format=I2S.MONO, rate=rate, ibuf=16000)
        self.dir, self.rate = direction, rate

    def mic(self, on, rate):
        self._i2s("rx" if on else None, rate)

    def spk(self, rate, pcm):
        if not rate:
            return self._i2s(None, self.rate)
        self._i2s("tx", rate)
        self.i2s.write(pcm)

    def tone(self, hz, ms):
        rate = 16000
        self._i2s("tx", rate)
        n = rate // hz if hz else rate // 440
        one = bytearray(2 * n)
        for i in range(n):
            v = int(9000 * math.sin(2 * math.pi * i / n))
            one[2 * i] = v & 0xFF
            one[2 * i + 1] = (v >> 8) & 0xFF
        for _ in range(max(1, rate * ms // 1000 // n)):
            self.i2s.write(one)

    def pump(self, bridge):
        """microphone: send what the I2S driver has collected"""
        if self.dir != "rx":
            return
        n = self.i2s.readinto(self.raw)
        if n:
            _s32_to_s16(self.raw, self.pcm, n // 4)
            bridge.audio(self.rate, memoryview(self.pcm)[:n // 2])


def run():
    out = sys.stdout
    plat = Plat()
    # the FPGA bridge on UART1: TX GPIO11 -> FPGA L1, RX GPIO12 <- FPGA L2
    uart = UART(1, baudrate=921600, tx=11, rx=12, rxbuf=4096)

    def rd():
        return uart.read() if uart.any() else b""

    br = fcl_bridge.Bridge(uart.write, rd, time.sleep_ms)
    hub = fcl_hubpy.Hub(br, store=CalStore("magcal.json"), cfg_store=CalStore("cal.json"), plat=plat)
    bridge = fcl_usb.Bridge(hub, lambda s: out.write(s + "\r\n"), plat)
    plat.usb = bridge
    try:                                     # your own pages: fcl_user.py with setup(apps), see doc/DEVELOPER_GUIDE.md
        import fcl_user
        fcl_user.setup(hub.apps)
    except ImportError:
        pass
    except Exception as e:
        out.write("$I,fcl_user.py stopped: %s\r\n" % e)
    web = None
    try:                                     # the web page (fcl_web.py); the unit works without it
        import fcl_web
        web = fcl_web.Web(bridge, hub, plat, 80)
    except Exception as e:
        out.write("$I,web page not started: %s\r\n" % e)
    hub.on_telemetry = bridge.on_telemetry
    hub.on_event = bridge.on_event
    hub.on_info = bridge.out
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    micropython.kbd_intr(-1)
    out.write("$I," + fcl_usb.VERSION + "\r\n")
    if br.ping() is None:
        out.write("$I,no answer from the FPGA bridge: is a bitstream with fcl_bridge loaded?\r\n")
    found = hub.start()
    out.write("$I,sensors found 0x%02X (1 IMU, 2 compass, 4 barometer, 8 ranger, 16 ADC)\r\n" % found)
    last_w = time.ticks_ms()
    try:
        while not bridge.exit:
            br.poll()
            hub.tick_ms(time.ticks_ms())
            while poll.poll(0):
                line = sys.stdin.readline()
                if not line:
                    break                # end of input (a PC test with a pipe); never on the USB port
                bridge.command(line)
            plat.pump(bridge)
            if web:
                web.poll()
            if time.ticks_diff(time.ticks_ms(), last_w) > 5000:
                last_w = time.ticks_ms()
                bridge.wifi_line()
            if not uart.any():
                time.sleep_ms(1)
    finally:
        micropython.kbd_intr(3)
        plat._i2s(None, plat.rate)
        plat.log_stop()
        if web:
            web.close()
