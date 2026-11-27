# An example of a page of your own.  Copy this file to the unit as fcl_user.py: fcl_usbdev.py calls setup(apps)
# at start, and the page appears after the built-in ones (B1 steps to it).
# Try it on a PC first:   python firmware/sim/fcl_sim.py --user fcl_user_example --web 8080
#
# CLIMB: B2 starts and stops a climb.  Shows the height gained and the rate, from the barometer.
import fcl_app


class Climb(fcl_app.App):
    name = "CLIMB"

    def __init__(self):
        self.t0 = None           # start time in ms while running
        self.h0 = 0.0
        self.done = None         # (metres, seconds) of the last climb

    def start(self, unit):       # the page has just been selected
        self.t0 = self.done = None

    def button(self, unit):      # B2
        if self.t0 is None:
            self.t0, self.h0, self.done = unit.time_ms(), unit.height(), None
            unit.beep()
        else:
            self.done = (unit.height() - self.h0, (unit.time_ms() - self.t0) / 1000.0)
            self.t0 = None
            unit.say("climb %+.1f m in %.0f s" % self.done)       # one $I line on the USB stream and in the log
            unit.beep(1320)

    def draw(self, unit, put):   # 20 times a second; put(row, text) writes a centred line
        put(fcl_app.T_ROW, self.name)
        if self.t0 is not None:
            h, s = unit.height() - self.h0, (unit.time_ms() - self.t0) / 1000.0
        elif self.done:
            h, s = self.done
        else:
            put(fcl_app.V_ROW, "B2 = START")
            return
        put(fcl_app.V_ROW, "%+.1fm  %d:%02d" % (h, int(s) // 60, int(s) % 60))
        if s >= 2:
            put(fcl_app.V2_ROW, "%+.1f m/min" % (h / s * 60.0))
        put(fcl_app.H_ROW, "B2 = STOP" if self.t0 is not None else "B2 = AGAIN")


def setup(apps):
    apps.add(Climb())
