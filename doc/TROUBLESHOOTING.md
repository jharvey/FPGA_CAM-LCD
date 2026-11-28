# FCL monocular: troubleshooting

What to check when something does not work, by symptom. For the first power-up of a new board use
[BRINGUP.md](BRINGUP.md) instead: it goes stage by stage with the values to expect.

**Where this comes from.** No board has been built yet. Every line here follows from the design and the software,
not from a fault that was seen and fixed. Treat it as the list of first things to look at, and add to it.

The fastest look at the unit is the USB port: `python firmware/tools/fcl_dash.py --port COM7` (Linux:
`/dev/ttyACM0`). The first lines after connecting say what the software found.

## Nothing happens at all

| Symptom | Look at | Then |
|---|---|---|
| No LED, no picture, on battery | cell voltages: under about 3.4 V the 3.3 V rail drops out | charge over USB-C; the charge LEDs D2 to D4 light while a cell charges |
| Nothing on USB power either | press B0: D11 (power hold) must light | D11 dark: BRINGUP stages 1 and 2 (5 V at TP7, then the rails) |
| D11 lights for a moment, then goes out | the FPGA's `SHUTDOWN` output, or a rail collapsing under load | measure +3V3 at TP3 while pressing B0; load no bitstream and try again: if it then stays on, the bitstream drives `SHUTDOWN` high |
| Switches off by itself after a while | the dashboard's cell rows before it happens: `OFF` means a cell is under 3.20 V | charge; the unit switches itself off to protect the cells |

## The picture

| Symptom | Likely cause | Check or fix |
|---|---|---|
| Backlight on, screen white or black, never a picture | the panel was not set up, or the FPGA has no bitstream | `FPGA_DONE` probe via high? LED D53 lights once the ESP32 is talking to the bridge in the bitstream. The panel set-up is sent once when the FPGA starts: press B0 briefly to reload the FPGA |
| Four coloured squares with a black cross, for about two seconds, then the picture | normal: the design's own test pattern at start | nothing |
| The four squares stay | the design is built with `FORCE_TEST_PATTERN` | rebuild with it at 0 |
| **Magenta** picture, or magenta flashes | the display has run out of camera data: the camera is not delivering, or the SDRAM path is too slow | camera clock at J1 pin 8 (25 MHz)? Camera seated in J1? If the camera works and magenta comes and goes, see "wrong pixels" below |
| Picture with **random wrong pixels**, sparkle, or columns shifted | SDRAM timing. The design meets timing at 100 MHz (9 % margin by the tool's estimate); the SDRAM's own clock-to-data timing is not modelled | load the fallback `fpga/prebuilt/full87/fcl_full_87.bit` (memory clock 87.5 MHz, 36 % margin): if the pixels are then right, it was timing. Note whether it changes with temperature. The remaining lever is the phase of the SDRAM clock (`fpga/IO_REMAP.md`, section Clocks) |
| Picture rolls, tears or is cut at one side | the panel does not like the timing: 17.86 MHz pixel clock, 640 clocks per line, 506 lines, 55.1 pictures per second | scope `pix_clk_out` (C13 via): 17.86 MHz? Then compare the porches in the LCD block with the panel's data sheet |
| Picture fine, but no text and no dot | the ESP32 is not talking to the bridge | dashboard: `$I,no answer from the FPGA bridge` means the wrong bitstream (camera-only) or the UART (TP12, TP13) |
| Text is there but garbled, or the wrong size | the font memory | rebuild; `python fpga/osd/test_osd.py` must pass |
| The view (camera / edges) is the opposite of what the menu says | the FPGA was reloaded while the ESP32 kept running: the FPGA only has a toggle | select View once more, or restart the ESP32 (`reboot`) |
| Colours wrong (red and blue swapped, or a colour missing) | an LCD data line, or the camera's colour order register | a missing bit shows as banding in the test pattern's squares; swapped colours with a good test pattern point at the camera set-up list |

## Sensors and readings

The start line `$I,sensors found 0x1F` has one bit per sensor: 1 IMU, 2 compass, 4 barometer, 8 ranger, 16 ADC.

| Symptom | Likely cause | Check or fix |
|---|---|---|
| `sensors found 0x00` | the I2C bus, or the bridge | TP8 / TP9 at 3.3 V when idle? `no answer from the FPGA bridge` before it? |
| One sensor missing | that part, or its address | BRINGUP stage 6 with an I2C adapter: 0x68 IMU, 0x1E compass, 0x5C barometer, 0x29 ranger |
| Heading wrong by a constant amount | declination or mounting | `cal set head0 <degrees>`; the `north` step of `fcl_calibrate.py` |
| Heading wanders or jumps near metal, or depends on tilt | the compass is not calibrated | menu **Compass cal**, away from steel, with the cells in (they are steel-cased); turn slowly through all six directions so that the soft-iron part is fitted too: the `$M` line's last number is then above 1.00 |
| Heading right in some directions, off in others, after a calibration | soft iron not fitted (too few readings), or the cells were changed since | calibrate again, turning more slowly; after a cell change, always |
| Pitch and roll swapped, or a sign wrong | the sensor's orientation on the board differs from what the software assumes | the `axes` step of `fcl_calibrate.py` reports it; the signs are in `firmware/esp32/fcl_fix.py` and `fcl_hubpy.py` |
| Level page not 0 on a level surface | mounting error of the sensor board | `level` step of the calibration, or **Level trim** on the phone page |
| Height drifts by a metre over minutes | weather: 1 hPa is about 8 m | **Zero height** before a measurement; the barometer is for changes over a short time |
| Distance always `---` | nothing within about 4 m, a dark or shiny target, bright sun, or the ranger's window covered | aim at a matt wall 1 m away |
| A cell shows `--` | no cell in that slot, or its sense divider | multimeter on the cell; `VBATn_SENSE` at U21 should be 0.544 x the cell voltage |
| Charge percent jumps under load | the table is for a resting cell | expected; the value settles when the load goes |
| `HOT` | a cell over 55 C | stop charging and let it cool; check the cell |

## Buttons, pages, graphics

| Symptom | Likely cause | Check or fix |
|---|---|---|
| B1 does nothing | the page changes on **release**; held for 0.7 s it opens the menu instead | press and let go |
| B1 switches camera / edges instead of the page | the ESP32 has not taken the buttons over: it is not running or not connected to the bridge | dashboard start lines; until then B1 and B2 work the picture directly, by design |
| B2 does nothing on Height or Survey, low beep | the ranger sees nothing | the hint row says `OUT OF RANGE` |
| No reticle, horizon or tape | the Overview shows none unless switched on | menu **Graphics**, or `hud all` |
| The horizon line disappears | the horizon is out of the picture (more than about 18 degrees of pitch at the standard lens angle) | expected |
| Horizon line does not sit on the real horizon | lens angle or level trim | `lens` and `level` steps of the calibration (`hfov`, `pitch0`, `roll0`) |
| My own page does not appear | `fcl_user.py` has an error | the dashboard shows `$I,fcl_user.py stopped: ...` at start |

## Wi-Fi, phone page, updates

| Symptom | Likely cause | Check or fix |
|---|---|---|
| `$W,failed` | wrong password, or the network is 5 GHz only (the ESP32 uses 2.4 GHz) | `wifi <name> <password>` again; `wifi scan` lists what it sees |
| Connected, but the page does not open | phone on another network or on mobile data; some guest networks keep devices apart | same network, `http://` not `https://`, the address from the `$W` line |
| Buttons work, **Level trim** says it needs the PIN | no PIN typed, or none set | `webpin 1234` on the USB port, then the same digits in the PIN box |
| `too many wrong PINs` | five wrong tries | wait a minute |
| `fcl_update.py`: `no answer` | address, or the unit is busy restarting | ping the address; wait 10 s |
| `fcl_update.py`: a file `REFUSED` | PIN, or the flash is full | the line says which; `--dry` shows the plan; old logs are on the flash when no SD card is in (`mpremote rm :fcl001.log`) |
| After installing, the USB port shows the `>>>` prompt and no `$I` lines | `main.py` did not run or stopped: press Ctrl-D and read the error. A `boot.py` from before 2026-11-28 stops at an unconfigured WebREPL | `python firmware/tools/fcl_install.py --port <port>` again (it copies the current `boot.py`) |
| After an update the unit does not start its stream | an error in a new file | USB port: the Python prompt shows the error. Create an empty file `nostream` to stay at the prompt (`mpremote fs touch :nostream`), copy the old file back with `mpremote cp`, remove `nostream` |
| After a bitstream update no picture | the wrong file was loaded | the bitstream in the FPGA's memory is only read at power-on: load the right one with `fpga <file>` or FTP, or `--flash` again |

## Logging

| Symptom | Likely cause | Check or fix |
|---|---|---|
| `log stopped: ... is the limit` | 2 MB on the ESP32's flash | put an SD card in, or `stream 1` (one line a second) for long runs |
| `log not started` | no room, or the card is not mounted | the phone page lists the logs on the unit; download the ones to keep, then delete them over USB (`mpremote rm :fcl001.log`) |
| The log on the card is empty after pulling the power | up to 5 s of lines are still in memory | `log off` before switching off |

## The simulator and the tests on a PC

| Symptom | Likely cause | Check or fix |
|---|---|---|
| `fcl_dash.py --port`: no module named serial | pyserial is not installed | `pip install pyserial` (the simulator needs nothing) |
| `test_mpy.py`: SKIPPED | no MicroPython program on this PC | build the Unix port and set `MICROPYTHON=/path/to/micropython` |
| `test_full.py` takes an hour | it simulates every clock edge of the whole FPGA design | run it after changes to the FPGA sources only |
| An FPGA build fails with timing FAIL | a change slowed a path | the build prints the clock results; `fpga/prebuilt/MANIFEST.md` has the last good ones |
