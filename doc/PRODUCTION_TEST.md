# Production test (boards of a validated design)

The short check for every board once the design has passed the full first power-up in `doc/BRINGUP.md`. It keeps
only the checks that catch assembly faults (shorts, missing or wrong parts, bad BGA joints, dead chips) and skips the
design checks (ripple, clock frequency, the lowest working voltage, reverse-polarity, charger behaviour, ID by ID
sensor reads) that do not change from board to board.

**Golden values:** the "Result" columns of the first good board in `BRINGUP.md`. Copy them into the "Golden" column
below once; every later board is compared with them. A board more than about 20 % away from the golden value on a
resistance or current row gets the full `BRINGUP.md` treatment for that stage.

Roughly 10 minutes per board with the files already on the PC.

## What you need

Multimeter, lab supply with current limit and a USB-C plug breakout, a USB-C cable to the PC, a microSD card, a charged
18650. On the PC: the release bitstream and the ESP32 files (same as `BRINGUP.md` stage 3).

## Checks

Probe points (bare vias on the back) are listed in `doc/PROBE_POINTS.md`.

| # | Check | How | Golden | Pass | Result |
|---|---|---|---|---|---|
| P1 | Visual | JLC's AOI / X-ray report for the batch; look over J17, U9, U23, the battery contacts; RV2 empty, RV3 fitted | | nothing odd | |
| P2 | Cell slots | ohms, + contact to - contact, slots 1-3 (`BRINGUP.md` Stage 0 cell rows) | | > 1 kΩ, near golden | |
| P3 | Core and I/O rails | ohms to TP1: TP4 (+1V1), TP3 (+3V3), TP6 (VSYS) | | near golden; TP4 > 1 Ω | |
| P4 | Off current | supply 5.0 V, limit 50 mA, into J17 through the breakout; on for 1 s, then leave on | | a few mA, flat | |
| P5 | On current | limit 300 mA, press B0 | | near golden, flat, D11 lit | |
| P6 | Rails | TP3, TP5, TP4 | 3.33 / 2.51 / 1.10 V | ± 3 % | |
| P7 | ESP32 | USB-C to the PC (charger / PC port from here on); flash MicroPython, copy `firmware/esp32/`, read `ecp5.idcode()` | `0x41113043` | ID matches | |
| P7a | If P7 fails | ESP32 console on the `TXD0` probe via (`BRINGUP.md` 3.0); `FPGA_DONE` / `FPGA_INITN` / `FLASH_SCK` vias for P8 | | boot messages / config activity seen | |
| P8 | FPGA flash | write the release bitstream to the config flash; unplug, plug, press B0 | | `FPGA_DONE` high without the ESP32 loading anything | |
| P9 | Display and camera | look | | backlight on, live picture | |
| P10 | Buttons and LEDs | B1 toggles the edge view, B2 steps the threshold, D53 / D54 follow the design | | all work | |
| P11 | SD card | `os.listdir('/sd')` after `uftpd.mount()` | | card listed | |
| P12 | Sensors | until the hub CPU exists: an I2C scan on TP8 / TP9 with the FPGA unconfigured (`BRINGUP.md` 6.2). With the hub CPU: its self-test line on the ESP32 | 0x1E 0x29 0x5C 0x68, RTC 0x6F | all answer | |
| P13 | One cell | 18650 in slot 1, USB in | | D2 lights (charging); unplug USB, board stays on | |
| P14 | Slots 2 and 3 | move the cell to slot 2, then 3 (or fit all three on the fixed-cell build) | | D3 / D4 light | |
| P15 | Power off | with the hub CPU: hold B0 2 s | | D11 dark, < 1 mA from the cell | |

Record per board: board number, date, firmware / bitstream versions, the P2-P6 numbers, pass / fail. A failed row:
go to the matching `BRINGUP.md` stage for that board.

## Left out on purpose (validated once in BRINGUP.md)

Rail ripple, the 25 MHz frequency, the cell reverse-polarity test, the lowest working cell voltage, ideal-diode
sharing between cells, charge current, cell-sense divider and NTC voltages, backlight voltages and current, audio
(sample a board per batch), servo outputs, RTC crystal and backup.
