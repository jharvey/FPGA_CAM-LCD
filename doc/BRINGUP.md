# First power-up and bring-up checklist

For the first boards back from JLC. Work top to bottom: each stage only adds one new thing, so a failure points at
that one thing. Write the measured value in the **Result** column.

Locations are board coordinates in mm from the top-left corner of the PCB (x to the right, y down) as seen from the
**front** (camera side). "back" means the part is on the eye side. All test points are on the back except TP6.

## What you need

- Multimeter, a USB-C meter (shows V and mA), a scope (for the 25 MHz clock and backlight), a lab supply with current
  limit (3.0-4.2 V, for the battery stages), a USB-C PD charger (for the 5 V check), a USB-C cable to a PC.
- One 18650 cell (charged to about 3.7 V) and a cell holder with leads, for the battery stages.
- A microSD card, a CR1225 coin cell (BAT1, RTC backup).
- Optional: a USB-I2C adapter (Bus Pirate, CH341A, etc.) for the sensor stage before the hub CPU exists.
- On the PC: `esptool`, `mpremote`, an FTP client, the MicroPython ESP32-S3 SPIRAM build, and the files in
  `firmware/esp32/` and the FPGA bitstream (`python fpga/build.py`).

## Where things are

| Test point | Net | Location (side) | Expected when on |
|---|---|---|---|
| TP1 | GND | (38.3, 31.1) back | 0 V reference |
| TP2 | GND | (40.7, 5.7) back | 0 V reference |
| TP7 | +5V | (62.6, 36.9) back | 4.5-4.8 V on USB (VBUS minus the D55 Schottky) |
| TP6 | VSYS | (45.8, 71.0) **front** | about +5V on USB; about the highest cell on battery |
| TP3 | +3V3 | (33.2, 7.1) back | 3.33 V (0.6 x (1 + 15k/3.3k)) |
| TP5 | +2V5 | (56.2, 47.8) back | 2.51 V (0.6 x (1 + 15k/4.7k)) |
| TP4 | +1V1 | (50.1, 50.1) back | 1.10 V (0.6 x (1 + 15k/18k)) |
| TP8 / TP9 | IMU_SCL / IMU_SDA | (18.7, 24.5) / (27.8, 29.5) back | 3.3 V idle (R76 / R77 pull-ups) |
| TP10 / TP11 | FPDI_SCL / FPDI_SDA (RTC) | (34.7, 55.5) / (31.5, 57.3) back | 3.3 V idle |
| TP12 / TP13 | WIFI_TXD / WIFI_RXD (ESP32 <-> FPGA UART) | (54.7, 36.5) / (51.9, 36.8) back | 3.3 V idle |

| Part | What | Location (side) |
|---|---|---|
| J17 | USB-C (power, data) | (77.8, 71.9) front, right edge |
| U23 | CH224K, USB-PD sink set to 5 V | (68.5, 73.2) back |
| U3 / U4 / U5 | buck regulators 1V1 / 2V5 / 3V3 (EN = PWREN) | (59.2, 59.8) / (59.3, 55.7) / (69.8, 64.2) front |
| RP1 / RP2 / RP3 | 0 R links regulator -> rail (+1V1 / +2V5 / +3V3) | (54.9, 59.1) / (54.7, 54.4) / (66.2, 64.3) back |
| RV3 / RV2 | bank 0/7 supply select: RV3 fitted = 3.3 V, RV2 must be **empty** | (52.7, 56.0) front / (52.7, 52.9) back |
| D11 | power-hold LED (lights while the rails are on) | (56.7, 72.2) back |
| D2 / D3 / D4 | charge LEDs cells 1 / 2 / 3 | (72.1, 25.6) / (72.0, 37.3) / (71.4, 54.6) back |
| D53 / D54 | FPGA LED0 / LED1 | (62.1, 41.6) / (62.6, 44.9) front |
| Y1 | 25 MHz oscillator (CLK_25MHz) | (59.5, 42.5) back |
| U8, L4, D1 | backlight boost (AP3032), EN = GP13 | (33.2, 70.8), (29.7, 70.8), (38.3, 70.3) front |
| U20 / U17 | VADC 3.3 V LDO / REF3025 2.5 V reference | (66.3, 44.0) back / (66.6, 44.1) front |
| BAT1 | RTC coin cell CR1225 (VBAT) | back |
| B0 / B1 / B2 | power / user 1 / user 2 buttons | (9.0, 4.0) / (16.0, 4.0) / (26.5, 4.0) back |
| B3 / B4 | ESP32 BOOT / RESET (paperclip holes in the front shell) | (80.1, 22.1) / (53.2, 12.0) front |
| J4 | backup JTAG pads (Tag-Connect TC2030) | (44.6, 21.5) front |

### How power-on works (ULX3S circuit)

B0 pulls `PWRBTn` low -> through D16 it pulls `WAKEUPn` low -> Q1 (PNP from VSYS) switches `WKUP` -> D10 / R1 drive
`PWREN` high -> the three bucks start -> +3V3 lights D11, and D11 / R4 then hold `PWREN` high after B0 is released.
The RTC alarm (`WAKEUPn`) can do the same. To switch off, the FPGA drives `SHUTDOWN` (ball D11) high -> D15 -> Q2 pulls
`PWREN` low through R8. B0 also reaches the FPGA (`BTN_PWRn`, ball D6) and, through D28, `FPGA_PROGRAMN`
(a press while on reloads the FPGA, as on the ULX3S).

## Stage 0 - unpowered checks

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 0.1 | Visual | Look for missing / rotated parts, bridges on U9, U21, U23, J17, J7 | nothing odd | |
| 0.2 | Board-variant parts | RV2 empty, RV3 fitted; RP1-RP3 fitted; springs BT13/23/33 fitted only on the fixed-cell build | as listed | |
| 0.3 | No shorts to GND | Ohms from TP1 to TP7, TP6, TP3, TP5, TP4 (both probe polarities) | none near 0 Ω. The core rail TP4 reads lowest; write all five down to compare with the next board | |
| 0.4 | No rail-to-rail short | Ohms TP3-TP5, TP5-TP4, TP6-TP3 | not near 0 Ω | |
| 0.5 | Cells out | No cells, no coin cell for now | | |

If 0.3 shows a short on +1V1 / +2V5 / +3V3: lift RP1 / RP2 / RP3 to tell regulator from load.

## Stage 1 - USB-C power, board still off

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 1.1 | PD asks for 5 V only | USB-C meter between a **PD charger** and J17 | 5 V on VBUS (never 9 / 12 / 15 / 20 V; if it shows more, unplug: U23 CFG1 is wrong) | |
| 1.2 | Input current, off | USB-C meter | a few mA (chargers idle, no cells) | |
| 1.3 | +5V | TP7 | 4.5-4.8 V | |
| 1.4 | VSYS | TP6 (front) | about TP7 minus 0.1 V | |
| 1.5 | Rails off | TP3, TP5, TP4; D11 dark | 0 V (PWREN low until B0) | |
| 1.6 | VADC / REF | U20 output (C69), U17 output (`VREF_SENSE`, R43) | 3.3 V / 2.50 V (these run from VSYS, always on) | |
| 1.7 | Charge LEDs | D2-D4 | undefined with no cells (may flicker): ignore for now | |

## Stage 2 - switch on (B0)

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 2.1 | Press B0 briefly | | D11 lights and stays lit after release | |
| 2.2 | +3V3 | TP3 | 3.30-3.36 V | |
| 2.3 | +2V5 | TP5 | 2.48-2.55 V | |
| 2.4 | +1V1 | TP4 | 1.08-1.12 V | |
| 2.5 | Bank 0/7 supply | `2V5_3V3` at C47 | 3.3 V (RV3) | |
| 2.6 | Current, blank FPGA + ESP32 idle | USB-C meter | record (expect roughly 100-250 mA at 5 V) | |
| 2.7 | Nothing hot | finger / thermal camera on U1, U3-U5, U9, U23 | warm at most | |
| 2.8 | 25 MHz clock | scope on Y1 output (`CLK_25MHz`) | 25.000 MHz, 3.3 V swing | |
| 2.9 | Rail ripple | scope on TP3 / TP4, 20 MHz BW | < 30 mV pk-pk | |
| 2.10 | FPGA not configured yet | `FPGA_DONE` (R32, ball Y3) | low (flash empty) | |
| 2.11 | SD supply | `SD3V3` at C15 | 3.3 V (through R38 0.47 Ω) | |

To switch off before the firmware can: unplug USB (and remove the cell in later stages).

## Stage 3 - ESP32-S3 and the programmer

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 3.1 | USB enumerates | PC device list | Espressif USB JTAG/serial debug unit (303A:1001), a COM / ttyACM port | |
| 3.2 | Enter download mode if needed | hold B3 (BOOT), tap B4 (RESET), release B3 | port re-appears in download mode | |
| 3.3 | Flash MicroPython | `esptool.py --chip esp32s3 erase_flash`, then `write_flash 0 <ESP32_GENERIC_S3-SPIRAM .bin>` | completes, reset, REPL on the port | |
| 3.4 | PSRAM / flash size | REPL: `import esp, gc; esp.flash_size(); gc.mem_free()` | 8 MB flash; more than 2 MB free with PSRAM | |
| 3.5 | Copy esp32ecp5 + FCL files | `mpremote cp firmware/esp32/*.py :` and a `wifiman.conf` with your Wi-Fi | files listed by `mpremote ls` | |
| 3.6 | Wi-Fi + FTP | reset, read the IP in the REPL, `ftp <ip>` | FTP login works | |
| 3.7 | JTAG to the FPGA | REPL: `import ecp5; ecp5.idcode()` | `0x41113043` (LFE5U-85F). If 0 or 0xFFFFFFFF: check JTAG pins / J4 / U1 | |

## Stage 4 - FPGA, LEDs and the display

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 4.1 | Load the video design to SRAM | FTP `put main.bit` (from `python fpga/build.py`) | completes; `FPGA_DONE` goes high | |
| 4.2 | Board stays on | | D11 still lit. If the board switches off when the design loads, `SHUTDOWN` (D11 ball) is floating high: drive it low in the design | |
| 4.3 | Backlight enable | `GP13` (R18 / U8 pin 4) | 3.3 V (the design holds it at 1) | |
| 4.4 | Backlight boost | `LCD_BL_A` at D1 cathode; `LCD_BL_K` at R19 | A: several volts above VSYS (record); K: about 0.2 V (100 mA x 2 Ω) | |
| 4.5 | Backlight current | USB-C meter, before / after 4.1 | rises by roughly 100 mA x V_LED / VSYS / 0.85 | |
| 4.6 | Panel lights | look at the TFT | backlight on, then picture (the panel is initialised over SPI by the design) | |
| 4.7 | Camera clock | J1 pin 8 (`XCLK_J`, after R15) | clock present (record frequency) | |
| 4.8 | Camera picture | | live image on the TFT | |
| 4.9 | B1 | press | toggles raw camera / Sobel edge view | |
| 4.10 | B2 | press several times in edge view | edge sensitivity steps, wraps after about 50 presses | |
| 4.11 | B0 short press | press briefly while on | video design restarts (B0 is its reset; also reloads the FPGA via PROGRAMN) | |
| 4.12 | LEDs | D53 / D54 | follow the design's `led[0]` / `led[1]` | |

## Stage 5 - storage

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 5.1 | SD card | insert card; REPL `import uftpd; uftpd.mount(); import os; os.listdir('/sd')` | card files listed (4-bit SDMMC) | |
| 5.2 | Card detect | REPL `from machine import Pin; Pin(4, Pin.IN).value()` with / without card | changes (R86 pull-up) | |
| 5.3 | Bitstream to config flash | FTP `put main.bit flash@0` (see `firmware/esp32/upstream_docs`) | write + verify OK | |
| 5.4 | Boot from flash | unplug, plug, press B0 | picture appears without the ESP32 loading anything; `FPGA_DONE` high | |

## Stage 6 - sensors and RTC (before the hub CPU exists)

The sensors sit on the FPGA's I2C bus, so test them with an external I2C adapter on TP8 (SCL) / TP9 (SDA) / TP1 (GND)
while the FPGA is **not configured** (unplug and replug, do not load a bitstream; its pins are then high-impedance).

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 6.1 | Bus idle level | TP8, TP9 | 3.3 V | |
| 6.2 | Scan | adapter scan | 0x1E (LIS2MDL), 0x29 (VL53L1X), 0x5C (LPS22DF), 0x68 (ICM-42688-P) | |
| 6.3 | IDs | read WHO_AM_I | ICM 0x75 = 0x47; LIS2MDL 0x4F = 0x40; LPS22DF 0x0F = 0xB4; VL53L1X 0x010F = 0xEA | |
| 6.4 | RTC bus | adapter on TP10 / TP11, scan | 0x6F (MCP7940N) | |
| 6.5 | RTC crystal | after setting ST bit in RTCSEC, read seconds twice | seconds count | |
| 6.6 | RTC backup | fit BAT1, check `VBAT` at C54 | about 3.0 V | |

With the hub CPU built later: the same values come out in `fcl_hub.last` on the ESP32 (heading, tilt, altitude, distance).

## Stage 7 - batteries (one cell, then all three)

Use a lab supply set to 3.7 V, current limit 0.5 A, in place of the first real cell. **USB unplugged** unless the
step says otherwise.

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 7.1 | Reverse protection | supply **reversed** on cell 1 contacts for one second, limit 0.1 A | ~0 mA, nothing warm (Q3 AO3401A) | |
| 7.2 | Cell path | supply correct way on cell 1 | `VBAT1` ≈ 3.7 V; `VBAT_OR` and TP6 (VSYS) ≈ 3.7 V | |
| 7.3 | Power on from battery | press B0 | rails as in stage 2; record supply current | |
| 7.4 | Lowest working voltage | lower the supply in 0.05 V steps | +3V3 stays in regulation down to about 3.4-3.5 V on VSYS (ROADMAP); record where it drops | |
| 7.5 | Ideal-diode OR | supply on cell 1 at 3.7 V and cell 2 at 4.0 V | VSYS follows the higher one; no current from cell 2 into cell 1 | |
| 7.6 | Charging | plug USB, real cell in slot 1 | D2 lights; cell voltage rises toward 4.2 V; charge current at the cell (record; set by R-PROG) | |
| 7.7 | Repeat for cells 2 and 3 | | D3 / D4, same results | |
| 7.8 | USB + cells | all three cells, USB in | VSYS from USB (+5V path, U16) | |
| 7.9 | Cell sense dividers | `VBAT1_SENSE`..`VBAT3_SENSE` at U21 | 0.544 x cell voltage (47k / 56k) | |
| 7.10 | NTCs | `TEMP_BAT_CELL1..3` at U21 | about 1.25 V at 25 C (10k / 10k from 2.5 V) | |

## Stage 8 - audio and the rest

| # | Check | How | Expected | Result |
|---|---|---|---|---|
| 8.1 | Speaker | speaker on J8; REPL: enable `AMP_SD` (GPIO47 high), play a tone over I2S (BCLK 35, WS 36, DOUT 37) | tone heard | |
| 8.2 | Microphone | I2S read on GPIO38 | samples change when you speak | |
| 8.3 | Servo outputs | needs the hub CPU or a test bitstream: 1-2 ms pulse on J_SRV1..6 pin 1 | 50 Hz pulses | |
| 8.4 | Power off | needs `SHUTDOWN` driven high by the FPGA (hub CPU: hold B0 2 s) | D11 goes dark, rails 0 V, < 1 mA from the cell | |

## What is ready to test with, today (2026-11-27)

| Stage | Firmware / file | State |
|---|---|---|
| 0-2 | none | ready |
| 3 | MicroPython + `firmware/esp32/` (esp32ecp5 + FCL pins) | ready, not yet run on hardware |
| 4-5 | `fpga/CameraToTFTSobel_FCL.ice`, `python fpga/build.py` -> `main.bit` | builds, timing met; not run on hardware |
| 6 | external I2C adapter | ready; the hub CPU (`firmware/hub/`) is not built yet |
| 7 | none (meters) | ready; the ADC readings need the hub CPU |
| 8 | MicroPython I2S snippets; hub CPU for servos and power-off | audio ready; servos and soft power-off wait for the hub CPU |

Record anything unexpected in `ROADMAP.md` with the board number and the step.
