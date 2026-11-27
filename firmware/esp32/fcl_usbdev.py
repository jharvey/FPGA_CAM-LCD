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
from machine import Pin, I2S
import network
import fcl_hub
import fcl_usb

I2S_BCLK, I2S_WS, I2S_SPK, I2S_MIC, AMP_SD = 35, 36, 37, 38, 47
CONF = "wifiman.conf"


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
    bridge = fcl_usb.Bridge(fcl_hub, lambda s: out.write(s + "\r\n"), plat)
    fcl_hub.on_telemetry = bridge.on_telemetry
    fcl_hub.on_event = bridge.on_event
    fcl_hub.stop_timer()                    # this loop polls the hub UART itself
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    micropython.kbd_intr(-1)
    out.write("$I," + fcl_usb.VERSION + "\r\n")
    last_w = time.ticks_ms()
    try:
        while not bridge.exit:
            fcl_hub.poll()
            while poll.poll(0):
                line = sys.stdin.readline()
                if line:
                    bridge.command(line)
            plat.pump(bridge)
            if time.ticks_diff(time.ticks_ms(), last_w) > 5000:
                last_w = time.ticks_ms()
                bridge.wifi_line()
            time.sleep_ms(5)
    finally:
        micropython.kbd_intr(3)
        plat._i2s(None, plat.rate)
        fcl_hub.start_timer()
