"""Lesson 6: a page of your own.  This one is a parking sensor: it beeps faster the closer something is.

Run it by itself to test it in the simulator:
    python doc/lessons/examples/lesson6_page.py
See it on the simulated unit's phone page (press "B1 page" until PARKING shows):
    python firmware/sim/fcl_sim.py --web 8080 --user doc/lessons/examples/lesson6_page.py
On a real unit: copy this file to the unit as fcl_user.py (firmware/tools/fcl_update.py --user lesson6_page.py).
"""
try:
    import fcl_app                           # on the unit, and when the simulator loads this file
except ImportError:                          # run by itself on a PC: the unit's software is elsewhere in this repository
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "firmware", "esp32"))
    import fcl_app


class Parking(fcl_app.App):
    name = "PARKING"
    hud = fcl_app.RETICLE                    # the cross at the centre: what the ranger looks at

    def __init__(self):
        self.next_beep = 0                   # the unit's clock (ms) at which the next beep is due
        self.quiet = False

    def button(self, unit):                  # B2: sound on / off
        self.quiet = not self.quiet

    def draw(self, unit, put):               # called 20 times a second
        put(fcl_app.T_ROW, self.name)
        d = unit.distance()
        if d is None:
            put(fcl_app.V_ROW, "CLEAR")
            return
        bar = int(min(d, 2.0) / 2.0 * 16)    # a bar that shrinks as the thing comes closer
        put(fcl_app.V_ROW, "%.2fm %s" % (d, "#" * bar))
        put(fcl_app.H_ROW, "B2 = SOUND " + ("ON" if self.quiet else "OFF"))
        if d < 2.0 and not self.quiet and unit.time_ms() >= self.next_beep:
            unit.beep(1500, 40)
            self.next_beep = unit.time_ms() + int(100 + 450 * d)     # 0.1 s apart when touching, 1 s apart at 2 m


def setup(apps):
    apps.add(Parking())


if __name__ == "__main__":
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "firmware", "tools"))
    sys.path.insert(0, HERE)
    import fcl
    with fcl.connect("sim", realtime=False, user="lesson6_page") as u:
        plat = u.src.sim.plat                # the simulator's stand-in for the speaker: it lists the beeps asked for
        u.page(5)                            # pages 0 to 4 are built in; ours is the next one
        counts = []
        for mm in (1800, 1000, 300, 5000):
            u.command("sim set dist %d" % mm)
            u.wait(3)
            del plat.tone_log[:]
            u.wait(4)
            counts.append(len(plat.tone_log))
            print("something at %.1f m: %-28s %d beeps in 4 s" % (mm / 1000.0, "'" + u.rows.get(5, "").strip() + "'", counts[-1]))
        u.command("sim set dist 300")
        u.wait(3)
        u.key("B2")
        del plat.tone_log[:]
        u.wait(2)
        print("after B2: '%s', %d beeps in 2 s" % (u.rows.get(9, "").strip(), len(plat.tone_log)))
        ok = counts[0] < counts[1] < counts[2] and counts[3] == 0 and not plat.tone_log
        sys.exit(0 if ok else 1)
