"""Lesson 4: why a compass has to be calibrated.

A piece of magnetised steel next to the compass adds its own field to the earth's.  The compass then reads wrong,
by an amount that depends on which way you face.  Calibration finds the added field and takes it away.

    python doc/lessons/examples/lesson4_compass.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "firmware", "tools"))
import fcl      # noqa: E402

DIRECTIONS = (0, 45, 90, 135, 180, 225, 270, 315)


def errors(u):
    """face each direction in turn; -> how far off the compass is, in degrees"""
    out = []
    for d in DIRECTIONS:
        u.command("sim set heading %d" % d)
        u.wait(4)
        out.append((u.heading - d + 180) % 360 - 180)
    return out


def show(title, errs):
    print(title)
    for d, e in zip(DIRECTIONS, errs):
        print("  facing %3d   compass off by %+6.1f  %s" % (d, e, "#" * min(60, int(abs(e) + 0.5))))
    print("  worst: %.1f degrees" % max(abs(e) for e in errs))


with fcl.connect("sim", realtime=False) as u:
    u.command("magcal auto off")                 # for this lesson the unit must not correct itself as it goes
    u.command("sim set pitch 0")
    u.command("sim set roll 0")
    u.wait(3)
    clean = errors(u)
    show("1. Nothing near the compass", clean)

    u.command("sim hardiron 40 -30 20")          # a magnet: 60, -45 and 30 milligauss along the unit's three axes
    spoiled = errors(u)
    show("\n2. A small magnet next to the compass", spoiled)

    print("\n3. Calibrating: point the unit up, down, and to four sides")
    u.command("magcal start")
    for pitch, heading in ((80, 0), (-80, 0), (0, 0), (0, 90), (0, 180), (0, 270)):
        u.command("sim set pitch %d" % pitch)
        u.command("sim set heading %d" % heading)
        u.wait(4)
    u.command("sim set pitch 0")
    print("   the unit says:", u.command("magcal stop"))
    u.wait(2)
    fixed = errors(u)
    show("\n4. The same magnet, after calibration", fixed)

    worst = [max(abs(e) for e in errs) for errs in (clean, spoiled, fixed)]
    ok = worst[0] < 3 and worst[1] > 8 and worst[2] < 4
    print("\nworst error: %.1f clean, %.1f with the magnet, %.1f after calibration  %s" % (worst[0], worst[1], worst[2], "OK" if ok else "UNEXPECTED"))
    sys.exit(0 if ok else 1)
