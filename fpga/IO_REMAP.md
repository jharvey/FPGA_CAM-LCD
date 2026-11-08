# FPGA I/O remap for the FCL board (camera + LCD)

The camera (J1) and LCD (J7) signals were moved to U1 balls on the edge facing each connector, in connector pin order, so both buses route as parallel ribbons without crossings. Only pin locations changed; the Verilog is untouched. All new balls are general I/O in the same 3.3 V banks (0/1/7); the camera pixel clock moved to the dedicated clock input **PCLKT1_0 (B12)**.

Files: `CameraToTFTSobel_FCL.ice` (Icestudio project with the new pins) and `main_FCL.lpf` (the matching constraints). Add clock constraints in your build, e.g. `FREQUENCY PORT "cmos_pclk" 24 MHZ;`, and check nextpnr timing.

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
| cmos_db | gn21 | D17 | B17 |
| cmos_db | gn22 | C15 | A16 |
| cmos_db | gn23 | C17 | A15 |
| cmos_db | gn24 | D16 | A14 |
| cmos_db | gp21 | C18 | B16 |
| cmos_db | gp23 | B17 | C15 |
| cmos_db | gp24 | C16 | A13 |
| cmos_href | gp15 | N17 | A18 |
| cmos_pclk | gp16 | N16 | B12 |
| cmos_pwdn | gp17 | L16 | A12 |
| cmos_rst_n | gn17 | L17 | B13 |
| cmos_scl | gn14 | U17 | B20 |
| cmos_sda | gp14 | U18 | A19 |
| cmos_vsync | gn15 | P16 | B18 |
| cmos_xclk | gn16 | M17 | A17 |

Board-specific (already in the FCL schematic before this remap): camera PCLK is on J1 pin 7 and PWDN on J1 pin 18 (swapped relative to the original project, PCLK on a clock-capable pin).
