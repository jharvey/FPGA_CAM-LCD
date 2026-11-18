# FPGA I/O remap for the FCL board (camera + LCD)

Camera (J1, through-hole, front layer): the 16 camera signals sit on U1's two outer ball rows (A/B) of the bottom-left edge in J1 column order, so every camera trace routes on the top layer without vias; the camera pixel clock is on the dedicated clock input **PCLKT1_0 (B12)** (one via). LCD (J7, back side): outer three rows of the bottom-right corner in J7 pin order, one dogbone via each, then a back-layer ribbon. Only pin locations changed; the Verilog is untouched. All new balls are general I/O in the 3.3 V banks 0/1/7.

Files: `CameraToTFTSobel_FCL.ice` (Icestudio project with the new pins) and `main_FCL.lpf`. Add clock constraints, e.g. `FREQUENCY PORT "cmos_pclk" 24 MHZ;`, and check nextpnr timing.

| FPGA port | pin name | old ball | new ball |
|---|---|---|---|
| LCD_B0 | gn2 | B10 | C4 |
| LCD_B1 | gp2 | A9 | B4 |
| LCD_B2 | gn3 | C10 | A4 |
| LCD_B3 | gp3 | B9 | C5 |
| LCD_B4 | gn4 | A8 | B5 |
| LCD_B5 | gp4 | A7 | A5 |
| LCD_DE | gp1 | A10 | A3 |
| LCD_G0 | gn5 | B8 | C6 |
| LCD_G1 | gp5 | C8 | B6 |
| LCD_G2 | gn6 | C7 | A6 |
| LCD_G3 | gp6 | C6 | C7 |
| LCD_G4 | gn7 | B6 | A7 |
| LCD_G5 | gp7 | A6 | C8 |
| LCD_HS | gp0 | B11 | C3 |
| LCD_PCLK | gn1 | A11 | B3 |
| LCD_R0 | gn8 | A5 | B8 |
| LCD_R1 | gp8 | A4 | A8 |
| LCD_R2 | gn9 | B1 | C9 |
| LCD_R3 | gp9 | A2 | B9 |
| LCD_R4 | gn10 | B4 | A9 |
| LCD_R5 | gp10 | C4 | C10 |
| LCD_RESET_N | gn11 | E3 | B10 |
| LCD_SPI_CLK | gn12 | F3 | C11 |
| LCD_SPI_CS_N | gp11 | F4 | A10 |
| LCD_SPI_DC | gp12 | G3 | B11 |
| LCD_SPI_MOSI | gn13 | G5 | A11 |
| LCD_VS | gn0 | C11 | A2 |
| cmos_db | gn21 | D17 | A17 |
| cmos_db | gn22 | C15 | B16 |
| cmos_db | gn23 | C17 | B15 |
| cmos_db | gn24 | D16 | A14 |
| cmos_db | gp21 | C18 | B17 |
| cmos_db | gp22 | B15 | A16 |
| cmos_db | gp23 | B17 | A15 |
| cmos_db | gp24 | C16 | A13 |
| cmos_href | gp15 | N17 | B18 |
| cmos_pclk | gp16 | N16 | B12 |
| cmos_pwdn | gp17 | L16 | B13 |
| cmos_rst_n | gn17 | L17 | A12 |
| cmos_scl | gn14 | U17 | B20 |
| cmos_sda | gp14 | U18 | B19 |
| cmos_vsync | gn15 | P16 | A19 |
| cmos_xclk | gn16 | M17 | A18 |

Board-specific: camera PCLK is on J1 pin 7 and PWDN on J1 pin 18 (swapped relative to the original project). The RTC I2C data line FPDI_SDA moved from B19 to C15 to free an outer ball (not part of this FPGA project).

## ESP32 / SD / ADC links (2026-11-08)
These balls are not used by the FPGA design (no `.lpf` change). They were re-ordered on U1's right edge to match the ESP32's new pads. See `ESP32_PINS.md`.

| Net | old ball | new ball |
|---|---|---|
| WIFI_TXD | K4 | L1 |
| WIFI_RXD | K3 | L2 |
| WIFI_GPIO13 (was GPIO40) | N3 | K1 |
| WIFI_GPIO14 (was GPIO41) | E6 | K2 |
| WIFI_GPIO21 (was GPIO1) | E9 | J1 |
| WIFI_GPIO0 | F1 | F1 |
| SD_CD | N5 | N4 |
| SD_D1 | H1 | G3 |
| SD_D0 | J3 | H3 |
| SD_CLK | H2 | J3 |
| SD_CMD | J1 | K3 |
| SD_D3 | K2 | K4 |
| SD_D2 | K1 | N3 |
| WIFI_GPIO47 (ADC CNV, was GPIO9) | L1 | B1 |
| WIFI_GPIO48 (ADC DIN, was GPIO21) | K5 | C1 |
| WIFI_GPIO35 (ADC SCK, was GPIO8) | L2 | D1 |
| WIFI_GPIO36 (ADC SDO, was GPIO6) | N4 | E1 |

2026-11-08 (LCD routing): camera RESET (`cmos_rst_n`, net GN17, J1.17) and PWDN (`cmos_pwdn`, net GP16, J1.18) swapped balls to A12 / B13 so both drop straight to the back layer beside J1 and leave the top layer clear for the LCD ribbon.

2026-11-08 (step 3): ADC SPI moved to U1 outer balls B1 (CNV), C1 (DIN), D1 (SCK), E1 (SDO) facing U21; IMU_INT1 / IMU_INT2 moved from C1 / D1 to F3 / E3 (IMU is top-left, slow signals). Not used by the FPGA design (no .lpf change).

2026-11-08 (step 3, SD shared): FPGA SD balls are D2 U17, D3 U18, CMD R17, CLK T16, D0 U16, D1 R16 (order chosen so the escape lanes do not cross). SD card detect stays on the ESP32 only; M17 is a no-connect. Not used by the current FPGA design (no .lpf change).

2026-11-08 (step 3, closest balls): nine nets moved to the nearest free U1 ball that has a free via spot, all on 3.3 V banks. None are used by the current FPGA design (no .lpf change).

| Net | old ball | new ball | why |
|---|---|---|---|
| IMU_SCL | E7 | P16 (VREF1_3, used as plain I/O; bank 3 needs no VREF) | left edge, faces the IMU in the top-left corner |
| IMU_SDA | D7 | K17 | left edge |
| IMU_INT1 | F3 | K16 | left edge; frees clock-capable F3 |
| SRV_PWM6 | J4 | D17 | bottom-left corner, faces the servo resistors |
| SRV_PWM4 | P4 | D16 | bottom-left corner |
| SRV_PWM2 | P2 | D15 | bottom-left corner |
| SRV_PWM5 | N2 | D14 | bottom-left corner |
| SRV_PWM3 | P3 | D13 | bottom-left corner; frees PLL inputs P3 / P4 |
| WIFI_EN | J5 | N3 | about 4 mm closer to R35 |

The left-edge balls N16, N17, M17 and L17 were left free at first, because the back-side decoupling caps cover every via spot next to them. On 2026-11-12 they were given slow sensor signals (a via can be found when routing, or the caps nudged): **L17** MAG_DRDY (U25 compass), **M17** BARO_INT (U26 barometer), **N16** TOF_XSHUT (U27 distance sensor, FPGA output), **N17** TOF_INT (U27, open-drain with a 10k pull-up R89). None are in the .lpf yet. IMU_INT2, BTN1n, BTN2n and FPDI_SDA stay where they are, because the free balls left are no closer to their targets.

## 2026-11-17 (routing pass 2)

Balls moved while routing the remaining FPGA links. None are in `main_FCL.lpf`, so no FPGA rebuild is needed (but note that the old `.lpf` still names E1, D1 and C1 for another bus). Schematic labels moved with them; the old balls are now no-connects.

| Net | old ball | new ball | why |
|---|---|---|---|
| IMU_INT2 | E3 | N4 | E3 sits inside the 2V5_3V3 In1 island; N4 is in the In1 gap between the +2V5 and 2V5_3V3 islands, next to USER_PROGRAMN (M4). L16 was tried first, but all four of its dog-bone spots are taken |
| BTN1n | E8 | N5 | E8 is inside the 2V5_3V3 island; also moves the button from bank 0 (2V5_3V3) to bank 6 (+3V3) |
| BTN2n | D8 | M5 | same as BTN1n |
| SRV_PWM1 | P1 | C18 | P1 is on the far (right) edge; C18 is the west-most free ball in the bottom-left corner |
| SRV_PWM2 | D15 | D17 | west-to-east ball order now matches R78…R83 left-to-right, so the In1 bundle does not cross |
| SRV_PWM3 | D13 | D16 | as above |
| SRV_PWM4 | D16 | D15 | as above |
| SRV_PWM5 | D14 | D14 | unchanged |
| SRV_PWM6 | D17 | D13 | as above |
| FPDI_SDA | C15 | D12 | beside FPDI_SCL (E12) so the I2C pair runs together, east of the servo bundle |
| SHUTDOWN | G16 | D11 | east of the servo and FPDI lines, toward D15/R13 |
| ADC_DIN | C1 | E1 | U21's ADC pins face away from U1: DIN, SCK and SDO reach them over the top of U21 and CNV around the bottom, so the upper three balls feed the top route in pin order |
| ADC_SCK | D1 | D1 | as above |
| ADC_SDO | E1 | C1 | as above |
| ADC_CNV | B1 | B1 | as above |

Routing notes:
- Sensor, button, servo, FPDI and SHUTDOWN lines leave U1 through a dog-bone via and run on In1, kept out of the +1V1, +2V5, 2V5_3V3 and VSYS fills.
- **ADC:** to make room for ADC_SDO, C72 (U21 VIO decoupling) moved from (148.61, 103.70) to (148.30, 103.06). It is still fed straight from U21.15, and its GND pad, which had no connection before, now has a trace to a GND via at (147.45, 101.30). The unrouted battery-sense parts to its right were then nudged right to open a lane: R25/R24 +0.9 mm, C59 +1.2 mm, C44, C45 and R26/R36 +0.6 mm (R37/R39 stay, R23 is in the way on the back).
- **GP13 (FPGA port `gp13`, to U8.4 / R18) moved H4 → H1.** H4 is three balls deep and inside the 2V5_3V3 In1 island, with no dog-bone site; H1 is a free outer ball in bank 6 (+3V3). **This one is in the FPGA design:** `main_FCL.lpf` (`v5e972b`) and `CameraToTFTSobel_FCL.ice` were updated, so rebuild the bitstream.

## 2026-11-18 (routing pass 3)

| Net | old ball | new ball | why |
|---|---|---|---|
| GP13 | H1 | G16 | H1 has no way out: every layer around it is taken. G16 (PR17C, bank 2, +3V3 like H1's bank 6) is one of only five free balls the router could reach from U8/R18 |

- **GP13 is in the FPGA design** (port `gp13`): `main_FCL.lpf` (`v5e972b`) and `CameraToTFTSobel_FCL.ice` now say G16, so rebuild the bitstream.
- Schematic: the GP13 label moved from U1E pin H1 (usb sheet, now a no-connect) to U1C pin G16 (ram sheet).
- Route: dog-bone via at G16, In1 down the west side of the LCD fan-out, a short B.Cu hop at (114.95-119.25, 104.35-108.65), then In1 to a new via at (114.3, 125.2) beside R18.1. In1 is kept out of the strip that feeds C20.1's +3V3 via.
- **R16** (GN17 pull-up, B side) is flipped end-for-end about its GN17 pad, (123.2, 103.3) -> (122.18, 103.3), so its +3V3 pad is off the 2V5_3V3 island and reaches the +3V3 plane.
- **VBAT3 to R37.1** is a 0.15-0.2 mm sense tap, not a 0.4 mm power trace: it only feeds the 47k/56k divider.
