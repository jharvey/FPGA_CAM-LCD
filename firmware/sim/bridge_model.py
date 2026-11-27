#!/usr/bin/env python3
"""The FPGA bridge (fpga/bridge/fcl_bridge.v) as a Python model: same frames in, same frames out.

Used by the PC simulator in place of the FPGA, and by fpga/bridge/test_bridge.py, which runs the Verilog and this
model on the same commands and compares what they send.

    m = BridgeModel(devices)          devices: object with i2c(addr, nreg, reg, wdata, rlen) -> (bytes, status),
                                                adc_xfer(cfg14) -> code16
    m.feed(data)                      bytes from the ESP32 side
    out = m.advance(dt_us, buttons)   move time on; returns the bytes the bridge sent
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "esp32"))
import fcl_hub      # noqa: E402    (frame format and parser are shared with the old hub link)

PING, I2C, SCHED, ADC, SERVO, OUT, OSD_TEXT, OSD_DOT, INPUTS = 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28
SAMPLE, ADC_DATA, INPUT_DATA = 0x30, 0x31, 0x32


class BridgeModel:
    def __init__(self, dev):
        self.dev = dev
        self.t_us = 0
        self.sched = [None] * 4             # (period, addr, nreg, reg, rlen)
        self.s_cnt = [0] * 4
        self.adc = None                     # (period, cfg)
        self.a_cnt = 0
        self.servo = [0] * 6
        self.led, self.tof_xshut, self.shutdown = 0, 0, 0
        self.osd = [" "] * 450
        self.dot = (240, 240, 0, 0)
        self.btn = self.btn_sent = 0
        self.ints = 0
        self.hold_ms = 0
        self.force_off = False
        self.parser = fcl_hub.Parser()
        self.out = bytearray()
        self._sub = 0

    def _send(self, typ, payload):
        self.out += fcl_hub.frame(typ, bytes(payload))

    def _t(self):
        return struct.pack("<I", self.t_us & 0xFFFFFFFF)

    def _i2c(self, addr, nreg, reg, wdata, rlen):
        data, status = self.dev.i2c(addr, nreg, reg, wdata, rlen)
        if status:
            data = bytes(rlen)
        return bytes(data) + bytes((status,))

    def feed(self, data):
        for typ, p in self.parser.feed(data):
            if typ == PING:
                self._send(typ, b"\x01" + self._t())
            elif typ == I2C:
                addr, nreg, wlen, rlen = p[0] & 0x7F, p[1] & 3, p[2] & 31, p[3] & 31
                reg = (p[4] << 8 | p[5]) if nreg == 2 else (p[4] if nreg == 1 else 0)
                self._send(typ, self._i2c(addr, nreg, reg, p[4 + nreg:4 + nreg + wlen], rlen))
            elif typ == SCHED:
                if p[0] < 4:
                    per = p[1] | p[2] << 8
                    self.sched[p[0]] = (per, p[3] & 0x7F, p[4] & 3, p[5] << 8 | p[6], p[7] & 31) if per else None
                    self.s_cnt[p[0]] = per
                    self._send(typ, b"\x00")
                else:
                    self._send(typ, b"\x01")
            elif typ == ADC:
                per = p[0] | p[1] << 8
                self.adc = (per, p[2] | p[3] << 8) if per else None
                self.a_cnt = per
                self._send(typ, b"\x00")
            elif typ == SERVO:
                if p[0] < 6:
                    self.servo[p[0]] = (p[1] | p[2] << 8) & 0xFFF
                    self._send(typ, b"\x00")
                else:
                    self._send(typ, b"\x01")
            elif typ == OUT:
                m, v = p[0], p[1]
                if m & 1:
                    self.led = (self.led & 2) | (v & 1)
                if m & 2:
                    self.led = (self.led & 1) | (v & 2)
                if m & 4:
                    self.tof_xshut = v >> 2 & 1
                if m & 8:
                    self.shutdown = v >> 3 & 1
                self._send(typ, b"\x00")
            elif typ == OSD_TEXT:
                a = p[0] | (p[1] & 1) << 8
                for i, c in enumerate(p[2:]):
                    if a + i < 450:
                        self.osd[a + i] = chr(c & 0x7F)
                self._send(typ, b"\x00")
            elif typ == OSD_DOT:
                self.dot = (p[0] | (p[1] & 3) << 8, p[2] | (p[3] & 3) << 8, p[4] & 1, p[4] >> 1 & 1)
                self._send(typ, b"\x00")
            elif typ == INPUTS:
                self._send(INPUT_DATA, self._t() + bytes((self.btn, self.ints)))
            else:
                self._send(typ, b"\xff")

    def _adc_scan(self):
        cfg = self.adc[1]
        out = b""
        for k in range(10):
            c = (cfg & 0x3C7F) | ((k if k < 8 else 0) << 7)
            r = self.dev.adc_xfer(c)
            if k >= 2:
                out += struct.pack("<H", r)
        return out

    def advance(self, dt_us, buttons=None, ints=None):
        """buttons: bit 0 PWR, 1 B1, 2 B2 (already debounced: the 5 ms filter is not modelled)"""
        if ints is not None:
            self.ints = ints
        end = self.t_us + int(dt_us)
        while self.t_us < end:
            step = min(100 - self._sub, end - self.t_us)
            self.t_us += step
            self._sub += step
            if self._sub < 100:
                break
            self._sub = 0
            for i, s in enumerate(self.sched):                      # every 100 us
                if s:
                    self.s_cnt[i] -= 1
                    if self.s_cnt[i] <= 0:
                        self.s_cnt[i] = s[0]
                        self._send(SAMPLE, bytes((i,)) + self._t() + self._i2c(s[1], s[2], s[3], b"", s[4]))
            if self.adc:
                self.a_cnt -= 1
                if self.a_cnt <= 0:
                    self.a_cnt = self.adc[0]
                    self._send(ADC_DATA, self._t() + self._adc_scan())
            if buttons is not None and buttons != self.btn:
                self.btn = buttons
            if self.btn != self.btn_sent:
                self.btn_sent = self.btn
                self._send(INPUT_DATA, self._t() + bytes((self.btn, self.ints)))
            if self.t_us % 1000 < 100:
                self.hold_ms = self.hold_ms + 1 if self.btn & 1 else 0
                if self.hold_ms >= 8000:
                    self.force_off = True
        out = bytes(self.out)
        del self.out[:]
        return out

    def osd_rows(self):
        return ["".join(self.osd[r * 30:(r + 1) * 30]) for r in range(15)]


class TbDevices:
    """the register memories of fcl_bridge_tb.v"""

    def __init__(self):
        self.mem8 = [((i % 256) * 3 + (i // 256) * 17 + 1) & 0xFF for i in range(768)]
        self.mem16 = [((i // 256) * 5 + (i % 256) * 7 + 41) & 0xFF for i in range(65536)]
        self.ptr = 0
        self.hist = [0, 0]

    def i2c(self, addr, nreg, reg, wdata, rlen):
        dev = {0x68: 0, 0x1E: 1, 0x5C: 2, 0x29: 3}.get(addr)
        if dev is None:
            return b"", 1
        if nreg:
            self.ptr = reg if dev == 3 else reg & 0xFF
        for b in wdata:
            if dev == 3:
                self.mem16[self.ptr & 0xFFFF] = b
            else:
                self.mem8[dev * 256 + (self.ptr & 0xFF)] = b
            self.ptr += 1
        out = bytearray()
        for _ in range(rlen):
            out.append(self.mem16[self.ptr & 0xFFFF] if dev == 3 else self.mem8[dev * 256 + (self.ptr & 0xFF)])
            self.ptr += 1
        return bytes(out), 0

    def adc_xfer(self, cfg):
        old = self.hist[0]
        self.hist = [self.hist[1], cfg]
        return ((old >> 7) & 7) << 12 | 0x123
