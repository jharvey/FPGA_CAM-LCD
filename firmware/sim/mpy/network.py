# MicroPython Unix port only: a stand-in for the ESP32's network module, so that fcl_usbdev.py runs on a PC
STA_IF = 0
STAT_WRONG_PASSWORD, STAT_NO_AP_FOUND, STAT_CONNECTING, STAT_GOT_IP = 202, 201, 1001, 1010


class WLAN:
    def __init__(self, iface):
        self.on = False
        self.ssid = ""

    def active(self, v=None):
        if v is None:
            return self.on
        self.on = v

    def connect(self, ssid, pw):
        self.ssid = ssid

    def disconnect(self):
        self.ssid = ""

    def isconnected(self):
        return self.on and bool(self.ssid)

    def status(self, what=None):
        return -50 if what == "rssi" else (STAT_GOT_IP if self.isconnected() else STAT_CONNECTING)

    def config(self, what):
        return self.ssid

    def ifconfig(self):
        return ("192.168.4.20", "255.255.255.0", "192.168.4.1", "192.168.4.1")

    def scan(self):
        return [(b"HomeNet", b"", 6, -48, 3, False), (b"Workshop", b"", 1, -71, 3, False)]
