# FCL sensor-hub link: reads telemetry and events from the FPGA soft CPU (firmware/common/link.h) and sends
# servo / mode commands.  UART on ESP32 GPIO11 (TX -> FPGA L1) / GPIO12 (RX <- FPGA L2), 921600 8N1.
#
#   import fcl_hub
#   fcl_hub.start()             # polls the UART every 20 ms from a timer
#   fcl_hub.last                # latest telemetry as a dict
#   fcl_hub.servo(0, 1500)      # servo 1 to 1500 us
#   fcl_hub.mode(2)
#   fcl_hub.log("/sd/fcl.csv")  # append telemetry to a CSV while recording (B2 toggles recording)
from struct import unpack, pack

MSG_TELEMETRY, MSG_EVENT, MSG_CMD_SERVO, MSG_CMD_MODE = 0x01, 0x02, 0x10, 0x11
EVENTS = {1: "B1", 2: "B2", 3: "PWR_SHORT", 4: "PWR_OFF", 5: "CELL_LOW", 6: "CELL_CUTOFF"}
TF_RECORDING = 0x01
FIELDS = ("t_ms", "heading", "pitch", "roll", "alt_m", "press_pa", "tof_mm", "cell1_mv", "cell2_mv", "cell3_mv",
          "vsys_mv", "temp1_c", "temp2_c", "temp3_c", "mode", "flags")

last = {}
events = []
frames = 0
crc_errors = 0
on_event = None          # set to a function(name) to react to events
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
    v = unpack("<IhhhiIHHHHHhhhBB", p)
    return {"t_ms": v[0], "heading": v[1] / 100, "pitch": v[2] / 100, "roll": v[3] / 100, "alt_m": v[4] / 100,
            "press_pa": v[5], "tof_mm": v[6], "cell1_mv": v[7], "cell2_mv": v[8], "cell3_mv": v[9], "vsys_mv": v[10],
            "temp1_c": v[11] / 10, "temp2_c": v[12] / 10, "temp3_c": v[13] / 10, "mode": v[14], "flags": v[15]}


_parser = Parser()


def handle(data):
    global last, frames
    for typ, p in _parser.feed(data):
        if typ == MSG_TELEMETRY and len(p) == 36:
            last = decode_telemetry(p)
            frames += 1
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


def _send(typ, payload):
    if _uart:
        _uart.write(frame(typ, payload))


def servo(ch, us):
    _send(MSG_CMD_SERVO, pack("<BH", ch, us))


def mode(m):
    _send(MSG_CMD_MODE, bytes((m,)))


def poll(_=None):
    if _uart and _uart.any():
        handle(_uart.read())


def start(baud=921600, tx=11, rx=12, period_ms=20):
    global _uart
    from machine import UART, Timer
    _uart = UART(1, baudrate=baud, tx=tx, rx=rx, rxbuf=2048)
    Timer(0).init(period=period_ms, mode=Timer.PERIODIC, callback=poll)
