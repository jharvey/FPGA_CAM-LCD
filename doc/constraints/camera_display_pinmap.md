# Camera + display FPGA pin map (monocular-strip)

Generated from the KiCad netlist (`FCL.kicad_sch`, sheets `display`, `camera`, `fpga-io`)
and `doc/ECP5U85Pinout.csv` (CABGA381 column). Use this when writing the `.lpf` for the
monocular; the legacy `ulx3s_v20.lpf` names (`gp[]`/`gn[]`) still match the net names.

All banks used here (0, 1, 2, 3, 7) run at **3.3 V**:
banks 1/2/3 from `+3V3`; banks 0/7 from `2V5_3V3`, set to 3.3 V by RV3 (RV2 is DNP).
Use `IO_TYPE=LVCMOS33` for every pin below.

## Display - J7 (NHD-2.1-480480AF-ASXP, ST7701S)

Interface: RGB666 parallel + 3-wire/8-bit SPI for init (IM[2:0] = 001, DCX used).
The panel must be initialised over SPI before RGB pixel data is accepted.

| Conn pin | Signal | Net | ECP5 ball | Site | Bank | Dual function |
|---|---|---|---|---|---|---|
| 11 | LCD_VS | `GN0` | C11 | PT65B | 0 | PCLKC0_0 |
| 12 | LCD_HS | `GP0` | B11 | PT65A | 0 | PCLKT0_0 |
| 13 | LCD_PCLK | `GN1` | A11 | PT63B | 0 | PCLKC0_1 |
| 14 | LCD_DE | `GP1` | A10 | PT63A | 0 | PCLKT0_1 |
| 15 | LCD_B0 | `GN2` | B10 | PT60B | 0 | GR_PCLK0_0 |
| 16 | LCD_B1 | `GP2` | A9 | PT60A | 0 | GR_PCLK0_1 |
| 17 | LCD_B2 | `GN3` | C10 | PT58B | 0 | - |
| 18 | LCD_B3 | `GP3` | B9 | PT58A | 0 | - |
| 19 | LCD_B4 | `GN4` | A8 | PT18B | 0 | - |
| 20 | LCD_B5 | `GP4` | A7 | PT18A | 0 | - |
| 21 | LCD_G0 | `GN5` | B8 | PT15B | 0 | - |
| 22 | LCD_G1 | `GP5` | C8 | PT15A | 0 | - |
| 23 | LCD_G2 | `GN6` | C7 | PT11B | 0 | - |
| 24 | LCD_G3 | `GP6` | C6 | PT11A | 0 | - |
| 25 | LCD_G4 | `GN7` | B6 | PT4B | 0 | ULC_GPLL1C_IN |
| 26 | LCD_G5 | `GP7` | A6 | PT4A | 0 | ULC_GPLL1T_IN |
| 27 | LCD_R0 | `GN8` | A5 | PL11B | 7 | ULC_GPLL0C_IN |
| 28 | LCD_R1 | `GP8` | A4 | PL11A | 7 | ULC_GPLL0T_IN |
| 29 | LCD_R2 | `GN9` | B1 | PL35B | 7 | - |
| 30 | LCD_R3 | `GP9` | A2 | PL35A | 7 | - |
| 31 | LCD_R4 | `GN10` | B4 | PL14B | 7 | - |
| 32 | LCD_R5 | `GP10` | C4 | PL14A | 7 | - |
| 33 | LCD_RESETn | `GN11` | E3 | PL20B | 7 | - |
| 34 | LCD_CS | `GP11` | F4 | PL20A | 7 | - |
| 35 | LCD_SCK | `GN12` | F3 | PL44B | 7 | PCLKC7_1 |
| 36 | LCD_DC | `GP12` | G3 | PL44A | 7 | PCLKT7_1 |
| 37 | LCD_MOSI (SDA) | `GN13` | G5 | PL41B | 7 | - |
| - | LCD_BL_PWM (U8 CTRL) | `GP13` | H4 | PL41A | 7 | GR_PCLK7_1 |

Notes
- `GN12` / `GP12` (LCD_SCK / LCD_DC) are also wired to ESP32 IO32 / IO33. ESP32 firmware must
  leave those pins as inputs (Hi-Z). `GN13` (ESP32 IO39) and `GP13` (ESP32 IO36) are input-only on the ESP32.
- `GP13` has a 100 k pull-down (R18): backlight is off while the FPGA is unconfigured.
- Backlight current is set in hardware (R19 2R0 -> 100 mA); `GP13` is enable / PWM dimming.
- J2 (legacy 2x20 header, DNP) also sits on all `GN0..13` / `GP0..13` nets.

## Camera - J1 (OV7670 2x9 module)

| Conn pin | Signal | Net | ECP5 ball | Site | Bank | Dual function |
|---|---|---|---|---|---|---|
| 3 | CAM_SIOC | `GN14` | U17 | PR92B | 3 | - |
| 4 | CAM_SIOD | `GP14` | U18 | PR92A | 3 | - |
| 5 | CAM_VSYNC | `GN15` | P16 | PR56B | 3 | VREF1_3 |
| 6 | CAM_HREF | `GP15` | N17 | PR56A | 3 | - |
| 7 | CAM_PCLK | `GP17` | L16 | PR50A | 3 | GR_PCLK3_0 |
| 8 | CAM_XCLK (via R15 33R) | `CAM_XCLK` | M17 | PR53B | 3 | - |
| 9 | CAM_D7 | `GN21` | D17 | PR11B | 2 | URC_GPLL0C_IN |
| 10 | CAM_D6 | `GP21` | C18 | PR11A | 2 | URC_GPLL0T_IN |
| 11 | CAM_D5 | `GN22` | C15 | PT105B | 1 | - |
| 12 | CAM_D4 | `GP22` | B15 | PT105A | 1 | - |
| 13 | CAM_D3 | `GN23` | C17 | PT114B | 1 | - |
| 14 | CAM_D2 | `GP23` | B17 | PT114A | 1 | - |
| 15 | CAM_D1 | `GN24` | D16 | PT112B | 1 | - |
| 16 | CAM_D0 | `GP24` | C16 | PT112A | 1 | - |
| 17 | CAM_RESETn | `GN17` | L17 | PR50B | 3 | - |
| 18 | CAM_PWDN | `GP16` | N16 | PR53A | 3 | - |

Notes
- SCCB pull-ups: R7 / R14 4.7 k to +3V3. CAM_RESETn pulled up (R16 10 k), CAM_PWDN has R17 10 k.
- CAM_PCLK is on GR_PCLK3_0 (L16), a global-clock-capable input. CAM_PWDN moved to N16.
  (Swapped from the original ULX3S `gp16`/`gp17` assignment: in an old `ulx3s_v20.lpf`,
  `gp[16]` is now PWDN and `gp[17]` is PCLK.)
- J6 (legacy 2x20 header, DNP) also sits on every camera net.
- Camera data spans banks 1, 2 and 3 (right-hand side of the BGA); display uses banks 0 and 7
  (top / left). This favours display on the left, camera on the right of the FPGA in placement.

## User I/O (fpga-io sheet)

| Part | Signal | Net | ECP5 ball | Site | Bank | Polarity |
|---|---|---|---|---|---|---|
| B1 | Button 1 | `BTN1n` | E8 | PT13A | 0 | active-low, 10 k pull-up (R67) |
| B2 | Button 2 | `BTN2n` | D8 | PT13B | 0 | active-low, 10 k pull-up (R68) |
| D53 | Status LED 0 | `LED0` | B2 | PL35C | 7 | active-high, 1 k (R69) |
| D54 | Status LED 1 | `LED1` | C2 | PL35D | 7 | active-high, 1 k (R70) |

B0 (power button, `BTN_PWRn`) stays on the power path. Debounce the buttons in FPGA logic.

## IMU (imu sheet, U22 ICM-42688-P)

| IMU pin | Net | ECP5 ball | Site | Bank | Notes |
|---|---|---|---|---|---|
| 13 AP_SCL | `IMU_SCL` | E7 | PT9A | 0 | I²C clock, 4.7 k pull-up (R76), up to 1 MHz |
| 14 AP_SDA | `IMU_SDA` | D7 | PT9B | 0 | I²C data, 4.7 k pull-up (R77) |
| 4 INT1 | `IMU_INT1` | C1 | PL38A | 7 | configure push-pull |
| 9 INT2/FSYNC | `IMU_INT2` | D1 | PL38B | 7 | INT2 or FSYNC input (camera frame sync) |

I²C address 0x68 (AP_AD0 = GND); AP_CS tied to VDDIO selects I²C. Separate from the RTC bus (`FPDI_SCL`/`FPDI_SDA`, E12/B19).

## RC servo headers (servo sheet, all DNP)

| Header | Net | ECP5 ball | Bank | Notes |
|---|---|---|---|---|
| J_SRV1 | `SRV_PWM1` | P1 | 6 | 1 k series (R78) |
| J_SRV2 | `SRV_PWM2` | P2 | 6 | 1 k series (R79) |
| J_SRV3 | `SRV_PWM3` | P3 | 6 | 1 k series (R80) |
| J_SRV4 | `SRV_PWM4` | P4 | 6 | 1 k series (R81) |
| J_SRV5 | `SRV_PWM5` | N2 | 6 | 1 k series (R82) |
| J_SRV6 | `SRV_PWM6` | J4 | 6 | 1 k series (R83) |

Header pinout: 1 Signal (1–2 ms pulse, 3.3 V), 2 `SERVO_V` (source not yet chosen), 3 GND. Use `IO_TYPE=LVCMOS33`.
