# Six lessons with the FCL monocular

Measuring with angles, a compass and a ruler made of light, and writing a first program for a real instrument.
For ages of about 11 and up with an adult, or alone from about 14.

**You need:** a PC with Python 3. No unit: every lesson runs in the simulator, which runs the unit's own software
on models of its sensors. With a real unit, each lesson ends with the same thing done by hand.

**How the scripts work.** Each lesson has a short script in [examples](examples). In the simulator there is no hand
to hold the unit, so the script "holds" it by typing: `sim set heading 90` turns it east. Everything else is what
you would do with the real one. Read the script first, guess what it will print, then run it.

**Status.** The scripts are run by `python firmware/sim/test_lessons.py`, so they work as printed here. The parts
"with a real unit" have not been tried: no unit exists yet.

| | Lesson | The idea | Script |
|---|---|---|---|
| 1 | What the unit knows | sensors turn the world into numbers | `lesson1_readings.py` |
| 2 | Angles and slopes | the tangent of an angle | `lesson2_slope.py` |
| 3 | How tall is it? | a height from two angles and one distance | `lesson3_height.py` |
| 4 | Finding north | why a compass must be calibrated | `lesson4_compass.py` |
| 5 | A map of a room | coordinates, and area from corners | `lesson5_room.py` |
| 6 | A page of your own | a program that runs on the unit | `lesson6_page.py` |

## Lesson 1: what the unit knows

**Start.** Run `python firmware/sim/fcl_sim.py --web 8080` and open `http://127.0.0.1:8080`. That page is the
unit's screen and its buttons. Watch the heading turn: the simulator plays a one-minute loop.

**Then.** `python doc/lessons/examples/lesson1_readings.py`. It faces the unit five ways and prints what the
compass, the tilt sensor and the ranger say.

**Look for.** The compass is right to a degree or two, not exactly: no sensor is exact. The last wall is 6 m away
and the ranger reports nothing: it sends out light and times the echo, and from that far the echo is too weak.

**Questions.** Which reading would change if you walked upstairs? (None of these: add `u.height`.) Why does the
script wait 4 seconds after turning?

**With a real unit.** Stand it on a table, read the heading, turn it a quarter turn. Did the heading change by 90?

## Lesson 2: angles and slopes

**The idea.** A road sign says 10 %: the road climbs 10 m for every 100 m along the ground. On a triangle with the
angle `a` at the bottom, climb / along = tan(a). So slope in percent = 100 x tan(a).

**Do it.** `python doc/lessons/examples/lesson2_slope.py` puts the unit on five ramps. For each it works out the
angle from the ramp, and compares the slope with what the unit's Level page shows.

**Look for.** A 100 % slope is 45 degrees, not 90. Doubling the angle does not double the slope: compare 11 and 27
degrees.

**Questions.** What angle is a 100 % slope? What would the page show at 90 degrees, and why does it show nothing
there?

**With a real unit.** Page Level. Lay the unit along a ramp, a book cover, a staircase rail. Measure rise and run
with a tape and compare.

## Lesson 3: how tall is it?

**The idea.** You cannot hold a tape to the top of a tree, but you can aim at it. Aim at the foot: the ranger gives
the distance `d` along your line of sight, and the unit its angle `a1` below level. Tilt to the top: angle `a2`.

```
along the ground   g = d x cos(a1)
foot below you     b = d x sin(a1)          (negative: you are looking down)
top above you      t = g x tan(a2)
height             = t - b
```

**Do it.** `python doc/lessons/examples/lesson3_height.py` measures a 2.05 m door from 2.5 m away, does the sums
itself, and compares with the unit's Height page.

**Questions.** The script stands 2.5 m away. Would the answer change from 3.5 m? What if you take a step forward
between the two sightings? Which sighting needs the ranger, and why only that one?

**With a real unit.** Page Height: aim the cross at the foot of a door, B2; at the top, B2. Check with a tape. Try
again from further away, then from so far that the foot reads `OUT OF RANGE`.

## Lesson 4: finding north

**The idea.** A compass feels the earth's magnetic field, which is weak. Steel near it, such as the unit's own
battery cells, adds a field that turns with the unit. The compass then reads wrong, by a different amount in every
direction. Turning the unit to all sides shows the added field: the readings lie on a ball whose centre is off
zero by exactly that field. Take the centre away and the compass is right again.

**Do it.** `python doc/lessons/examples/lesson4_compass.py`. It measures the error in eight directions, puts a
small magnet next to the compass, measures again, calibrates, and measures a third time.

**Look for.** With the magnet the error is large in some directions and small in others. Which directions, and why
those? (Where the magnet's field points along the earth's it changes the strength, not the direction.)

**Part 2: bent fields.** Plain steel (not a magnet) does something else: it bends the earth's field, stronger along
one axis and weaker along another. The readings then lie on a squashed ball, an ellipsoid, and the first
calibration cannot help: the script shows about 10 degrees of error, changing sign twice in a turn. A second
calibration with the unit turned, tilted and rolled slowly for half a minute lets the unit fit the ellipsoid and
undo the bend: under a degree again.

**Questions.** Why must the unit be pointed up and down as well, not only turned round? Why does the bent field make
an error that repeats twice in one turn, while the magnet's repeats once? Would the calibration still be right after
you put in different cells?

**With a real unit.** Menu, Compass cal. Then hold a steel spoon near the top of the unit and watch the heading.

## Lesson 5: a map of a room

**The idea.** A direction and a distance fix a point. From where you stand, a corner at compass heading `h`, at
distance `g` along the ground, is `g x sin(h)` to the east and `g x cos(h)` to the north. With all the corners you
have a map. The area of any shape with straight sides comes from its corners alone: go round, add up
`x1 x y2 - x2 x y1` for every side, and halve the total (the "shoelace" sum).

**Do it.** `python doc/lessons/examples/lesson5_room.py` surveys an L-shaped room from one spot, prints the table
of points, works out the area both ways, and writes `lesson5_plan.svg`: open it in a browser.

**Look for.** The corners are a few centimetres off, each in a different direction: that is the compass. The area
is still close. Why does a small turn of the whole map not change the area?

**Questions.** Split the L into two rectangles and work out the area by hand. What happens to the shoelace sum if
you take the corners in a jumbled order?

**With a real unit.** Page Survey, in a room with clear corners at floor level, standing still in one place. Then
`python firmware/tools/fcl_survey.py --from COM7 --svg room.svg`. Measure two walls with a tape and compare.

## Lesson 6: a page of your own

**The idea.** The unit's pages are small programs. A page gets the readings and gives back lines of text; it may
beep and move servos. [lesson6_page.py](examples/lesson6_page.py) is a parking sensor in 25 lines: the closer
something is, the faster it beeps.

**Do it.** Read the class `Parking`. `draw` runs 20 times a second: it must be quick and must not wait. So the page
does not sleep between beeps; it notes the time the next beep is due. Run the file to test it, then see it live
: `python firmware/sim/fcl_sim.py --web 8080 --user doc/lessons/examples/lesson6_page.py`, press
**B1 page** until PARKING shows, and move the wall from another terminal with the dashboard
(`python firmware/tools/fcl_dash.py --tcp 127.0.0.1:7007`, then type `sim set dist 500`).

**Change it.** Make the bar grow instead of shrink. Make it silent beyond 1 m. Show `STOP` under 20 cm. Run the
file after each change: its last lines test your page.

**Questions.** What would happen to the rest of the unit if `draw` waited one second? Why does the page ask the
unit for the time instead of counting calls?

**With a real unit.** `python firmware/tools/fcl_update.py <address> --pin 1234 --user lesson6_page.py`. All the
calls a page may use are in [DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md).
