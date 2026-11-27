# FCL sensor-hub link: reads telemetry and events from the FPGA soft CPU (firmware/common/link.h) and sends
# servo / mode commands.  UART on ESP32 GPIO11 (TX -> FPGA L1) / GPIO12 (RX <- FPGA L2), 921600 8N1.
#
#   import fcl_hub
#   fcl_hub.start()             # polls the UART every 20 ms from a timer
#   fcl_hub.last                # latest telemetry as a dict
#   fcl_hub.servo(0, 1500)      # servo 1 to 1500 us
#   fcl_hub.mode(2)
#   fcl_hub.overlay(0x3F)       # LCD overlay items (OV_* bits); fcl_hub.zero_alt(); fcl_hub.follow(False)
#   fcl_hub.log("/sd/fcl.csv")  # append telemetry to a CSV while recording (B2 toggles recording)
from struct import unpack, pack

MSG_TELEMETRY, MSG_EVENT, MSG_CMD_SERVO, MSG_CMD_MODE = 0x01, 0x02, 0x10, 0x11
MSG_CMD_OVERLAY, MSG_CMD_ZERO_ALT, MSG_CMD_FOLLOW = 0x12, 0x13, 0x14
TELEMETRY_LEN = 46
EVENTS = {1: "B1", 2: "B2", 3: "PWR_SHORT", 4: "PWR_OFF", 5: "CELL_LOW", 6: "CELL_CUTOFF"}
TF_RECORDING, TF_CELL_LOW, TF_CUTOFF, TF_TOF_VALID, TF_HOT, TF_DOT_INSIDE = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20
OV_DOT, OV_HEADING, OV_ATTITUDE, OV_BARO, OV_DIST, OV_BATT, OV_ALL = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x3F
SOC_NO_CELL = 255
FIELDS = ("t_ms", "heading", "pitch", "roll", "alt_m", "press_pa", "tof_mm", "cell1_mv", "cell2_mv", "cell3_mv",
          "vsys_mv", "temp1_c", "temp2_c", "temp3_c", "mode", "flags", "soc1", "soc2", "soc3", "buttons", "dot_x", "dot_y",
          "overlay", "sensors")

last = {}
events = []
frames = 0
crc_errors = 0
on_event = None          # set to a function(name) to react to events
on_telemetry = None      # set to a function(dict), called for every telemetry frame
_uart = None
_logpath = None


def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def frame(typ, payload):
    body = bytes((typ, len(payload))) + payload
    return b"\xa5\x5a" + body + pack("<H", crc16(body))


class Parser:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        """returns a list of (type, payload) for every complete frame with a good CRC"""
        global crc_errors
        self.buf.extend(data)
        out = []
        while True:
            i = self.buf.find(b"\xa5\x5a")
            if i < 0:
                self.buf = self.buf[-1:] if self.buf[-1:] == b"\xa5" else bytearray()
                return out
            if i:
                self.buf = self.buf[i:]
            if len(self.buf) < 4:
                return out
            n = self.buf[3]
            if n > 64:
                self.buf = self.buf[2:]
                continue
            if len(self.buf) < n + 6:
                return out
            body = bytes(self.buf[2:4 + n])
            if unpack("<H", self.buf[4 + n:6 + n])[0] == crc16(body):
                out.append((body[0], body[2:]))
                self.buf = self.buf[n + 6:]
            else:
                crc_errors += 1
                self.buf = self.buf[2:]


def decode_telemetry(p):
    v = unpack("<IhhhiIHHHHHhhhBBBBBBhhBB", p)
    return {"t_ms": v[0], "heading": v[1] / 100, "pitch": v[2] / 100, "roll": v[3] / 100, "alt_m": v[4] / 100,
            "press_pa": v[5], "tof_mm": v[6], "cell1_mv": v[7], "cell2_mv": v[8], "cell3_mv": v[9], "vsys_mv": v[10],
            "temp1_c": v[11] / 10, "temp2_c": v[12] / 10, "temp3_c": v[13] / 10, "mode": v[14], "flags": v[15],
            "soc1": v[16], "soc2": v[17], "soc3": v[18], "buttons": v[19], "dot_x": v[20], "dot_y": v[21],
            "overlay": v[22], "sensors": v[23]}


_parser = Parser()


def handle(data):
    global last, frames
    for typ, p in _parser.feed(data):
        if typ == MSG_TELEMETRY and len(p) == TELEMETRY_LEN:
            last = decode_telemetry(p)
            frames += 1
            if on_telemetry:
                on_telemetry(last)
            if _logpath and last["flags"] & TF_RECORDING:
                _write_log(last)
        elif typ == MSG_EVENT and len(p) == 1:
            name = EVENTS.get(p[0], str(p[0]))
            events.append(name)
            del events[:-20]
            if on_event:
                on_event(name)


def _write_log(t):
    try:
        with open(_logpath, "a") as f:
            f.write(",".join(str(t[k]) for k in FIELDS) + "\n")
    except OSError:
        pass


def log(path):
    """log telemetry to a CSV file while the hub reports recording (B2); None to stop"""
    global _logpath
    _logpath = path
    if path:
        try:
            open(path, "r").close()
        except OSError:
            with open(path, "w") as f:
                f.write(",".join(FIELDS) + "\n")


send_raw = None          # set to a function(bytes) to send somewhere other than the UART (simulator)


def _send(typ, payload):
    if send_raw:
        send_raw(frame(typ, payload))
    elif _uart:
        _uart.write(frame(typ, payload))


def servo(ch, us):
    _send(MSG_CMD_SERVO, pack("<BH", ch, us))


def mode(m):
    _send(MSG_CMD_MODE, bytes((m,)))


def overlay(mask):
    _send(MSG_CMD_OVERLAY, bytes((mask & OV_ALL,)))


def zero_alt():
    _send(MSG_CMD_ZERO_ALT, b"")


def follow(on):
    _send(MSG_CMD_FOLLOW, bytes((1 if on else 0,)))


def poll(_=None):
    if _uart and _uart.any():
        handle(_uart.read())


_timer = None
_period = 20


def start_timer():
    global _timer
    from machine import Timer
    _timer = Timer(0)
    _timer.init(period=_period, mode=Timer.PERIODIC, callback=poll)


def stop_timer():
    """fcl_usbdev.run() polls the UART from its own loop instead"""
    global _timer
    if _timer:
        _timer.deinit()
        _timer = None


def start(baud=921600, tx=11, rx=12, period_ms=20):
    global _uart, _period
    from machine import UART
    _uart = UART(1, baudrate=baud, tx=tx, rx=rx, rxbuf=2048)
    _period = period_ms
    start_timer()
