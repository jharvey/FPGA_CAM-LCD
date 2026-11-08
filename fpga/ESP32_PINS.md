# ESP32-S3 (U9) ↔ FPGA (U1) ↔ SD / ADC / JTAG pin map (FCL board)

Remapped 2026-11-08 (SD and JTAG order revised the same day to match the routed SD bus) so the ESP32 pads that carry FPGA, SD and JTAG signals face U1, SD1 and J4. The ESP32 is the WROOM-1-N8R2: quad PSRAM, so GPIO35–37 are free. U9 is at (66.0, 12.8) with the antenna up. Its left pad column faces SD1 and J4, and its bottom row faces U1.

The FPGA design (`main_FCL.lpf`) uses none of these balls, so no FPGA rebuild is needed. ESP32 firmware has to use the GPIO numbers below. UART, SDMMC and SPI all go through the S3 GPIO matrix, so any GPIO works.

Nets that moved were renamed to their new GPIO number: `WIFI_GPIO40→13`, `41→14`, `1→21`, `9→47`, `21→48`, `8→35`, `6→36`.

| Net | Function | ESP32 pad | ESP32 GPIO | FPGA ball (old → new) | Other end |
|---|---|---|---|---|---|
| SD_CD | card detect | 4 | 4 | N5 → N4 | SD1.10, R86 pull-up |
| SD_D2 | SD DAT2 | 5 | 5 | K1 → N3 | SD1.1 |
| SD_D3 | SD DAT3/CD | 6 | 6 | K2 → K4 | SD1.2 |
| SD_CMD | SD CMD | 7 | 7 | J1 → K3 | SD1.3 |
| SD_CLK | SD CLK | 8 | 15 | H2 → J3 | SD1.5 |
| SD_D0 | SD DAT0 | 9 | 16 | J3 → H3 | SD1.7 |
| SD_D1 | SD DAT1 | 10 | 17 | H1 → G3 | SD1.8 |
| JTAG_TDO | FPGA JTAG | 11 | 18 | V4 (fixed) | J4.6 |
| JTAG_TMS | FPGA JTAG | 12 | 8 | U5 (fixed) | J4.5 |
| JTAG_TCK | FPGA JTAG | 17 | 9 | T5 (fixed) | J4.4 |
| JTAG_TDI | FPGA JTAG | 18 | 10 | R5 (fixed) | J4.3 |
| WIFI_TXD | UART ESP→FPGA | 19 | 11 | K4 → L1 | |
| WIFI_RXD | UART FPGA→ESP | 20 | 12 | K3 → L2 | |
| WIFI_GPIO13 | spare link (was GPIO40) | 21 | 13 | N3 → K1 | |
| WIFI_GPIO14 | spare link (was GPIO41) | 22 | 14 | E6 → K2 | |
| WIFI_GPIO21 | spare link (was GPIO1) | 23 | 21 | E9 → J1 | |
| WIFI_GPIO0 | BOOT strap / link | 27 | 0 | F1 (unchanged) | B3, R56 |

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
- **SD (routed, no vias):** the seven lines leave the top of SD1 at 0.35 mm pitch (card detect wraps over the top as the outermost line). They turn down tight against SD1's right edge, about 1.5 mm into the antenna band (this board's copy of the U9 keep-out starts at x 43.6), then fan straight into ESP32 pads 4–10. **The branch to U1 is not routed yet.**
- **JTAG (routed, hand-planned):** J4 (TC2030) escapes through the gaps between its leg holes: TDO/TMS on the right, TCK on top, TDI on the bottom, 3V3/GND on the left to vias. TDO/TMS run on F into ESP32 pads 11/12, each with one via to a B lane into U1 (TDO through a new dogbone via at (51.1, 31.1)). TCK runs on B into U1 and under the USB pair to pad 17. TDI runs on F with a via into U1, then drops to B under the USB pair to pad 18.
- **FPGA links:** a front-layer ribbon from the ESP32 bottom-row pads 19–23 to U1's outer balls L1, L2, K1, K2 and J1, in order. GPIO0 runs from pad 27 to F1.
- **ADC (U21) is FPGA-only (owner decision 2026-11-08):** nets renamed ADC_CNV / ADC_DIN / ADC_SCK / ADC_SDO on U1 balls B1 / C1 / D1 / E1, routed. The ESP32 gets readings from the FPGA over the UART link; ESP32 pads 24/25/28/29 are now unconnected.

J4 is a Tag-Connect TC2030 pad footprint (legged version, no part fitted), used only as a backup JTAG port. Pin numbers are unchanged: 1 GND, 2 3V3, 3 TDI, 4 TCK, 5 TMS, 6 TDO. A TC2030-IDC cable maps them 1:1 onto a 2×3 2.54 mm IDC plug.
