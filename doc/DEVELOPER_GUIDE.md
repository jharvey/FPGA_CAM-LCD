# FCL monocular: developer guide

How the software is layered, how to add a page of your own, and where each thing is tested.
The user's view is in [USER_MANUAL.md](USER_MANUAL.md); the USB protocol in [FIRMWARE_GUIDE.md](FIRMWARE_GUIDE.md).

**Status.** All of this runs in the simulator and passes its tests. Nothing has run on a real board. The ESP32
files run under ordinary Python and under real MicroPython 1.24 on a PC (the Unix port, `test_mpy.py`), with the same
output line for line; they have not run on an ESP32, whose pins, I2S, Wi-Fi and memory limits the PC does not have.

## Layers

```mermaid
flowchart LR
  subgraph FPGA["FPGA (ECP5), no CPU"]
    cam["camera to TFT<br/>(Icestudio project)"] --> osd["overlay<br/>fcl_osd_stream.v"] --> lcd(["round TFT"])
    br["bridge<br/>fcl_bridge.v"] --> osd
    br --> cam
  end
  sens(["IMU, compass, barometer,<br/>ranger, battery ADC,<br/>buttons, servos"]) <--> br
  subgraph ESP["ESP32-S3 (MicroPython)"]
    drv["fcl_bridge.py<br/>driver"] --> hub["fcl_hubpy.py<br/>hub"]
    hub --> app["fcl_app.py<br/>pages, menu"]
    hub --> usb["fcl_usb.py<br/>USB text protocol"]
    hub --> web["fcl_web.py<br/>phone page"]
  end
  br <-- "UART 921600" --> drv
  usb <--> pc(["PC: fcl_dash.py,<br/>fcl_calibrate.py, fcl_log.py"])
  web <--> phone(["phone browser"])
```

| Layer | File | Job |
|---|---|---|
| FPGA bridge | `fpga/bridge/fcl_bridge.v` | reads the sensors on its own clock and time-stamps them, drives servos and outputs, writes the overlay memory; one command frame in, one answer out |
| FPGA overlay | `fpga/osd/fcl_osd.v`, `fcl_osd_stream.v` | 30 x 15 characters, the graphics (reticle, horizon, compass tape) and the down dot over the video on its way to the panel |
| FPGA top | `fpga/full/fcl_top.v` | the camera design + overlay + bridge in one bitstream |
| Driver | `firmware/esp32/fcl_bridge.py` | the bridge's commands as Python calls |
| Hub | `fcl_hubpy.py` with `fcl_fix.py` (attitude filter, viper), `fcl_magcal.py` (compass), `fcl_cfg.py` (calibration values), `fcl_calc.py` (charge, dot, overview text) | turns samples into heading, pitch, roll, height, distance, charge; owns the keys, servos and the screen text |
| **Apps** | **`fcl_app.py`** | **the pages (Level, Height, Bearing, yours), the menu, and the `Unit` calls they use** |
| Outside world | `fcl_usb.py` (USB lines), `fcl_web.py` (phone page, files), `fcl_usbdev.py` (the ESP32's main loop, Wi-Fi, audio, log file) | |
| On a PC | `firmware/tools/fcl.py` (the unit in a script), `fcl_dash.py`, `fcl_survey.py`, `fcl_log.py`, `fcl_calibrate.py`, `fcl_update.py` | everything goes through the USB lines or the phone page's addresses |

A page never talks to a sensor or to the FPGA. It asks the `Unit` for readings and gives back lines of text.

## A page of your own

A page is a class with four optional methods. This is the whole of `firmware/esp32/fcl_user_example.py`, a climb
meter:

```python
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
            unit.say("climb %+.1f m in %.0f s" % self.done)
            unit.beep(1320)

    def draw(self, unit, put):   # 20 times a second
        put(fcl_app.T_ROW, self.name)
        ...                      # put(row, text) writes a centred line

def setup(apps):
    apps.add(Climb())
```

Try it on a PC:

```
python firmware/sim/fcl_sim.py --user fcl_user_example --web 8080
python firmware/sim/fcl_sim.py --user path/to/my_page.py --web 8080
```

Open `http://127.0.0.1:8080`, press **B1 page** until CLIMB shows, then **B2 action**. On the unit: copy your file
to the ESP32 as `fcl_user.py` (over Wi-Fi: `python firmware/tools/fcl_update.py <address> --pin <pin> --user my_page.py`);
`fcl_usbdev.py` calls its `setup(apps)` at start. A mistake in it is reported on the
USB port (`$I,fcl_user.py stopped: ...`) and the unit carries on without it.

### What a page gets

| Method | Called | Use it for |
|---|---|---|
| `start(unit)` | the page is selected (B1, `mode n`) | reset your state |
| `stop(unit)` | another page is selected | release what you held (a servo, a pan) |
| `button(unit)` | B2 is pressed on your page | your action |
| `draw(unit, put)` | every telemetry frame, 20 per second | `put(row, text)`: a centred line, 30 characters at most |
| `hud` (an attribute) | read every frame | graphics while your page shows: `fcl_app.RETICLE | fcl_app.HORIZON | fcl_app.TAPE`, 0 for none |

A second example, with a test at its end, is the parking sensor of [lesson 6](lessons/README.md)
(`doc/lessons/examples/lesson6_page.py`). A page file must import nothing the ESP32 lacks: `math` and `fcl_app` are
safe; `os.path`, `random.Random` and `str.ljust` are not there. `python firmware/sim/test_mpy.py` shows what real
MicroPython accepts.

Rows for a page: `T_ROW` 4 (title), `V_ROW` 5, `V2_ROW` 8, `H_ROW` 9 (hint). The other rows belong to the Overview
text, which stays on screen under your page. The screen is round: rows 4 to 10 show 24 or more characters, row 1
about 18, row 0 about 10.

### The `Unit` calls

| Call | Gives / does |
|---|---|
| `unit.heading()`, `unit.pitch()`, `unit.roll()` | degrees; heading 0 = north, clockwise; pitch + = lens up; roll + = right side down |
| `unit.height()` | metres above the last zero (barometer) |
| `unit.pressure()` | hPa |
| `unit.distance()` | metres from the ranger, or `None` when nothing is in reach (about 4 m) |
| `unit.cells()` | `[(millivolts, percent or None, degrees C)]` for the three cells |
| `unit.time_ms()` | the unit's clock, milliseconds |
| `unit.servo(n, us)` | servo 1..6, pulse 500..2500, 0 = off |
| `unit.follow(on)`, `unit.pan(heading or None)` | level servo; servo 2 holds a heading |
| `unit.zero()`, `unit.view(edges)`, `unit.overlay(mask)` | zero the height; camera or edge picture; Overview items |
| `unit.graphics(mask)` | graphics on every page (the user's setting; your page's own are its `hud` attribute) |
| `unit.beep(hz, ms)` | a tone on the speaker |
| `unit.say(text)` | one `$I,text` line on the USB stream and in the log |
| `unit.line(text)` | a line of your own kind, as it is (`$X,...`): for results a PC tool should read, as the Survey page's `$P` |

### Rules that keep the unit responsive

- `draw` runs 20 times a second between sensor frames. Keep it to arithmetic and a few `put` calls: no loops over
  history, no file access, no waiting.
- Do not call the bridge driver from a page. `Unit` calls are safe: the hub sends commands to the FPGA only from
  its `tick_ms`, never while frames are being read (a command sent then would be answered out of order).
- Readings can be `None` before the first frame; `button` and `draw` are only called once there is telemetry.
- Text is ASCII 32..126: that is what the FPGA's font has.

## Keys and the menu

`fcl_hubpy.Hub._inputs` only notes key changes; `tick_ms` turns them into `"B1"`, `"B2"` or `"B1L"` (B1 held 0.7 s;
B1 acts on release so that holding it can mean something else) and hands them to `Apps.key`. The menu is a tuple of
`(label function, action function)` in `Apps.__init__`: add a pair to add an item.

In the full FPGA design B1 and B2 are also wired to the camera design's own keys (view, threshold). At start the hub
sets OUT bit 7, which hands the two buttons to the ESP32; from then on the hub presses the video keys itself
(OUT bits 4, 5, 6, held 100 ms each). If the ESP32 never starts, B1 and B2 work the picture directly, as in the
camera-only design. The video logic only has a toggle for the view, so the hub keeps count of which view is on.

## Graphics

The FPGA draws three things under the text from 8 bytes the hub sends when they change (bridge command 0x29,
`fcl_bridge.osd_hud`): which of them are on, the horizon as a line `a*dx + b*dy + 128*c = 0` in pixels from the screen
centre, and how far the compass ticks are moved. `fcl_calc.hud_values(heading, pitch, roll, hfov)` makes the numbers;
`fcl_osd.v` tests every pixel against them (two multipliers and a few comparators). The same pixel rules are in
`firmware/sim/fcl_osd.py` (`hud_pixel`), and `fpga/osd/test_osd.py` compares the two for whole frames. What is drawn
on a page is `hub.hud_mask | page.hud`, nothing while the menu is open. The USB stream reports it as
`$H,flags,a,b,c,tape`; the phone page draws its preview from the same five numbers.

To add a shape: a flag bit and the pixel test in `fcl_osd.v` and in `hud_pixel`, a frame in `test_osd.py`, the
bit's name in `fcl_calc.py` / `fcl_app.py` and in the `hud` command.

## From a PC: fcl.py

```python
import sys; sys.path.insert(0, "firmware/tools")
import fcl
with fcl.connect("sim", realtime=False) as u:      # or "COM7", "tcp:127.0.0.1:7007", "replay:trip.log"
    u.command("sim set heading 90")                # simulator only: turn the unit
    u.wait(3)
    print(u.heading, u.pitch, u.height, u.distance)
    u.page("survey"); u.key("B2")
    print(u.points(), u.rows)                      # the Survey points; the LCD rows the page wrote
    for t in u.telemetry(count=10):
        print(t["t_ms"], t["alt_m"])
```

`realtime=False` gives a simulator whose time only moves in `wait()` and `command()`: 4 s of the unit take about
half a second, and a script gives the same result every run. That is how the lessons and `test_tools.py` use it.
A refused command raises `fcl.Error` with the unit's text.

## Calibration values

`fcl_cfg.py` holds the names, defaults and limits (the table at its top). The hub applies them where a reading is
made. To add one: a row in `DEFAULTS`, a use in `fcl_hubpy.py`, and if a person has to measure something, a step
in `firmware/tools/fcl_calibrate.py` (a function that returns `[(name, ok, text)]`, plus an entry in `RUN` and
`STEPS`, plus what the simulated user does for it in `DemoUser`).

## The phone page

`fcl_web.py` is one file: a non-blocking HTTP server polled from the main loop and the page as a string.

| Address | Does | Who |
|---|---|---|
| `GET /` | the page | anyone |
| `GET /s` | the state as JSON: telemetry, LCD rows, graphics, level trim, whether a PIN is set | anyone |
| `POST /c` | one command line: those in `ALLOWED` | anyone |
| | those in `PIN_ALLOWED` (`cal`, `reboot`, `fpga`) | header `X-Pin` |
| `GET /files` | names, sizes and CRC-32 of the `.py`, `.bit` and `.log` files | anyone |
| `GET /f/<name>` | one of those files, sent a piece per call of `poll()` | anyone |
| `PUT /f/<name>` | store a `.py` or `.bit`; header `X-Crc`; written as `<name>.new`, renamed when whole and correct | header `X-Pin` |

The PIN is set on the USB port only (`webpin`), kept in `webpin.txt` (never served), and with none set the PIN
actions are refused. Five wrong PINs lock them for a minute. It is sent in clear text over HTTP: enough against a
neighbour on the same Wi-Fi, not against someone recording the network. The page polls `/s` three times a second;
there is no websocket. A connection is a small state machine (reading a request, receiving a file, sending a
file), so a 440 kB bitstream moves between sensor frames without stopping them.

## FPGA builds

| Bitstream | Build | What |
|---|---|---|
| full | `python fpga/full/build_full.py` | camera to TFT + overlay + bridge: the unit's bitstream |
| bridge | `python fpga/bridge/build_bridge.py` | the bridge alone: first bring-up of sensors, buttons, servos |
| camera | `python fpga/build.py` | the Icestudio camera project alone |

`python fpga/make_prebuilt.py` builds all three, runs the tests and stores the results with checksums in
`fpga/prebuilt/`; `--check` rebuilds and compares.

Clocks of the full design, as built on 2026-11-27 (nextpnr's estimates; `fpga/prebuilt/MANIFEST.md` has the
figures of the stored build):

| Clock | Runs at | From | Drives |
|---|---|---|---|
| board | 25 MHz | oscillator Y1 | bridge, overlay text memory, camera clock output |
| memory | 100 MHz | PLL, 25 x 4 | camera capture, the FIFOs, SDRAM controller, edge filter |
| pixel | 17.857 MHz | PLL, 25 x 5 / 7 | LCD timing, panel set-up, overlay |

`python fpga/full/test_full.py` simulates the whole of it for 113 ms (about an hour): a camera model sends a known
picture, an SDRAM model stores it, a script plays the ESP32, and every pixel that leaves for the panel is compared
with what it should be. Run it after any change to the camera project or to `fpga/full`.

The full design takes the generated `main.v` unchanged. `build_full.py` writes `fcl_cam.v`, the same module with the
port names of the `.ice` file, and the pin file from the `.ice` pins plus `firmware/hub/fcl_hub_pins.lpf`. The
overlay sits between the camera design's LCD outputs and the pins; it recovers the pixel position from DE and VS
and delays the sync signals by its own three clocks. The pixel clock is the camera design's `debug-OUT` output.

The camera project (`fpga/CameraToTFTSobel_FCL.ice`) is an Icestudio file: open it in Icestudio to see the blocks.
`fpga/build.py` generates the same Verilog Icestudio would, so changes made in either place build the same way. A
change to a code block shows in `git diff` as one long line of JSON; `python fpga/build.py --gen-only --out x` and
a diff of `x/main.v` against `fpga/prebuilt/camera/main.v` shows it as Verilog.

## Tests

| Test | Covers | Run |
|---|---|---|
| `test_app.py` | pages, the tools incl. Survey, the menu, graphics, `$L` / `$H` / `$P` lines, logging, calibration values, pan hold, the example page | `python firmware/sim/test_app.py` |
| `test_web.py` | the phone page over real sockets: page, state, commands, refusals, the PIN and its lock, files up (CRC, broken, refused names, 300 kB) and down, a silent client | `python firmware/sim/test_web.py` |
| `test_tools.py` | `fcl.py`, `fcl_survey.py`, `fcl_update.py` against the simulator | `python firmware/sim/test_tools.py` |
| `test_lessons.py` | the six lesson scripts | `python firmware/sim/test_lessons.py` |
| `test_mpy.py` | the ESP32 files under real MicroPython (Unix port): imports, a 40 s session compared line for line with ordinary Python, and the real main loop `fcl_usbdev.run()` with stand-ins for pins, I2S, UART and Wi-Fi. Says SKIPPED when there is no `micropython` | `MICROPYTHON=/path/to/micropython python firmware/sim/test_mpy.py` |
| `test_calibrate.py` | the guided calibration against simulated hardware with errors built in | `python firmware/sim/test_calibrate.py` |
| `test_usb.py` | the USB stream: every older command, buttons, Wi-Fi, audio, overlay | `python firmware/sim/test_usb.py` |
| `test_filter.py`, `test_magcal.py` | attitude filter; compass calibration | `python firmware/sim/test_filter.py`, `test_magcal.py` |
| `test_bridge.py` | `fcl_bridge.v` in Icarus Verilog against the Python model | `python fpga/bridge/test_bridge.py` |
| `test_osd.py` | the overlay pixel for pixel (text, dot, graphics), alone and behind `fcl_osd_stream.v` with video timing and a second clock | `python fpga/osd/test_osd.py` |
| `test_full.py` | the whole FPGA design: clocks, camera set-up, panel set-up, a camera picture through the SDRAM to the panel pins pixel for pixel, the view key, the bridge alongside (about an hour) | `python fpga/full/test_full.py` |

What the simulator is: the ESP32 files run as they are, on a Python model of the bridge that is checked frame by
frame against the Verilog, on register-level models of the sensors. What it cannot show: timing and memory on the
real ESP32, real sensor behaviour, and the FPGA on a board.

Running the files under real MicroPython found three faults that ordinary Python had hidden (2026-11-27): the
bridge driver deleted slices of a bytearray, which MicroPython cannot do (the driver would have stopped at the
first frame); the attitude filter had a number above 2^30 in viper code, which a 32-bit MicroPython does not take
as a native integer; and a log file that could not be opened stopped the main loop. `test_mpy.py` passes with a
64-bit and a 32-bit build of MicroPython; `fcl_fix.py` gives the same results with both word sizes. What remains is
the ESP32 itself: Xtensa machine code instead of x86, its memory, and its real pins and radio.

## Not done

- Soft-iron correction of the compass.
- Nothing has been loaded into a board. The whole FPGA design is simulated with models of the camera, the SDRAM
  and the panel's pins; those models have no delays.
- **Timing margin of the memory clock.** It runs at 100 MHz and nextpnr estimates 103 MHz possible: a pass by 3 %.
  The SDRAM's own timing against the FPGA's pins (clock out, data back) is not checked by any tool here. A picture
  with wrong pixels on the first board would point at this; the lever is the phase of the SDRAM clock, which is
  the inverted memory clock today.
- The camera capture, the SDRAM clock and the pixel clock of the camera project were changed on 2026-11-27
  (`fpga/IO_REMAP.md`, Clocks). The project's author should look at those three blocks in Icestudio.
- The phone page's PIN is not encryption. HTTPS on the ESP32 would need certificates and more memory.
- Audio and the phone page at the same time have not been tried on the ESP32.
- A file upload larger than the free flash is refused only when the write fails; the update tool does not ask for
  the free space first.
