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
| cmos_pwdn | gp17 | L16 | A12 |
| cmos_rst_n | gn17 | L17 | B13 |
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
| SD_D1 | H1 | N3 |
| SD_D0 | J3 | K4 |
| SD_CLK | H2 | K3 |
| SD_CMD | J1 | J3 |
| SD_D3 | K2 | H3 |
| SD_D2 | K1 | G3 |
| WIFI_GPIO47 (ADC CNV, was GPIO9) | L1 | F4 |
| WIFI_GPIO48 (ADC DIN, was GPIO21) | K5 | F3 |
| WIFI_GPIO35 (ADC SCK, was GPIO8) | L2 | E4 |
| WIFI_GPIO36 (ADC SDO, was GPIO6) | N4 | E3 |
