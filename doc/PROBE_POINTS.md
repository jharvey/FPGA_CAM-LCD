# Probe points on the back (bare-copper vias)

Added 2026-11-27: 57 points in all. Each point is a via whose **back** side has no solder mask, so the copper ring is exposed: touch it
with a scope probe tip, or solder a thin wire (30 AWG / 0.1-0.25 mm wire-wrap) to it. The front side stays covered.
Map: `doc/probe_points.png` (drawn as seen from the back). Positions below are board coordinates seen from the front,
as in `BRINGUP.md`; on the back, mirror x (85 - x).

The FPGA vias are small (0.45 mm ring, 0.2 mm hole) and sit between the balls: use a sharp probe tip or a fine wire and
a fine soldering tip. The new ESP32 and net vias are 0.6 mm (0.3 mm hole); uncovered existing vias keep their size
(0.45 or 0.6 mm).

## Spare FPGA balls (U1), dog-bone via next to the ball

These balls are not used by any design yet. Add them to a design's `.lpf` to use them as scope outputs, debug signals or
future expansion. Only 10 of the 45 spare balls had room: the others are boxed in by existing routing or sit under
decoupling capacitors on the back.

| Ball | Function | Via (x, y) |
|---|---|---|
| C13 | PT78B (bank 0) | (43.1, 43.1) |
| E13 | PT80B (bank 0) | (43.9, 42.3) |
| D7 | PT9B (bank 0) | (48.7, 43.1) |
| D5 | PL17B (bank 7) | (50.3, 43.1) |
| J3 | GR_PCLK6_1 (bank 6, global clock input) | (51.1, 38.3) |
| J4 | GR_PCLK6_0 (bank 6, global clock input) | (50.3, 38.3) |
| J5 | PL50B (bank 6) | (49.5, 38.3) |
| K4 | PL56A (bank 6) | (50.3, 37.5) |
| P3 | GPLL0T_IN (bank 6, PLL clock input) | (51.1, 34.3) |
| R3 | DOUT / CSOn (configuration pin; a user I/O after configuration) | (51.9, 33.5) |

J3 / J4 / P3 can take an external clock into the FPGA's clock network. Check the bank's I/O voltage in
`fpga/IO_REMAP.md` before driving a ball from outside.

## Spare ESP32-S3 pins (U9), short stub to a via beside the module

| GPIO | Use | Via (x, y) |
|---|---|---|
| TXD0 (GPIO43) | ESP32 boot / MicroPython console UART TX (115200) | (77.25, 11.3) |
| RXD0 (GPIO44) | console UART RX | (77.25, 12.57) |
| IO1 | free (`jtagpin.py` uses it as the activity LED pin) | (76.8, 8.35) |
| IO2 | free (`jtagpin.py` "tcknc") | (76.55, 10.03) |
| IO39, IO40, IO41, IO42 | free (also the ESP32's own JTAG pins MTCK / MTDO / MTDI / MTMS, if eFuse-selected) | (76.64, 18.45) / (76.3, 16.38) / (76.3, 15.11) / (76.3, 13.84) |
| IO46 | free after boot; **strapping pin**: do not pull it high while the ESP32 resets | (60.28, 26.95) |

No room for IO3, IO45, IO48 (IO3 / IO45 are strapping pins anyway). A 3.3 V USB-serial adapter on TXD0 / RXD0 and a
GND (TP2) shows the ESP32's boot messages even when its USB is not working.

## Existing nets

| Net | What it shows | Via (x, y) |
|---|---|---|
| CLK_25MHz | the 25 MHz oscillator Y1 into the FPGA | (52.65, 40.65) |
| PWREN | regulator enable (high = rails on) | (60.5, 62.3), new via next to U3 |
| SHUTDOWN | FPGA power-off request (high = switch off) | (53.5, 62.15) |
| VBAT_OR | the battery side of the power path (highest cell) | (67.65, 60.95) |
| WIFIEN | ESP32 enable / reset (low = held in reset) | (54.6, 14.75) |

More signals (existing vias uncovered on the back, two new vias where none was free):

| Net | What it shows | Via (x, y) |
|---|---|---|
| PWRBTn | power button B0 (low = pressed) | (29.2, 47.5) |
| WAKEUPn | wake request into Q1 (B0 or RTC alarm, low = wake) | (40.1, 61.95) |
| VBUS_C | USB-C VBUS before the input diode | (72.3, 69.45) |
| VBAT1 | cell 1 after its reverse-protection FET | (65.6, 39.75) |
| VBAT3 | cell 3 after its reverse-protection FET | (73.75, 52.25) |
| CHG1_CHRGn | charger 1 status (low = charging) | (67.05, 27.15) |
| CHG2_CHRGn | charger 2 status | (71.2, 41.1) |
| CHG3_CHRGn | charger 3 status | (72.2, 59.7) |
| PROG3 | charger 3 current monitor (1.0 V = full set current) | (77.55, 59.14) new via next to U15 |
| SD3V3 | SD card supply | (34.74, 5.26) new via next to SD1 |
| LCD_BL_K | backlight LED return (100 mA x 2 Ω = 0.2 V) | (40.55, 71.5) |
| GP13 | backlight enable (U8 EN) | (41.25, 53.15) |
| FPGA_DONE | FPGA configured (high) | (45.6, 27.7) |
| FPGA_INITN | FPGA init / config error (low = error) | (51.6, 29.2) |
| FPGA_PROGRAMN | FPGA reload (low pulse) | (27.05, 17.6) |
| FLASH_SCK | config flash SPI clock | (51.85, 31.95) |
| FLASH_nCS | config flash chip select | (60.35, 28.6) |
| FLASH_MOSI | config flash data in | (52.65, 30.35) |
| FLASH_MISO | config flash data out | (56.15, 28.15) |
| ADC_SDO | ADC data out (U21 to FPGA) | (69.83, 48.71) |
| ADC_DIN | ADC data in (FPGA to U21) | (54.25, 41.6) |
| SD_CLK | SD card clock | (36.3, 3.25) |
| SD_CMD | SD card command | (39.9, 33.5) |
| SD_D0 | SD card data 0 | (38.5, 3.25) |
| I2S_BCLK | audio bit clock | (52.0, 23.7) |
| I2S_WS | audio word select | (49.25, 22.15) |
| I2S_SPK | audio data to the amplifier | (58.5, 22.25) |
| I2S_MIC | audio data from the microphone | (19.7, 27.6) |
| AMP_SD | amplifier enable (high = on) | (21.8, 26.6) |
| IMU_INT1 | IMU interrupt 1 | (14.95, 17.2) |
| TOF_INT | distance sensor interrupt | (30.7, 30.65) |
| MAG_DRDY | magnetometer data ready | (39.9, 36.7) |
| BARO_INT | barometer interrupt | (18.0, 14.8) |

No free via (all under parts on the back, no room for a new one): HOLD, VBAT2, PROG1, PROG2, VADC, VREF_SENSE, PD_CC1,
ADC_SCK, ADC_CNV; measure those at their parts as in `BRINGUP.md`. Left out on purpose: the backlight boost switch node
and the SDRAM clock (a new stub there would add ringing / noise).

For a scope, ground the probe with a short spring to the nearest GND test point (TP1 near U1, TP2 near the top edge).

## Board checks

KiCad DRC after the change: 0 errors, 0 unconnected. New warnings only: 22 "via dangling" (the spare-pin vias and the two new
net vias connect on one layer by design) and 16 "silk over copper" (silkscreen lines crossing a bare via ring; the fab clips silkscreen
off exposed copper).
