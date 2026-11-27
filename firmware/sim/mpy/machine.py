# MicroPython Unix port only: stand-ins for the ESP32's machine.Pin, I2S and UART, so that fcl_usbdev.py (the
# unit's real main loop) runs on a PC.  The UART leads to the Python model of the FPGA bridge with the simulated
# sensors behind it, in real time.
import time
import fcl_sim
import bridge_model


class Pin:
    OUT, IN = 1, 0

    def __init__(self, n, mode=0, value=0):
        self.n, self.v = n, value

    def value(self, v=None):
        if v is None:
            return self.v
        self.v = v


class I2S:
    RX, TX, MONO = 0, 1, 0
    made = []           # (mode, rate) of every instance, for the test
    written = 0

    def __init__(self, n, sck=None, ws=None, sd=None, mode=0, bits=16, format=0, rate=16000, ibuf=0):
        self.mode = mode
        I2S.made.append((mode, rate))

    def write(self, buf):
        I2S.written += len(buf)
        return len(buf)

    def readinto(self, buf):
        return 0

    def deinit(self):
        pass


class UART:
    last = None

    def __init__(self, n, baudrate=115200, tx=None, rx=None, rxbuf=0):
        self.scenario = fcl_sim.Scenario()
        self.scenario.demo_buttons = False
        self.world = fcl_sim.SensorWorld(self.scenario)
        self.model = bridge_model.BridgeModel(self.world)
        self.buf = bytearray()
        self.t0 = self.t_last = time.ticks_us()
        self.baud = baudrate
        UART.last = self

    def _run(self):
        now = time.ticks_us()
        dt = time.ticks_diff(now, self.t_last)
        if dt >= 1000:
            self.t_last = now
            self.world.now(time.ticks_diff(now, self.t0) / 1e6)
            self.buf += self.model.advance(dt, buttons=self.world.btn)
        if self.model.out:
            self.buf += bytes(self.model.out)
            self.model.out[:] = b""

    def write(self, data):
        self.model.feed(data)
        return len(data)

    def any(self):
        self._run()
        return len(self.buf)

    def read(self, n=-1):
        self._run()
        d = bytes(self.buf)
        self.buf[:] = b""
        return d or None
