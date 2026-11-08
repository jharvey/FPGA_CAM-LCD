# ESP32-S3 (U9) ↔ FPGA (U1) ↔ SD / ADC / JTAG pin map (FCL board)

Remapped 2026-11-08 so the ESP32 pads that carry FPGA, SD and JTAG signals face U1, SD1 and J4. The ESP32 is the WROOM-1-N8R2: quad PSRAM, so GPIO35–37 are free. U9 is at (66.0, 12.8) with the antenna up. Its left pad column faces SD1 and J4, and its bottom row faces U1.

The FPGA design (`main_FCL.lpf`) uses none of these balls, so no FPGA rebuild is needed. ESP32 firmware has to use the GPIO numbers below. UART, SDMMC and SPI all go through the S3 GPIO matrix, so any GPIO works.

Nets that moved were renamed to their new GPIO number: `WIFI_GPIO40→13`, `41→14`, `1→21`, `9→47`, `21→48`, `8→35`, `6→36`.

| Net | Function | ESP32 pad | ESP32 GPIO | FPGA ball (old → new) | Other end |
|---|---|---|---|---|---|
| SD_D2 | SD DAT2 | 4 | 4 | K1 → G3 | SD1.1 |
| SD_D3 | SD DAT3/CD | 5 | 5 | K2 → H3 | SD1.2 |
| SD_CMD | SD CMD | 6 | 6 | J1 → J3 | SD1.3 |
| SD_CLK | SD CLK | 7 | 7 | H2 → K3 | SD1.5 |
| SD_D0 | SD DAT0 | 8 | 15 | J3 → K4 | SD1.7 |
| SD_D1 | SD DAT1 | 9 | 16 | H1 → N3 | SD1.8 |
| SD_CD | card detect | 10 | 17 | N5 → N4 | SD1.10, R86 pull-up |
| JTAG_TMS | FPGA JTAG | 11 | 18 | U5 (fixed) | J4.5 |
| JTAG_TDO | FPGA JTAG | 12 | 8 | V4 (fixed) | J4.6 |
| JTAG_TCK | FPGA JTAG | 17 | 9 | T5 (fixed) | J4.4 |
| JTAG_TDI | FPGA JTAG | 18 | 10 | R5 (fixed) | J4.3 |
| WIFI_TXD | UART ESP→FPGA | 19 | 11 | K4 → L1 | |
| WIFI_RXD | UART FPGA→ESP | 20 | 12 | K3 → L2 | |
| WIFI_GPIO13 | spare link (was GPIO40) | 21 | 13 | N3 → K1 | |
| WIFI_GPIO14 | spare link (was GPIO41) | 22 | 14 | E6 → K2 | |
| WIFI_GPIO21 | spare link (was GPIO1) | 23 | 21 | E9 → J1 | |
| WIFI_GPIO47 | ADC CNV (was GPIO9) | 24 | 47 | L1 → F4 | U21.11 |
| WIFI_GPIO48 | ADC DIN (was GPIO21) | 25 | 48 | K5 → F3 | U21.12 |
| WIFI_GPIO0 | BOOT strap / link | 27 | 0 | F1 (unchanged) | B3, R56 |
| WIFI_GPIO35 | ADC SCK (was GPIO8) | 28 | 35 | L2 → E4 | U21.13 |
| WIFI_GPIO36 | ADC SDO (was GPIO6) | 29 | 36 | N4 → E3 | U21.14 |

**Unchanged:** EN (pad 3, `WIFIEN`) and USB D−/D+ (pads 13/14, GPIO19/20).

**Left unconnected:**
- Strapping pins GPIO3, GPIO45 and GPIO46 (pads 15, 26, 16).
- GPIO37–42 (pads 30–35), which keeps the ESP32's own JTAG (39–42) free.
- UART0 RXD0/TXD0 (pads 36/37).
- GPIO1/GPIO2 (pads 39/38).

**Notes:**
- **UART0 no longer reaches the FPGA.** The FPGA link is now a matrix-assigned UART on GPIO11/12. ROM boot messages and flashing use the S3's native USB (USB-Serial/JTAG), which reaches the USB-C port through U24.
- **ADC SPI order** at U21 (left to right on its top edge) is CNV, DIN, SCK, SDO, which is GPIO47, 48, 35, 36.
- **SD1 needs only 3.3 V I/O,** with SDMMC 4-bit available on GPIO4–7/15/16.

## Routing intent
- **SD:** a via above each SD1 pad, then the back layer to the ESP32 left column (pads 4–10, in pad order) and on to U1's col-3/4 balls (rows N–G) through dogbones.
- **JTAG:** J4 to the ESP32 pads 11/12 (left column) and 17/18 (bottom row), and J4 down to U1's dedicated JTAG balls.
- **FPGA links:** a front-layer ribbon from the ESP32 bottom-row pads 19–23 to U1's outer balls L1, L2, K1, K2 and J1, in order. GPIO0 runs from pad 27 to F1.
- **ADC SPI:** back layer, from pads 24, 25, 28 and 29 past U1's col-3/4 balls F4, F3, E4 and E3 (dogbones) down to U21, which is also on the back.
