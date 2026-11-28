"""Lesson 4: why a compass has to be calibrated.

A piece of magnetised steel next to the compass adds its own field to the earth's.  The compass then reads wrong,
by an amount that depends on which way you face.  Calibration finds the added field and takes it away.
Part 2: plain steel bends the earth's field instead (soft iron); a slower calibration finds that too.

    python doc/lessons/examples/lesson4_compass.py
"""
import math
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

    # ---- part 2: soft iron.  Plain steel near the compass does not add a field, it bends the earth's: stronger
    # along one axis, weaker along another.  The readings then lie on a squashed ball, an ellipsoid.
    u.command("sim softiron 1.2 0.85 1 0.05 0 0")
    bent = errors(u)
    show("\n5. Steel near the compass bends the field (the calibration from step 3 is still in use)", bent)

    print("\n6. Calibrating again: turning, tilting and rolling the unit slowly, for about 40 seconds, so the compass sees")
    print("   the field from every side and the unit can find the ellipsoid")
    u.command("magcal start")
    t = 0.0
    while t < 45 and u.src.sim.hubpy.cal.manual:      # it finishes by itself once every direction has been seen
        u.command("sim set heading %.0f" % (40 * t % 360))
        u.command("sim set pitch %.0f" % (80 * math.sin(2 * math.pi * t / 11)))
        u.command("sim set roll %.0f" % (60 * math.sin(2 * math.pi * t / 7)))
        u.wait(0.5)
        t += 0.5
    for k in ("pitch", "roll"):
        u.command("sim set %s 0" % k)
    print("   it finished by itself after %.0f s" % t if not u.src.sim.hubpy.cal.manual else "   the unit says: " + u.command("magcal stop"))
    u.wait(2)
    unbent = errors(u)
    show("\n7. After the second calibration", unbent)
    w2 = [max(abs(e) for e in errs) for errs in (bent, unbent)]
    ok2 = w2[0] > 4 and w2[1] < 3
    print("\nworst error: %.1f with the bend, %.1f after the second calibration  %s" % (w2[0], w2[1], "OK" if ok2 else "UNEXPECTED"))
    sys.exit(0 if ok and ok2 else 1)
