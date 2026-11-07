# Monocular FPGA Vision Device – Roadmap

**Repo**: https://github.com/jharvey/FPGA_CAM-LCD  
**Branch**: `monocular-strip`  
**Base**: ULX3S open hardware (emard)  
**Goal**: Single-board monocular with ECP5 + OV7670 + Newhaven 2.1" TFT + 3×18650 + USB charging + WiFi + SD

---

## Current status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Architecture decisions locked | Done |
| 1 | Branch created, cleanup | Done |
| 2 | Power input redesign (3×18650 + monitoring) | **Done** – schematic frozen (CE drive later) |
| 2b | USB-C 5 V PD trigger | **Done** – CH224K 5 V-only sink on the USB-C port (schematic) |
| 2c | Single USB-C (power + SD + programming) | **Done** – ESP32-S3 native USB, USBLC6 ESD, FTDI/micro-B fallback DNP (schematic) |
| 3 | Camera + display connectors / sheets | **Done** – schematic frozen |
| – | **Schematic freeze** | **Frozen** – ERC fully classified, see `doc/constraints/schematic_freeze.md` |
| 3b | IMU (6-axis) | **Done** – ICM-42688-P on I²C to FPGA (schematic) |
| 3c | RC servo headers | **Done (DNP)** – 6× 1x3 headers on `servo` sheet; SERVO_V source open |
| 4 | PCB mechanical outline (monocular form) | Pending |
| 5 | BOM / JLCPCB / first prototype | Pending |

---

## Decisions (locked)

- Full single PCB (not shield)
- Keep ECP5-85F, SDRAM, flash, WiFi, SD card
- **One USB-C port** for power/charging, SD card (USB MSC) and programming; the ESP32-S3 (native USB) is the USB device and the ECP5 programmer (Phase 2c). FTDI / micro-B kept only as DNP fallback
- Remove GPDI, large GPIO headers, audio
- 3 independent 18650 cells with ideal-diode OR-ing (LM66100), hot-swap capable
- Cell interface: PCB-mounted Keystone-style contacts per cell – positive button **MY-18650-04-J (LCSC C19184125)**, negative spring **MY-18650-05-J (LCSC C19184124)** (MYOUNG); replaces the JST-PH placeholders
- Per-cell reverse-polarity protection (AO3401A) + TP4056 chargers
- **8-channel ADC**: AD7689 (16-bit, SPI) replaced ADS1115; absolute 2.5 V reference so measurements are non-ratiometric
- ADC channels used for: per-cell voltages, NTC / temperature, +V / VSYS rail sense, and spare channels
- ADC VDD from a small always-on 3.3 V LDO (XC6206 → VADC) fed from VSYS; ADC VIO from +3V3 (matches ESP32 SPI levels)
- ST pins of all LM66100s tied to GND through 0 Ω links (removable later)
- VSYS = OR of (VBAT_OR + USB 5 V)
- Soft-shutdown path (Q2 / SHUT) retained
- Individual cell enable/control (CE pins) planned so the most-depleted cell can be consumed first (firmware-driven, later)
- Bulk capacitance after ideal-diode OR-ing for contact bounce / vibration
- Optional later boost stage to recover the bottom ~5–15 % capacity once cells fall below ~3.5 V
- Camera: OV7670 parallel + SCCB
- Display: NHD-2.1-480480AF-ASXP (40-pin FFC, RGB + SPI)
- Case: 3D-printed first → metal later

### Power / charging evolution
- **Near-term (done, Phase 2b)**: USB-C PD sink / trigger **WCH CH224K (LCSC C970725)** fixed to request **5 V only** on a new USB-C charge port. Keeps existing TP4056 linear chargers.
- **Longer-term**: Evaluate higher-voltage / higher-wattage PD path (9–20 V) together with switching chargers or a multi-cell charger IC for significantly higher total charge power.

### Sensors
- IMU added now (Phase 3b): TDK InvenSense **ICM-42688-P**, LCSC **C1850418** (JLCPCB extended part), I²C to the FPGA. See Phase 3b.

---

## Phase details

### Phase 1 – Branch & cleanup (NOW)
- [x] Create `monocular-strip` branch
- [x] Update `.gitignore`
- [x] Delete unused sheets: gpdi, gpio, analog, serdes (optionally blinkey)
- [x] Remove corresponding hierarchical blocks from root sheet
- [x] Commit: "strip unused ULX3S sheets for monocular"

### Phase 2 – Power input redesign
- [x] Replace single-cell input with 3×18650 paths
- [x] Per-cell: AO3401A reverse protection, TP4056 charger, LM66100 ideal diode
- [x] Cell connection changed from JST-PH (J8/J9/J10, **removed**) to PCB spring/button contacts, one pair per cell:
  | Cell | Positive button → `CELLn_RAW` (AO3401A drain) | Negative spring → GND |
  |---|---|---|
  | 1 | BT11 MY-18650-04-J (LCSC **C19184125**) | BT12 MY-18650-05-J (LCSC **C19184124**) |
  | 2 | BT21 MY-18650-04-J (C19184125) | BT22 MY-18650-05-J (C19184124) |
  | 3 | BT31 MY-18650-04-J (C19184125) | BT32 MY-18650-05-J (C19184124) |

  AO3401A / TP4056 / LM66100 path unchanged. Note on the power sheet: the contacts are for a plastic battery bay that provides mechanical retention and cell-length tolerance.
  - [ ] Phase 4: create/import footprints for BT11–BT32 (LCSC lists them as "SMT" in the title but "TH" in the attributes – confirm from the datasheet / EasyEDA model) and define the bay geometry (contact spacing for 65 mm cells + spring travel).
- [x] VBAT_OR + USB → VSYS via additional LM66100s
- [x] ~~ADS1115 (0x48) on WIFI_GPIO21/22~~ – superseded by AD7689 (below)
- [x] Always-on 3.3 V LDO from VSYS for the ADC (U20 XC6206 → VADC)
- [x] ST pins of all five LM66100s linked to GND via 0 Ω (R46, R47, R48, R51, R55)
- [x] TLV62569 inputs and wake circuit moved to VSYS
- [x] LCD backlight boost input renamed to VSYS
- [x] **Replace ADS1115 with 8-channel ADC** – U21 AD7689BCPZ, SPI to ESP32: SDO=WIFI_GPIO19, DIN=WIFI_GPIO21, SCK=WIFI_GPIO22, CNV=WIFI_GPIO26 (renumbered for the ESP32-S3 in Phase 2c: SDO=WIFI_GPIO6, DIN=WIFI_GPIO21, SCK=WIFI_GPIO8, CNV=WIFI_GPIO9)
  - IN0–IN2: VBAT1–3 via 47 k / 56 k dividers (4.2 V → 2.28 V), 100 nF filter caps
  - IN3: TEMP_BAT, 10 k pull-up (R43) + 10 k NTC (TH1)
  - IN4: REF3025 (U17) output – absolute-reference cross-check
  - IN5: VSYS_SENSE via 100 k / 68 k (5.25 V → 2.13 V)
  - IN6, IN7 spare and COM tied to GND via 0 Ω (R57, R58, R59) – lift to use
- [x] Add resistor divider for +V / VSYS rail sensing into the new ADC (R44/R45 → IN5)
- [x] Absolute reference / non-ratiometric: AD7689 internal 2.5 V reference (REF + 10 µF C68, REFIN + 100 nF C70). Firmware must set CFG.REF = internal 2.5 V.
- [x] **ADC reference loading** – chose option (a): NTC pull-up R43 now fed from REF3025 OUT (`VREF_SENSE`) instead of the AD7689 REF pin. The conversion reference (`VREF_2V5`, internal 2.5 V + C68) carries no DC load; cell / VSYS readings stay absolute (non-ratiometric). NTC: compute the divider ratio as IN3 / IN4 – both channels see the same REF3025 voltage, so the NTC result cancels both reference tolerances. No firmware config change (AD7689 stays in internal-reference mode). Option (b) rejected: it needs a config change, makes REF3025 drive the REF pin's switched load, and gives up the ADC's lower-drift internal reference.
- [x] Bulk capacitance: VBAT_OR = C58 10 µF + **C73 100 µF 1210 (CL32A107MPVNNNE, LCSC C23742)**; VSYS = 3× 22 µF (C1/C5/C9) + C63 10 µF. Revisit at layout (X5R DC-bias derating).
- [x] **LM66100 ~CE break-out** – U12/U14/U18 ~CE now on local nets `BAT1_CE` / `BAT2_CE` / `BAT3_CE`, tied to `VBAT_OR` through 0 Ω links R71 / R72 / R73 (0603, C21189, fitted). Behaviour unchanged (plain ideal-diode OR); the 0 Ω pads are the rework point for later control.
  - Control constraint (LM66100 datasheet): the device turns OFF when ~CE > VIN + 80 mV and ON when ~CE < VIN − 250 mV (~CE max 5.5 V). Forcing a cell off therefore needs ~CE driven above that cell's voltage (up to ~4.3 V), so a 3.3 V ESP32/FPGA GPIO needs a level shifter (e.g. small PFET or open-drain + pull-up to a rail above the highest cell). Forcing ON (pulling ~CE low) can back-feed the other cells, so avoid it.
  - [ ] Later: pick GPIO source (ESP32 / FPGA / I²C expander) and the level-shift circuit, together with firmware cell prioritisation.
- [ ] Expose TP4056 CE / ~CHRG status (currently CE tied to +5 V, ~CHRG drives LEDs only)
- [x] Schematic clean-up: 4 dangling wire stubs fixed (PWREN ×3, VBAT1)
- [x] Final KiCad ERC run – done in the schematic-freeze pass (`doc/constraints/schematic_freeze.md`): 179 items, all classified acceptable or deferred to layout. Orphan `ADC_*` labels on `ram` kept (harmless, unconnected FPGA pins). The unused ADS1115 cache entry drops on the next save in KiCad.
- [ ] ~~Add USB-C PD sink/trigger chip~~ → moved to **Phase 2b** (below)
- [ ] (Optional later) Boost stage to extract remaining capacity below ~3.5 V

### Phase 2b – USB-C 5 V PD trigger
- [x] New sheet `usbc_pd.kicad_sch`. The board had no USB-C connector (US1 FTDI and US2 OTG are micro-B), so a **dedicated power-only USB-C charge port** was added; both micro-B data ports are unchanged.
  | Ref | Part | LCSC | Role |
  |---|---|---|---|
  | U23 | **WCH CH224K** (ESSOP-10) | **C970725** | USB PD sink controller, 5 V only |
  | J17 | GCT USB4125-GF-A, USB-C 6P power-only | C3151650 (JLC extended) | charge port, footprint `USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal` |
  | D55 | SS34 Schottky 3 A / 40 V (SMA) | C8678 | VBUS_C → `+5V` OR-ing, parallel to D8/D9 |
  | R84 | 1 k 0603 | C21190 | VBUS_C → CH224K VDD (shunt regulator) |
  | C79 | 1 µF 0603 | C15849 | CH224K VDD decoupling |
  | R85 | 10 k 0402 | C25744 | CH224K VBUS sense |
  | C80 | 10 µF 0805 | C15850 | VBUS_C bulk |
- [x] **5 V only:** CH224K level mode – **CFG1 (pin 9) tied directly to VDD** (= request 5 V), CFG2/CFG3 to GND. No CFG1 resistor: a resistor or open CFG1 would select 9/12/15/20 V. Marked on the sheet.
- [x] PD-only mode (datasheet §5.5): DP shorted to DM on the CH224K, not wired to the connector. CC1/CC2 go straight to the CH224K (Rd is internal – the external 5.1 k in the WCH reference is only for the CH221K). PG unused. `#FLG03` marks PD_VDD as a supply for ERC.
- [x] TP4056 path unchanged: `VBUS_C` only joins `+5V` through D55, like the existing micro-B inputs.
- [ ] Phase 4: J17 at the case edge; keep the VBUS_C → D55 → +5V path wide enough for 3 A. (J17 became the USB 2.0 data + power port in Phase 2c; the micro-B paths D8/D9 are DNP.)

### Phase 2c – Single USB-C: power + SD card + programming
**Decision:** replace the classic ESP32-WROOM-32 (no native USB) with an **ESP32-S3-WROOM-1-N8R2** and make it the only USB device on the one USB-C port. Rejected: USB hub + FT231X + separate USB card-reader IC (more parts, and the SD card would need a bus switch between the reader, ESP32 and FPGA).

| Ref | Part | LCSC | Role |
|---|---|---|---|
| U9 | **ESP32-S3-WROOM-1-N8R2** (8 MB flash, 2 MB quad PSRAM) | **C2913204** | USB device (CDC + MSC), WiFi/BLE, SD host, ECP5 JTAG programmer |
| J17 | **HCTL HC-TYPE-C-16P-01A** (USB 2.0 USB-C) | **C2894897** | single port: VBUS/CC (power) + D+/D− (data); replaces the 6P power-only connector |
| U24 | **USBLC6-2SC6** | **C7519** | ESD on D+/D−/VBUS |
| U23 | CH224K (unchanged) | C970725 | 5 V-only PD sink on CC1/CC2 |
| B3 / B4 | PTS645 tact switch | C285463 | BOOT (GPIO0) / RESET (EN) for USB download-mode recovery |
| C81 | 1 µF 0603 | C15849 | EN RC delay required by ESP32-S3 |
| R86 | 10 k 0402 | C25744 | SD card-detect pull-up |
| SD1 | Molex 104031-0811 microSD (existing socket) | C585350 | card-detect pin 10 now wired (`SD_CD`) |

- **USB data path:** J17 D+/D− (A6/B6, A7/B7 joined) → U24 → `USB_DP`/`USB_DN` → ESP32-S3 GPIO20/19. **CC1/CC2 stay on the CH224K**, which runs in PD-only mode (its DP/DM shorted together, not connected to the bus), so PD and USB data coexist. VBUS still feeds `+5V` only through D55, so the TP4056 chargers are unchanged; no higher-voltage path.
- **Programming the ESP32-S3:** built-in USB-Serial-JTAG (CDC console + flashing, no DTR/RTS). If application firmware switches the PHY to TinyUSB (CDC + MSC), recover with **BOOT (B3) + RESET (B4)** → ROM download mode.
- **SD card ownership: ESP32-S3** (SDMMC 4-bit, same GPIO numbers as before: CLK 14, CMD 15, D0 2, D1 4, D2 12, D3 13; card detect `SD_CD` on GPIO10, low = card present). Exposed to the PC as **USB Mass Storage** by the S3 firmware. The FPGA bank-6 SD pins (and N5 for `SD_CD`) remain connected: the FPGA bitstream must keep them Hi-Z while the S3 owns the card.
- **Programming the ECP5 over the same USB-C:** the ESP32-S3 drives the existing JTAG nets (`JTAG_TCK` GPIO18, `JTAG_TMS` GPIO5, `JTAG_TDI` GPIO16, `JTAG_TDO` GPIO17) to load SRAM or program the config flash through the FPGA (esp32ecp5 / openFPGALoader-style bit-bang, triggered over USB CDC or WiFi). No second USB interface.
- **ESP32-S3 GPIO map:** EN = `WIFIEN`; GPIO0 `WIFI_GPIO0` (BOOT, R56 pull-up, FPGA F1); UART0 TXD/RXD to the FPGA (`WIFI_TXD`/`WIFI_RXD`); ADC SPI SDO 6 / DIN 21 / SCK 8 / CNV 9; FPGA links GPIO1 (E9), GPIO40 (N3), GPIO41 (E6). Nets renamed to the S3 GPIO numbers: `WIFI_GPIO19→6`, `22→8`, `26→9`, `25→1`, `27→40`, `35→41`. Strapping pins 3/45/46 and GPIO35–37 left unconnected.
- **Side benefit:** the ESP32 no longer shares the display SPI pins (`GN12/GP12/GN13/GP13`), so that Phase 3 limitation is gone.
- **Fallback (DNP):** FT231X bridge U6 with micro-B US1 (the old USB-serial + JTAG path), FPGA-USB micro-B US2 and their parts (D8, D9, R9, R40, R49, R50, R52, R53, R54, R63, R64, D20, D21, D23–D26), and the 2×3 JTAG header **J4**. Populating U6 + US1 restores the original ULX3S programming path (the ESP32-S3 must then release the JTAG lines).
- [ ] Limitations / to do: no VBUS-detect GPIO on the S3 (self-powered device; add one if strict USB compliance is needed); S3 USB is full-speed (12 Mbit/s), so MSC throughput is roughly 1 MB/s; firmware work: TinyUSB CDC + MSC composite, SDMMC, JTAG bit-bang for the ECP5. Phase 4: J17 + B3/B4 reachable from the case, S3 antenna at a board edge.
- Full higher-voltage / higher-wattage PD charging (9–20 V + switching or multi-cell charger) remains a **Later** item.

### Phase 3 – Camera & Display
- [x] Add OV7670 connector / sheet
- [x] Add 40-pin FFC for Newhaven TFT
- [x] Map pins (reuse known mappings from existing projects)
- [x] Split former `LCD-Camera` sheet into dedicated `camera` and `display` sheets (residual renamed `fpga-io`)
- [x] Constraints note for later FPGA work → `doc/constraints/camera_display_pinmap.md` (ball / bank table for J7 + J1, all LVCMOS33)
- [x] J7 pinout checked against NHD datasheet (RGB666 + SPI, IM[2:0]=001); local VDD decoupling C74/C75 added
- [x] Backlight boost U8 (AP3032) on VSYS, 100 mA set by R19 2R0, CTRL pulled down (R18)
- [x] OV7670 J1 pinout checked (standard 18-pin module); SCCB pull-ups present
- [x] VCCIO for display banks 0/7 fixed at 3.3 V (RV2 DNP, RV3 fitted); legacy header J2 DNP

- [x] **CAM_PCLK on a clock pin** – swapped `GP16`/`GP17` on the `camera` sheet: CAM_PCLK now on L16 (GR_PCLK3_0), CAM_PWDN (with R17) on N16
- [x] **J6 legacy 2×20 header** – DNP (kept in schematic/layout like J2; keep/drop decided at layout). D51/D52 5 V links to the header are DNP as well.
- [x] **J5 VCCIO jumper (power sheet)** – DNP; VCCIO for banks 0/7 is hard-set to 3.3 V by RV3

- [x] **User I/O for the monocular** – 2 buttons + 2 status LEDs on `fpga-io` (besides power button B0):
  B1/B2 PTS645 (C285463) active-low on `BTN1n` (E8) / `BTN2n` (D8), 10 k pull-ups R67/R68;
  D53/D54 0603 red (C2286) active-high on `LED0` (B2) / `LED1` (C2) via 1 k R69/R70.
  Orphan ULX3S labels removed (`SW3/4`, `LED2..7`, 12× `AUDIO_*`); those U1 pins plus D9 now carry no-connect flags.
- [x] **ERC clean-up (+5V)** – D51/D52 DNP (follow J6); `#FLG02` PWR_FLAG added on `+5V` at U16 VIN (power sheet), since +5V is only fed through the D8/D9 diodes from USB VBUS. `fpga-io` now shows only the intentional `CAM_XCLK` alias warnings.

**Carried into Phase 4**
- [ ] B0/B1/B2 footprint `Button_Switch_SMD:SW_SPST_PTS645` no longer exists in the KiCad 10 library (now e.g. `SW_SPST_PTS645Sx43SMTR92`) – pick the variant matching LCSC C285463 (and the case: top vs side-actuated) during placement.
- [ ] LED colour / brightness: D53/D54 reuse the red charge-LED part; 1 k at 3.3 V ≈ 1–1.5 mA (kept dim, the LEDs sit near the eyepiece). Revisit with the case design.

**Verify (no schematic change expected)**
- [ ] U8 uses the `AP3019AKTR` symbol with value AP3032KTR-G1 – confirm identical SOT-23-6 pinout; confirm L4 4.7 µH against the AP3032 datasheet recommendation.
- [ ] J7 footprint is Hirose FH12-40S-0.5SH; NHD recommends Molex 54104 (datasheet lists both -4031 and -4096). Pick contact side (top/bottom) once the FPC fold direction is fixed in Phase 4.
- [ ] LCD VDD = +3V3 is at the panel's 3.3 V maximum (typ 3.0 V) – accepted, note only.
- [x] ~~ESP32 IO32/IO33 share LCD_SCK/LCD_DC~~ – resolved in Phase 2c (ESP32-S3 no longer connected to the display SPI lines).

**Sheet map (camera / display area)**

| Sheet file | Contents | Connects via |
|---|---|---|
| `display.kicad_sch` | J7 NHD-2.1-480480AF-ASXP 40-pin FFC, C74/C75 VDD decoupling, backlight boost U8 AP3032 (L4, D1, C37, C38, R18, R19) from VSYS | Global `GN0..13`/`GP0..13` (RGB, sync, SPI, reset), `GP13` (BL PWM), `+3V3`, `VSYS`, `GND` |
| `camera.kicad_sch` | J1 OV7670 2×9 header, SCCB pull-ups R7/R14, R15 XCLK series, R16/R17, C18/C36 decoupling | Global `GN14..17,21..24`/`GP14..17,21..24` (XCLK via `GN16`, net named `CAM_XCLK`), `+3V3`, `GND` |
| `fpga-io.kicad_sch` | U1 ECP5 bank units (BANK0/7 and BANK1 I/O), user I/O (B1/B2 buttons, D53/D54 LEDs), legacy ULX3S headers J2 and J6 and their D51/D52 5 V links (all DNP) | Global labels to the sheets above |

Local labels (`LCD_*`, `CAM_*`) are descriptive aliases on each sheet; the `GN*`/`GP*` global labels carry the connections.

### Phase 3b – IMU (moved from stretch goals)
- [x] Part: TDK InvenSense **ICM-42688-P** (6-axis gyro + accel, LGA-14 2.5×3 mm), LCSC **C1850418**, JLCPCB assembly: extended part (stock to re-check at order time)
- [x] New sheet `imu.kicad_sch` (U22); symbol in project library `symbols/fcl_local.kicad_sym` (KiCad 10 has none); footprint `Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` (pad pattern matches DS-000347 pin-out)
- [x] Power: VDD + VDDIO from +3V3; decoupling per datasheet Table 10 – C76 100 nF (C1525) + C77 2.2 µF (C87995) on VDD, C78 10 nF (C15195) on VDDIO
- [x] Interface: **I²C, dedicated bus to the FPGA** (separate from the RTC bus, so it can run at up to 1 MHz), AP_CS = VDDIO selects I²C, address **0x68** (AP_AD0 = GND), 4.7 k pull-ups R76/R77 (C25900)
  | Net | IMU pin | FPGA ball | Bank |
  |---|---|---|---|
  | `IMU_SCL` | 13 AP_SCL | E7 (PT9A) | 0 |
  | `IMU_SDA` | 14 AP_SDA | D7 (PT9B) | 0 |
  | `IMU_INT1` | 4 INT1 | C1 (PL38A) | 7 |
  | `IMU_INT2` | 9 INT2/FSYNC/CLKIN | D1 (PL38B) | 7 |
  (FPGA pins reuse balls freed in Phase 3. INT2 pin can instead be used as FSYNC, e.g. camera frame sync from the FPGA; the ESP32 can reach the IMU through the FPGA.)
- [ ] Phase 4: place U22 rigidly near the board's centre of mass, away from the boost inductor / switching regulators; record its axis orientation relative to the camera optical axis.

### Phase 3c – RC servo headers (DNP for first prototype)
- [x] New sheet `servo.kicad_sch`: 6× 1x3 2.54 mm headers **J_SRV1–J_SRV6** (`PinHeader_1x03_P2.54mm_Vertical`), **all DNP**
- [x] Pinout (standard RC servo): **1 = Signal** (1–2 ms pulse), **2 = +V (`SERVO_V`)**, **3 = GND**
- [x] Signals from FPGA bank 6 (3.3 V, not used by camera/display) through 1 k series resistors R78–R83 (0603, C21190, **DNP with the headers** – protects the FPGA pin if a servo lead is miswired):
  | Header | Net | FPGA ball |
  |---|---|---|
  | J_SRV1 | `SRV_PWM1` | P1 |
  | J_SRV2 | `SRV_PWM2` | P2 |
  | J_SRV3 | `SRV_PWM3` | P3 |
  | J_SRV4 | `SRV_PWM4` | P4 |
  | J_SRV5 | `SRV_PWM5` | N2 |
  | J_SRV6 | `SRV_PWM6` | J4 |
  (these balls previously carried the orphan ULX3S `OLED_*` labels, now repurposed)
- [ ] **Open decision – SERVO_V source.** `SERVO_V` currently only joins the six header pin 2s. Options: jumper / 0 Ω link to VSYS (simple, but servo stall current – often > 1 A each – then loads the cells and the LM66100 path), or a dedicated 5–6 V regulator. Decide before the servo headers are populated; size copper and connector for the chosen current.
- [ ] Phase 4: keep footprint space for J_SRV1–6 + R78–R83 near a board edge (they are DNP but on the PCB); header LCSC part still to pick.

### Phase 4 – Mechanical & PCB
- [ ] **First:** resolve the 12 footprint-link issues from the freeze note (mounting holes, socket strips, RV2/RV3, PTS645 buttons) and add footprints for the 18650 contacts BT11–BT32, then *Update PCB from Schematic*
- [ ] Battery bay geometry: 3×18650 bay in the case, PCB contact positions BT11–BT32, spring travel / cell-length tolerance, reverse-insertion keying
- [ ] Board outline for monocular (camera + TFT inline, batteries side-by-side)
- [ ] Placement for vibration robustness (NTC next to cells)
- [ ] 3D-print case concept

**Placement constraints (prepared – outline / placement not started)**
- *Optical axis first.* TFT faces the eye, camera faces forward, inline. Decide PCB orientation
  before anything else:
  - (a) PCB perpendicular to the axis: TFT on the rear face, camera on the front face.
  - (b) PCB along the axis.
  OV7670 modules have in-plane header pins, so with J1 as a *vertical* 2×9 socket the lens
  looks parallel to the PCB (suits b). Option (a) needs a right-angle socket or a flat-mounted
  module. This choice sets the J1 type and position.
- *TFT.* 2.1" 480×480 IPS. Take the outline, active-area centre, FPC exit position / length and
  stiffener from the drawing on datasheet page 3 (vector drawing, not transcribed here). Put J7
  where the FPC lands without a twist; the FPC fold direction fixes the FFC contact side.
  Keep the backlight boost loop (U8, L4, D1, C38, R19) tight and close to J7.
- *Camera / TFT alignment.* The lens axis and the TFT active-area centre should be coaxial (or
  offset by a known amount for software correction). Fix that in the case model, then place
  J1 / J7 from it.
- *FPGA side.* Display nets exit the BGA top / left (banks 0, 7); camera nets exit the right
  (banks 1, 2, 3). Natural arrangement: J7 left / top of U1, J1 right of U1. Keep CAM_PCLK and
  LCD_PCLK short and away from the switching regulators.
- *Batteries.* 3×18650 (Ø18.6 × 65 mm each, ≈ 56 × 65 mm side-by-side + bay walls) sit in a
  plastic battery bay in the case and press directly on PCB-mounted contacts: positive buttons
  BT11/BT21/BT31 and negative springs BT12/BT22/BT32 (one pair per cell, at opposite ends of each cell).
  The final bay geometry (contact pitch, spring compression, cell length tolerance, polarity
  keying so a reversed cell cannot touch) is defined in Phase 4. Keep the contacts close to the
  reverse-FET / LM66100 input stage; the PCB must span the full cell length (≈ 65 mm + springs). The NTC must
  physically touch or sit next to the cells. Hot-swap needs a cell door that does not stress
  the PCB.
- *Edge-accessible parts.* J17 USB-C (power + data + programming), the microSD slot SD1, B0 power button,
  B3 BOOT / B4 RESET (can sit behind pin-holes), J3 WIFI_OFF, BAT1 CR1225 holder.
  DNP fallbacks US1 / US2 / J4 only need edge access if they are ever populated.
  J17 (USB-C 5 V charge port, Phase 2b) also needs case-edge access; higher-voltage PD stays deferred.
- *ESP32 antenna.* Board edge with copper keep-out under the antenna, away from the cells and
  any future metal case (the metal case will need an RF window).
- *Large / optional parts.* J2 and J6 2×20 angled headers (both DNP) are ≈ 51 mm long; keep the
  footprints or drop them depending on layout space.
- *Mounting.* H1–H4 M3 holes exist but are still at ULX3S positions; re-place them for the case.
  Avoid putting tall or heavy parts (headers, inductors, cell connectors) at unsupported spans
  (vibration).

### Phase 5 – Prototype
- [ ] BOM with LCSC / JLCPCB numbers
- [ ] Gerbers + CPL
- [ ] First order

### Later / stretch goals
- [ ] Higher-voltage / higher-wattage USB-C PD path + switching or multi-cell charger (max charging power)
- [ ] Firmware-driven cell prioritisation (CE control) using the new 8-ch ADC data
- [ ] Optional bottom-capacity boost stage

---

## Power architecture notes (current)

- Cell negatives common (GND). Positives individual (CELLx_RAW → VBATx after reverse FET).
- VSYS powers the main regulators and the LCD boost. CR1225 VBAT is unrelated.
- 3.3 V rail needs ≥ ~3.4 V on VSYS → practical cutoff ≈ 3.5–3.6 V on the highest cell.
- AD7689 8-ch ADC on SPI (WIFI_GPIO6/21/8/9 on the ESP32-S3, also routed to FPGA pins on the usb sheet). Internal 2.5 V reference (unloaded); REF3025 measured on IN4 and also feeds the NTC pull-up R43 (NTC ratio = IN3 / IN4).
- CHGx LEDs are local only; charger enable/status not yet routed to a processor (open item).
- Ideal-diode OR-ing currently prefers the highest cell. True sequential “dead-first” requires CE control: ~CE pins are broken out via R71–R73 (0 Ω), and the level-shifted drive is still to be designed.
- CH224K (U23) requests a 5 V-only PD contract on the USB-C charge port; the existing TP4056s are unchanged.

---

## What we keep from original ULX3S

- ECP5-85F + config flash + SDRAM
- ~~USB (FTDI) programming / serial~~ → single USB-C via ESP32-S3; FTDI path kept as DNP fallback (Phase 2c)
- WiFi (ESP32) sheet
- SD card sheet
- Core power regulators (1.1 / 2.5 / 3.3 V)

## What we remove

- GPDI / digital video connector
- Large GPIO headers
- Audio jack / analog path
- Original single-cell / simple battery input (replaced by 3×18650)

---

## Notes

- Original files stay on `master`. All destructive work happens on `monocular-strip`.
- Mark checklist items complete as we finish them.
- Update this file at the end of each phase.
- Next power-related work: ADC reference-loading decision, CE pin control, KiCad ERC pass → close Phase 2. Then Phase 2b (USB-C PD 5 V trigger).