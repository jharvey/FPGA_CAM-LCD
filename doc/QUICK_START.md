# FCL monocular: quick start

One page. The full story is in [USER_MANUAL.md](USER_MANUAL.md).
A printable copy of this page: [QUICK_START.pdf](QUICK_START.pdf).

**No unit yet?** Everything below works in the simulator on any PC with Python 3:
`python firmware/sim/fcl_sim.py --web 8080`, then open `http://127.0.0.1:8080`.

## Buttons

| | Press | Hold |
|---|---|---|
| **PWR** | | 2 s: off |
| **B1** | next page | 0.7 s: menu |
| **B2** | the page's action | |

In the menu: B1 down, B2 select.

## Pages (B1 steps through them)

| Page | What it shows | B2 |
|---|---|---|
| **Overview** | heading, pitch and roll, distance, height, cells | recording mark |
| **Level** | pitch, roll, slope in percent, horizon line | |
| **Height** | height of an object | 1: at its foot. 2: at its top |
| **Bearing** | the way back to a marked direction | mark |
| **Survey** | points, side lengths, area | store a point |

Aim with the cross at the centre. The ranger reaches about 4 m.

## Screen rows

`048 NE` heading. `P+2.0 R-1.5` pitch (+ lens up) and roll (+ right side down). `D 1.87m` distance.
`ALT +1.2m` height since the last zero. `84% 77% 23%` the three cells. `25 26 27C` their temperatures.
`LOW` a cell under 3.40 V. `HOT` over 55 C. The dot marks straight down.

## First time

1. Charge over USB-C until the three charge LEDs go out.
2. Menu, **Compass cal**: point the unit up, down and to four sides until the item reads 6/6.
3. On a level surface: `python firmware/tools/fcl_calibrate.py --port COM7` for the rest (10 minutes, a tape measure
   and a multimeter).
4. Wi-Fi, once, on the USB port: `wifi <name> <password>`, then `webpin 1234`. The menu's Wi-Fi item shows the
   address; open it in a phone's browser.

## Every time

- **Zero height** (menu) before measuring heights with the barometer.
- **Log: on** (menu) records the trip; download it from the phone page.
- Hold still for a second before B2: every measurement uses the reading at that moment.

## On a PC

| | |
|---|---|
| `python firmware/tools/fcl_dash.py --port COM7` | everything on one screen; type `help` |
| `python firmware/tools/fcl_survey.py --from COM7 --svg plan.svg` | the Survey points as a plan |
| `python firmware/tools/fcl_log.py trip.log --plot trip.png` | a log as a picture |
| `python firmware/tools/fcl_update.py <address> --pin 1234` | new software over Wi-Fi |
| `python firmware/tools/fcl_bringup.py --port COM7 --board 1` | a new board's checks, with a report |
| `import fcl; u = fcl.connect("COM7")` | the unit in a Python script |

Not working? [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
