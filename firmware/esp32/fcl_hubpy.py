# The sensor hub in MicroPython, on the ESP32-S3.  It reaches the sensors, buttons, ADC, servos and the LCD
# overlay through the FPGA bridge (fcl_bridge.py) and produces the same telemetry dictionary the C hub sent
# (keys of fcl_hub.FIELDS), so fcl_usb.py, the dashboard and the overlay work unchanged.
#
# Speed plan: the FPGA reads the sensors on its own clock and time-stamps each sample, so jitter here does not
# reach the filter.  The 200 Hz path is integer-only viper code (fcl_fix.py); floats are used only at 20 Hz
# (angles, dot), 25 Hz (height) and 5 Hz (battery).
#
#   hub = Hub(bridge, on_telemetry, on_event); hub.start(); then call bridge.poll() often and hub.tick_ms(now)
import math
from array import array
import fcl_fix
import fcl_calc
import fcl_bridge as fb
import fcl_magcal
import fcl_cfg
import fcl_app

A_IMU, A_MAG, A_BARO, A_TOF = 0x68, 0x1E, 0x5C, 0x29
ADC_CFG = 1 << 13 | 7 << 10 | 1 << 6 | 1 << 3 | 1          # AD7689: unipolar to GND, internal 2.5 V reference  CHECK
DIV_CELL = (47.0 + 56.0) / 56.0
DIV_VSYS = (100.0 + 68.0) / 68.0
NTC_R25, NTC_BETA, NTC_PULLUP, VREF = 10000.0, 3435.0, 10000.0, 2.5
CELL_LOW_MV, CELL_CUTOFF_MV, CELL_HOT_C = 3400, 3200, 55.0
EVENTS = {1: "B1", 2: "B2", 3: "PWR_SHORT", 4: "PWR_OFF", 5: "CELL_LOW", 6: "CELL_CUTOFF", 7: "B1_LONG"}
OUT_KEY_VIEW, OUT_KEY_INC, OUT_KEY_DEC, OUT_OWN_KEYS = 0x10, 0x20, 0x40, 0x80      # full FPGA design: video keys
FIELDS = ("t_ms", "heading", "pitch", "roll", "alt_m", "press_pa", "tof_mm", "cell1_mv", "cell2_mv", "cell3_mv",
          "vsys_mv", "temp1_c", "temp2_c", "temp3_c", "mode", "flags", "soc1", "soc2", "soc3", "buttons", "dot_x", "dot_y",
          "overlay", "sensors")


class Hub:
    def __init__(self, bridge, on_telemetry=None, on_event=None, store=None, cfg_store=None, plat=None):
        self.br = bridge
        self.on_telemetry, self.on_event = on_telemetry, on_event
        self.on_info = None              # f(line): extra lines for the USB stream ($M compass calibration)
        self.st = fcl_fix.new_state()
        self.cal = fcl_magcal.MagCal(store)
        self._cal_apply()
        self.n_mag = 0
        self._cal_t = 0
        self.last = {}
        self.sensors = 0
        self.t24 = -1                    # time stamp of the previous IMU sample (24 bits of microseconds)
        self.t_us = 0                    # running time from the IMU time stamps
        self.n_imu = 0
        self.p_pa = 101325.0
        self.p0 = 0.0
        self.p0_n = 0
        self.alt = 0.0
        self.alt_zero = 0.0
        self.zero_req = False
        self.tof_mm, self.tof_valid = 0, False
        self.cell_mv = [0, 0, 0]
        self.temp_c = [0.0, 0.0, 0.0]
        self.soc = [-1.0, -1.0, -1.0]
        self.vsys_mv = 0
        self.flags = 0
        self.mode_n, self.overlay_mask = 0, 0x3F
        self.tele_due = False
        self.recording = False
        self.follow_on = True
        self.buttons = 0
        self.pwr_t = None
        self.power_off = False
        self.now_ms = 0
        self.osd = [" " * 30] * 15
        self.dot = None
        self.hud_mask = 0                # graphics the user switched on for every page (fcl_app.RETICLE ...)
        self.hud = (0, 0, 0, 0, 0)       # as sent to the FPGA: flags, a, b, c, tape
        self.servo_us = -1
        self.leds = -1
        self._tof_due = 0
        self.cfg = fcl_cfg.Cfg(cfg_store)        # calibration values of this unit (cal.json)
        self.keys = []                   # keys waiting for tick_ms: "B1", "B2", "B1L"
        self.b1_t, self.b1_long = None, False
        self.edges = False               # the LCD shows the edge view (the FPGA starts with the camera view)
        self._vk, self._vk_on, self._vk_t = [], 0, 0     # video keys: waiting, held now, time of the last change
        self.pan_target, self.pan_us = None, -1
        self.apps = fcl_app.Apps(self, plat)     # pages and menu (fcl_app.py)
        bridge.on_sample, bridge.on_adc, bridge.on_inputs = self._sample, self._adc, self._inputs

    # ---- sensor set-up (the register values of firmware/common/sensors.c)
    def start(self):
        br = self.br
        w, r = br.i2c_write, br.i2c_read
        ok = 0
        # ranger on, power held, LED0 on; video keys released and B1 / B2 taken over from the FPGA's video logic
        br.out(fb.OUT_TOF_XSHUT | fb.OUT_SHUTDOWN | fb.OUT_LED0 | 0xF0, fb.OUT_TOF_XSHUT | fb.OUT_LED0 | OUT_OWN_KEYS)
        w(A_IMU, 0x76, b"\x00")
        if r(A_IMU, 0x75, 1) == b"\x47":
            w(A_IMU, 0x11, b"\x01")                         # soft reset
            w(A_IMU, 0x4F, bytes((2 << 5 | 7,)))            # gyro +-500 deg/s, 200 Hz
            w(A_IMU, 0x50, bytes((2 << 5 | 7,)))            # accel +-4 g, 200 Hz
            w(A_IMU, 0x4E, b"\x0f")                         # gyro + accel, low noise
            ok |= 1
        if r(A_MAG, 0x4F, 1) == b"\x40":
            w(A_MAG, 0x60, bytes((0x80 | 3 << 2,)))         # temperature compensation, 100 Hz, continuous
            w(A_MAG, 0x61, b"\x02")
            w(A_MAG, 0x62, b"\x10")
            ok |= 2
        if r(A_BARO, 0x0F, 1) == b"\xb4":
            w(A_BARO, 0x11, b"\x08")
            w(A_BARO, 0x10, bytes((4 << 3,)))               # 25 Hz  CHECK
            ok |= 4
        if r(A_TOF, 0x010F, 1, True) == b"\xea":
            w(A_TOF, 0x0087, b"\x40", True)                 # start ranging (ST's configuration block: TODO)
            ok |= 8
        if br.adc_schedule(2000, ADC_CFG):                  # every 200 ms
            ok |= 16
        self.sensors = ok
        if ok & 1:
            br.schedule(0, 50, A_IMU, 0x1D, 14)             # every 5 ms
        if ok & 2:
            br.schedule(1, 100, A_MAG, 0x68, 6)             # every 10 ms
        if ok & 4:
            br.schedule(2, 400, A_BARO, 0x28, 5)            # every 40 ms
        b = br.inputs()
        if b:
            self.buttons = b[0]
        return ok

    # ---- commands (the interface fcl_usb.Bridge expects)
    def servo(self, ch, us):
        if ch == 0:
            self.follow_on = False
            self.servo_us = us
        if ch == 1:
            self.pan_target = None
            self.pan_us = us
        self.br.servo(ch, us)

    @property
    def n_modes(self):
        return len(self.apps.pages)

    def mode(self, m):
        self.apps.select(m)

    def view(self, edges):
        """LCD picture: camera (False) or edges (True).  The FPGA's video logic only has a toggle key, so this
        keeps count; `view` again after an FPGA reload if the two disagree."""
        if bool(edges) != self.edges:
            self.edges = bool(edges)
            self._vk.append(OUT_KEY_VIEW)

    def threshold(self, step):
        """edge threshold one step up (+1) or down (-1)"""
        self._vk.append(OUT_KEY_INC if step > 0 else OUT_KEY_DEC)

    def pan(self, heading):
        """servo 2 holds this compass heading (degrees); None = stop"""
        if heading is None:
            self.pan_target, self.pan_us = None, 0
            self.br.servo(1, 0)
        else:
            self.pan_target = heading % 360.0

    def key(self, name):
        """press a key from outside (USB, web page): B1, B2 or B1L"""
        self.keys.append(name)

    def overlay(self, mask):
        self.overlay_mask = mask & 0x3F

    def graphics(self, mask):
        """reticle 1, horizon 2, compass tape 4 on every page; a page adds its own (App.hud)"""
        self.hud_mask = mask & 7

    def zero_alt(self):
        self.zero_req = True

    def follow(self, on):
        self.follow_on = bool(on)
        if not on:
            self.servo_us = 0
            self.br.servo(0, 0)

    # ---- compass calibration
    def _cal_apply(self):
        for i in range(3):
            self.st[16 + i] = int(round(self.cal.off[i]))
            for j in range(3):
                w = max(-1.9, min(1.9, self.cal.soft[i][j]))
                self.st[20 + 3 * i + j] = int(round(w * 16384))

    def _cal_report(self):
        if self.on_info:
            self.on_info("$M," + self.cal.status())

    def magcal(self, a):
        """the USB command: magcal [start | stop | auto on|off | reset]; returns the reply text"""
        cal = self.cal
        c = a[0] if a else "status"
        if c == "start":
            cal.manual_start()
            r = "magcal started: point the unit up, down, north, south, east and west"
        elif c == "stop":
            if not cal.manual:
                r = "magcal: no calibration running (" + cal.state + ")"
            else:
                r = "magcal stored" if cal.manual_stop() else "magcal stopped: not enough directions, nothing changed"
        elif c == "auto":
            cal.auto = a[1] == "on"
            cal.save()
            r = "magcal auto " + ("on" if cal.auto else "off")
        elif c == "reset":
            cal.reset()
            r = "magcal reset"
        elif c == "status":
            r = "magcal"
        else:
            raise ValueError
        self._cal_apply()
        self._cal_report()
        return r

    def _event(self, code):
        if self.on_event:
            self.on_event(EVENTS[code])

    # ---- data from the bridge
    def _sample(self, slot, t24, data, status):
        if status:
            return
        if slot == 0:
            t24 &= 0xFFFFFF
            dt = 5000 if self.t24 < 0 else (t24 - self.t24) & 0xFFFFFF
            self.t24 = t24
            self.t_us += dt
            fcl_fix.imu_step(self.st, data, dt)
            self.n_imu += 1
            if self.n_imu % 10 == 0:
                self.tele_due = True                        # done from tick_ms: it sends commands, which must not
                                                            # happen while the bridge is still handing out frames
        elif slot == 1:
            fcl_fix.mag_step(self.st, data)
            self.n_mag += 1
            if self.n_mag % 10 == 0:                        # calibration looks at 10 readings a second
                x, y, z = data[0] | data[1] << 8, data[2] | data[3] << 8, data[4] | data[5] << 8
                if self.cal.add(x - 65536 if x > 32767 else x, y - 65536 if y > 32767 else y, z - 65536 if z > 32767 else z):
                    self._cal_apply()
                    self._cal_report()
        elif slot == 2:
            raw = data[0] | data[1] << 8 | data[2] << 16
            if raw & 0x800000:
                raw -= 0x1000000
            p = raw / 4096.0                                # hPa
            self.p_pa = p * 100.0
            if self.p0_n < 16:                              # reference: mean of the first 16 readings
                self.p0 = (self.p0 * self.p0_n + p) / (self.p0_n + 1)
                self.p0_n += 1
            alt = 44330.0 * (1.0 - math.pow(p / self.p0, 1.0 / 5.255))
            self.alt += 0.2 * (alt - self.alt)
            if self.zero_req:
                self.alt_zero, self.zero_req = self.alt, False

    def _adc(self, t24, c):
        old = self.flags
        fl = 0
        for i in range(3):
            mv = int(c[i] * VREF / 65536.0 * DIV_CELL * 1000.0 * self.cfg.v[("cell1", "cell2", "cell3")[i]] + 0.5)
            self.cell_mv[i] = mv
            v = c[(3, 6, 7)[i]] * VREF / 65536.0
            if 0.001 < v < VREF - 0.001:
                rr = NTC_PULLUP * v / (VREF - v)
                tc = 1.0 / (1.0 / 298.15 + math.log(rr / NTC_R25) / NTC_BETA) - 273.15 + self.cfg.v[("temp1", "temp2", "temp3")[i]]
            else:
                tc = -99.0
            self.temp_c[i] = tc
            if 2500 < mv < CELL_LOW_MV:
                fl |= fcl_calc.TF_CELL_LOW
            if 2500 < mv < CELL_CUTOFF_MV:
                fl |= fcl_calc.TF_CUTOFF
            if tc > CELL_HOT_C:
                fl |= fcl_calc.TF_HOT
            soc = fcl_calc.soc_from_mv(mv)
            if soc == fcl_calc.SOC_NO_CELL:
                self.soc[i] = -1.0
            else:
                self.soc[i] = soc if self.soc[i] < 0 else self.soc[i] + 0.1 * (soc - self.soc[i])
        self.vsys_mv = int(c[5] * VREF / 65536.0 * DIV_VSYS * 1000.0 + 0.5)
        self.flags = fl
        if fl & fcl_calc.TF_CELL_LOW and not old & fcl_calc.TF_CELL_LOW:
            self._event(5)
        if fl & fcl_calc.TF_CUTOFF and not old & fcl_calc.TF_CUTOFF:
            self._event(6)

    def _inputs(self, t24, buttons, ints):
        ch = buttons ^ self.buttons
        self.buttons = buttons
        # keys are only noted here; tick_ms acts on them (acting may send commands, which must not happen while
        # the bridge is still handing out frames).  B1 acts on release, so that holding it can mean something else.
        if ch & 2:
            if buttons & 2:
                self.b1_t, self.b1_long = self.now_ms, False
            else:
                if self.b1_t is not None and not self.b1_long:
                    self.keys.append("B1")
                self.b1_t = None
        if ch & 4 and buttons & 4:
            self.keys.append("B2")
        if ch & 1:
            if buttons & 1:
                self.pwr_t = self.now_ms
            else:
                self.pwr_t = None
                if not self.power_off:
                    self._event(3)

    def _key(self, k):
        if self.power_off:
            return
        self._event({"B1": 1, "B2": 2, "B1L": 7}[k])
        if self.apps.key(k):
            return
        if k == "B1":
            self.mode_n = (self.mode_n + 1) % 4
        elif k == "B2":
            self.recording = not self.recording

    def tick_ms(self, now_ms):
        """call every few milliseconds from the main loop, with a millisecond clock"""
        self.now_ms = now_ms
        if self.b1_t is not None and not self.b1_long and now_ms - self.b1_t >= fcl_app.LONG_MS:
            self.b1_long = True
            self.keys.append("B1L")
        while self.keys:
            self._key(self.keys.pop(0))
        if self._vk_on:                                             # a video key is held for 100 ms, then 100 ms pause
            if now_ms - self._vk_t >= 100:
                self.br.out(self._vk_on, 0)
                self._vk_on, self._vk_t = 0, now_ms
        elif self._vk and now_ms - self._vk_t >= 100:
            self._vk_on, self._vk_t = self._vk.pop(0), now_ms
            self.br.out(self._vk_on, self._vk_on)
        if self.tele_due:
            self.tele_due = False
            self._telemetry()
        if self.cal.manual and now_ms - self._cal_t >= 1000:     # progress once a second while calibrating by hand
            self._cal_t = now_ms
            self._cal_report()
        if self.pwr_t is not None and not self.power_off and now_ms - self.pwr_t >= 2000:
            self.power_off = True
            self._event(4)
            self.br.servo(0, 0)
            self.br.out(fb.OUT_SHUTDOWN | fb.OUT_LED0 | fb.OUT_LED1, fb.OUT_SHUTDOWN)
        if self.sensors & 8 and not self.power_off and now_ms - self._tof_due >= 0:     # ranger, 20 times a second
            self._tof_due = now_ms + 50
            br = self.br
            s = br.i2c_read(A_TOF, 0x0031, 1, True)
            if s is not None and not s[0] & 1:
                d = br.i2c_read(A_TOF, 0x0096, 2, True)
                if d is not None:
                    raw = d[0] << 8 | d[1]
                    self.tof_valid = 0 < raw < 4000
                    self.tof_mm = max(0, raw + int(self.cfg.v["dist0"]))
                br.i2c_write(A_TOF, 0x0086, b"\x01", True)

    # ---- 20 times a second: angles, dot, overlay, servo, telemetry
    def angles(self):
        st = self.st
        ux, uy, uz = st[0], st[1], st[2]
        n = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / n, uy / n, uz / n
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, ux))))
        roll = math.degrees(math.atan2(uy, uz))
        mx, my, mz = st[3], st[4], st[5]
        d = mx * ux + my * uy + mz * uz
        hx, hy, hz = mx - d * ux, my - d * uy, mz - d * uz          # the field's horizontal part points north
        heading = math.degrees(math.atan2(-(uy * hz - uz * hy), hx)) % 360.0
        return heading, pitch, roll

    def _telemetry(self):
        if self.power_off:
            return
        br = self.br
        cfg = self.cfg.v
        hd, pt, rl = self.angles()
        hd, pt, rl = (hd + cfg["head0"]) % 360.0, pt - cfg["pitch0"], rl - cfg["roll0"]     # small trims: plain subtraction
        dx, dy, inside = fcl_calc.down_dot(pt, rl, cfg["hfov"])
        fl = self.flags | (fcl_calc.TF_RECORDING if self.recording else 0) | (fcl_calc.TF_TOF_VALID if self.tof_valid else 0) \
            | (fcl_calc.TF_DOT_INSIDE if inside else 0) | (fcl_calc.TF_EDGES if self.edges else 0) \
            | (fcl_calc.TF_MENU if self.apps.menu_open else 0) | (fcl_calc.TF_LOG if self.apps.log_on else 0)
        soc = [fcl_calc.SOC_NO_CELL if s < 0 else int(s + 0.5) for s in self.soc]
        t = {"t_ms": self.t_us // 1000, "heading": hd, "pitch": pt, "roll": rl, "alt_m": self.alt - self.alt_zero,
             "press_pa": int(self.p_pa + 0.5), "tof_mm": self.tof_mm,
             "cell1_mv": self.cell_mv[0], "cell2_mv": self.cell_mv[1], "cell3_mv": self.cell_mv[2], "vsys_mv": self.vsys_mv,
             "temp1_c": self.temp_c[0], "temp2_c": self.temp_c[1], "temp3_c": self.temp_c[2],
             "mode": self.mode_n, "flags": fl, "soc1": soc[0], "soc2": soc[1], "soc3": soc[2], "buttons": self.buttons,
             "dot_x": dx, "dot_y": dy, "overlay": self.overlay_mask, "sensors": self.sensors}
        self.last = t
        # overlay: send only the part of a row that changed
        grid = self.apps.compose(t)                                 # standard overlay + the page or the menu
        for r in range(15):
            a, b = self.osd[r], grid[r]
            if a != b:
                i, j = 0, 30
                while a[i] == b[i]:
                    i += 1
                while a[j - 1] == b[j - 1]:
                    j -= 1
                br.osd_text(r * 30 + i, b[i:j])
        self.osd = grid
        if self.on_info:
            self.apps.report(self.now_ms, self.on_info)
        dot = (240 + dx, 240 + dy, bool(self.overlay_mask & 1) and not self.apps.menu_open, inside)
        if dot != self.dot:
            self.dot = dot
            br.osd_dot(*dot)
        f = self.apps.hud_flags()
        hud = (0, 0, 0, 0, 0)
        if f:
            ok, a, b, c, tape = fcl_calc.hud_values(hd, pt, rl, cfg["hfov"])
            if not (f & 2 and ok):                                  # no horizon wanted, or it has left the picture
                f, a, b, c = f & ~2, 0, 0, 0
            hud = (f, a, b, c, tape if f & 4 else 0)
        if hud != self.hud:
            self.hud = hud
            br.osd_hud(*hud)
        if self.follow_on:                                          # servo 1 holds the camera level
            us = int(min(2000, max(1000, 1500 + cfg["tilt_us"] * pt)))
            if us != self.servo_us:
                self.servo_us = us
                br.servo(0, us)
        if self.pan_target is not None:                             # servo 2 holds a compass heading
            e = (self.pan_target - hd + 180.0) % 360.0 - 180.0
            us = int(min(2000, max(1000, 1500 + cfg["pan_us"] * e)))
            if us != self.pan_us:
                self.pan_us = us
                br.servo(1, us)
        leds = 1 | (2 if ((self.n_imu // 50) & 1 if fl & fcl_calc.TF_CELL_LOW else self.recording) else 0)
        if leds != self.leds:
            self.leds = leds
            br.out(fb.OUT_LED0 | fb.OUT_LED1, leds)
        if self.on_telemetry:
            self.on_telemetry(t)
