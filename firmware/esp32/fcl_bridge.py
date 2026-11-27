# Driver for the FPGA bridge (fpga/bridge/fcl_bridge.v): everything wired to the FPGA, reached over the UART.
# Runs on the ESP32 (MicroPython) and on a PC (simulator, tests).
#
#   br = Bridge(write, read)          write(bytes); read() -> bytes waiting, b"" if none
#   br.i2c_read(0x68, 0x75, 1)        -> bytes or None (no acknowledge / no answer)
#   br.i2c_write(0x68, 0x4E, b"\x0f") -> True / False
#   br.schedule(0, 50, 0x68, 0x1D, 14)        slot 0: read 14 bytes from register 0x1D every 5.0 ms
#   br.adc_schedule(2000, cfg)                all 8 ADC inputs every 200 ms
#   br.servo(0, 1500); br.out(mask, value); br.osd_text(addr, "text"); br.osd_dot(x, y, on, inside)
#   br.poll()                         handle what has arrived: calls on_sample / on_adc / on_inputs
from struct import pack, unpack

PING, I2C, SCHED, ADC, SERVO, OUT, OSD_TEXT, OSD_DOT, INPUTS = 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28
SAMPLE, ADC_DATA, INPUT_DATA = 0x30, 0x31, 0x32
OUT_LED0, OUT_LED1, OUT_TOF_XSHUT, OUT_SHUTDOWN = 1, 2, 4, 8


def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


try:                                     # the CRC is the one hot loop of the driver: native code on the ESP32
    import micropython

    @micropython.viper
    def crc16(data, crc: int) -> int:    # noqa: F811
        p = ptr8(data)
        n = int(len(data))
        i = 0
        while i < n:
            crc ^= p[i] << 8
            k = 0
            while k < 8:
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
                k += 1
            i += 1
        return crc
except (ImportError, NameError, SyntaxError):
    pass


def frame(typ, payload=b""):
    body = bytes((typ, len(payload))) + payload
    return b"\xa5\x5a" + body + pack("<H", crc16(body, 0xFFFF))


class Bridge:
    def __init__(self, write, read, sleep_ms=None):
        self._write, self._read, self._sleep = write, read, sleep_ms
        self.buf = bytearray()
        # time stamps are passed as the low 24 bits of the microsecond counter (wraps every 16.7 s): small
        # integers, so MicroPython never has to allocate a big number for them
        self.on_sample = None            # f(slot, t24, data, status)   data: memoryview, valid during the call
        self.on_adc = None               # f(t_us, codes)                codes: tuple of 8
        self.on_inputs = None            # f(t_us, buttons, ints)
        self.crc_errors = 0
        self.frames = 0
        self.timeouts = 0
        self._reply = None
        self._want = -1

    # ---- receive
    def poll(self):
        d = self._read()
        if d:
            self.buf.extend(d)
        buf = self.buf
        while True:
            n = len(buf)
            i = 0
            while i < n - 1 and not (buf[i] == 0xA5 and buf[i + 1] == 0x5A):
                i += 1
            if i:
                del buf[:i]
                n -= i
            if n < 4 or buf[0] != 0xA5:
                if n == 1 and buf[0] != 0xA5:
                    del buf[:]
                return
            ln = buf[3]
            if ln > 40:
                del buf[:2]
                continue
            if n < ln + 6:
                return
            mv = memoryview(buf)
            if crc16(mv[2:4 + ln], 0xFFFF) == (buf[4 + ln] | buf[5 + ln] << 8):
                self.frames += 1
                self._dispatch(buf[2], mv[4:4 + ln])
                mv = None
                del buf[:ln + 6]
            else:
                mv = None
                self.crc_errors += 1
                del buf[:2]

    def _dispatch(self, typ, p):
        if typ == SAMPLE:
            if self.on_sample:
                self.on_sample(p[0], p[1] | p[2] << 8 | p[3] << 16, p[5:len(p) - 1], p[len(p) - 1])
        elif typ == ADC_DATA:
            if self.on_adc:
                self.on_adc(p[0] | p[1] << 8 | p[2] << 16, unpack("<8H", p[4:20]))
        elif typ == INPUT_DATA and self._want != INPUTS:
            if self.on_inputs:
                self.on_inputs(p[0] | p[1] << 8 | p[2] << 16, p[4], p[5])
        elif typ == self._want or (typ == INPUT_DATA and self._want == INPUTS):
            self._reply = bytes(p)

    # ---- commands
    def request(self, typ, payload=b"", tries=200):
        """send one command and wait for its answer (other frames are handled while waiting); None on timeout"""
        self._want, self._reply = typ, None
        self._write(frame(typ, payload))
        for _ in range(tries):
            self.poll()
            if self._reply is not None:
                break
            if self._sleep:
                self._sleep(1)
        self._want = -1
        if self._reply is None:
            self.timeouts += 1
        return self._reply

    def ping(self):
        r = self.request(PING)
        return None if r is None else (r[0], unpack("<I", r[1:5])[0])

    def i2c(self, addr, reg, nreg, wdata, rlen):
        hdr = bytes((addr, nreg, len(wdata), rlen)) + (pack(">H", reg) if nreg == 2 else (bytes((reg,)) if nreg else b""))
        r = self.request(I2C, hdr + wdata)
        if r is None or r[-1]:
            return None
        return r[:-1]

    def i2c_read(self, addr, reg, n, reg16=False):
        return self.i2c(addr, reg, 2 if reg16 else 1, b"", n)

    def i2c_write(self, addr, reg, data, reg16=False):
        return self.i2c(addr, reg, 2 if reg16 else 1, data, 0) is not None

    def schedule(self, slot, period_100us, addr=0, reg=0, n=1, reg16=False):
        r = self.request(SCHED, pack("<BHBB", slot, period_100us, addr, 2 if reg16 else 1) + pack(">H", reg) + bytes((n,)))
        return r is not None and r[0] == 0

    def adc_schedule(self, period_100us, cfg):
        return self.request(ADC, pack("<HH", period_100us, cfg)) is not None

    def servo(self, ch, us):
        return self.request(SERVO, pack("<BH", ch, us)) is not None

    def out(self, mask, value):
        return self.request(OUT, bytes((mask, value))) is not None

    def osd_text(self, addr, text):
        return self.request(OSD_TEXT, pack("<H", addr) + text.encode()) is not None

    def osd_dot(self, x, y, on, inside):
        return self.request(OSD_DOT, pack("<HHB", x, y, (1 if on else 0) | (2 if inside else 0))) is not None

    def inputs(self):
        r = self.request(INPUTS)
        return None if r is None else (r[4], r[5])
