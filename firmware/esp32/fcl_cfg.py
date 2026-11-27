# Calibration values of one unit: what differs from board to board and from the drawings to the real thing.
# Kept in cal.json on the ESP32; changed with the USB command `cal set <name> <value>` or by the guided
# calibration on a PC (firmware/tools/fcl_calibrate.py).  Runs on the ESP32 (MicroPython) and on a PC.
#
#   name        default   range          meaning
#   hfov        40        20..90         camera angle across the 480 px of the screen, degrees (for the down dot)
#   pitch0      0         -15..15        pitch read when the unit lies level (subtracted)
#   roll0       0         -15..15        roll read when the unit lies level (subtracted)
#   head0       0         -180..180      added to the heading (mounting error, magnetic declination)
#   cell1..3    1         0.9..1.1       gain on each cell voltage (divider and reference tolerance)
#   temp1..3    0         -15..15        added to each cell temperature, degrees C
#   dist0       0         -200..200      added to the measured distance, mm
#   pan_us      10        -30..30        pan servo: microseconds per degree of heading error (sign = direction)
#   tilt_us     -10       -30..30        tilt servo: microseconds per degree of pitch
DEFAULTS = (("hfov", 40.0, 20.0, 90.0), ("pitch0", 0.0, -15.0, 15.0), ("roll0", 0.0, -15.0, 15.0),
            ("head0", 0.0, -180.0, 180.0), ("cell1", 1.0, 0.9, 1.1), ("cell2", 1.0, 0.9, 1.1), ("cell3", 1.0, 0.9, 1.1),
            ("temp1", 0.0, -15.0, 15.0), ("temp2", 0.0, -15.0, 15.0), ("temp3", 0.0, -15.0, 15.0),
            ("dist0", 0.0, -200.0, 200.0), ("pan_us", 10.0, -30.0, 30.0), ("tilt_us", -10.0, -30.0, 30.0))
NAMES = tuple(d[0] for d in DEFAULTS)


class Cfg:
    def __init__(self, store=None):
        self.store = store                  # object with load() -> dict or None, save(dict)
        self.v = dict((d[0], d[1]) for d in DEFAULTS)
        if store:
            try:
                d = store.load()
            except Exception:
                d = None
            if d:
                for k in d:
                    try:
                        self.set(k, d[k], save=False)
                    except (ValueError, TypeError):
                        pass                # a value from an older or damaged file: keep the default

    def get(self, name):
        return self.v[name]

    def set(self, name, value, save=True):
        """raises ValueError for an unknown name or a value outside its range"""
        for n, _, lo, hi in DEFAULTS:
            if n == name:
                value = float(value)
                if not lo <= value <= hi:
                    raise ValueError("%s must be %g..%g" % (name, lo, hi))
                self.v[name] = value
                if save:
                    self.save()
                return
        raise ValueError("no calibration value named " + str(name))

    def reset(self):
        self.v = dict((d[0], d[1]) for d in DEFAULTS)
        self.save()

    def save(self):
        if self.store:
            try:
                self.store.save(dict(self.v))
            except Exception:
                pass

    def line(self):
        """the fields of a $C line"""
        return ",".join("%s=%g" % (n, self.v[n]) for n in NAMES)
