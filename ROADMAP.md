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
| 4 | PCB mechanical outline (monocular form) | **In progress** – placement complete; routing step 1 done (rules, planes, fan-out, decoupling – 4.11); next: high-speed nets |
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

#### 4.1 Locked mechanical decisions (2026-11-07)
Reference renders: `Pic_LCD_ISO.png` (eye side) and `Pic_Cam_ISO.png` (scene side).
**Coordinates:** front view = looking at the scene/camera side; origin = top-left board corner, +X right, +Y down, mm.
**Front = PCB top layer (F)**, faces the scene. **Back = bottom layer (B)**, faces the eye.

**1. Optical axis – LOCKED: perpendicular to the PCB** (option (a)).
- Front (F): OV7670 module mounted **flat, parallel to the board**, lens forward, plugged into J1 (vertical 2×9 socket; module header pins point into the board).
- Back (B): 3×18650 battery bay; the round TFT sits on top of the bay facing the eye.
- The axis passes through the **board centre (42.5, 37.5)**: camera lens centre and TFT active-area centre are **coaxial** (target ±0.5 mm), so no software parallax offset is needed.

**2. Outline – LOCKED: 85.0 × 75.0 mm**, rectangle with R3 corners, 1.6 mm, **4 layers** (ULX3S-derived stack-up and BGA 0.8 mm rules).
- M3 holes H1 (4, 4), H3 (4, 71), H4 (81, 71). **H2 (81, 4) removed from the rev-A board** (*Exclude from board*): that corner is inside the ESP32-S3 antenna keep-out, which forbids any footprint; the case supports the corner with a ledge, which also keeps a metal screw away from the antenna. The cells are held by the bay, not the PCB, so 3 screws are enough.
- **Fresh PCB:** the ULX3S placement/routing in `FCL.kicad_pcb` is not reused (different outline, most parts gone).

| Fit check | Needed | Available |
|---|---|---|
| Cell + contacts along X | 18650 65.0 mm (protected cells up to ~69.5) + spring ~5 + button ~1.5 → bay ≈ 72–76 mm | 85 mm (≈ 5 mm margin each side) |
| 3 cells stacked along Y | 3 × 18.6 + 2 × 1.9 gap = 59.6 mm (row pitch **20.5**, refined in 4.4) | 75 mm (≈ 7.7 mm strip top and bottom) |
| Depth (front → back) | lens ≈ 25 (socket 8.5 + module 1.6 + lens ~15) + PCB 1.6 + bay standoff 1.5 + cell 18.6 + TFT ~3 | ≈ 50 mm + case walls |

**3. Component positions – LOCKED (zones; exact XY during placement)**

| Item | Side | Position (front view) | Notes |
|---|---|---|---|
| OV7670 module + J1 | F | lens on the axis (42.5, 37.5); keep-out ≈ 35 × 35 mm centred on it, ≈ 25 mm tall | J1 position = axis minus the module's lens-to-header offset (measure the module). Parts ≤ 6 mm tall may sit under the module. |
| Round TFT | on the bay (B side) | active-area centre on the axis | outline + FPC exit/length from the NHD drawing (datasheet p.3) – still to measure |
| Display FFC J7 | B | bottom edge, centred (x ≈ 42.5, y ≈ 70–73) | FPC leaves the display bottom and folds down past the bottom cell; the fold fixes the FFC contact side. If the FPC is too short: J7 moves to the F bottom edge with the FPC wrapping the board edge. Backlight boost (U8, L4, D1, C38, R19) next to J7. |
| 18650 cells 1/2/3 | B | rows y = **17.0 / 37.5 / 58.0** (pitch 20.5, symmetric about the axis), axes along X | cell 1 top, cell 3 bottom |
| − springs BT12 / BT22 / BT32 | B | left end, x ≈ 6 | common GND – wide GND pour |
| + buttons BT11 / BT21 / BT31 | B | right end, x ≈ 79 | each → `CELLn_RAW` → Q3/Q4/Q5 on F directly behind |
| Power input stage (Q3–Q5, U11/U13/U15 TP4056, LM66100 U12/U14/U16/U18/U19, sense dividers, ADC U21, REF U17) | F | right strip, x ≈ 62–85 | short cell paths; TP4056 heat kept away from the IMU and camera |
| NTC TH1 | B | (36, 37.5) under the middle cell's bottom line | thermal pad to cell 2 (4.4) |
| FPGA U1 + SDRAM U2 + flash U10 + TLV62569 regulators | F | left strip, U1 centre (17, 28) rotated 90° CW, SDRAM below U1 | rotation puts banks 2/3 (SDRAM + camera) at the bottom and bank 1/0 toward the centre; x ≥ 8 keeps the BGA clear of the spring-contact tabs that come through the board at x ≈ 5.5 |
| **IMU U22** | F | **on the optical axis, under the camera module (≈ 42.5, 37.5)** | board centre = most rigid point; away from TP4056/boost heat; record its axes relative to the camera |
| ESP32-S3 U9 | F | top-right, antenna at the top edge (y < 7) | antenna keep-out on all layers; no cell behind it (cells start at y ≈ 8.7); case needs an RF window |

**4. Edge-accessible parts – LOCKED**

| Edge | Parts |
|---|---|
| Bottom | J17 USB-C (F, x ≈ 62, mouth flush with the edge), SD1 microSD (F, x ≈ 25, Molex 104031 card slot ≈ 1 mm inside the edge, card protrudes ≈ 3 mm), J7 FFC (B, centre, cable entry from the edge), servo headers J_SRV1–6 (F, bottom-right block ≈ 16 × 8 mm, DNP but footprints kept – next to the power stage for future `SERVO_V`) |
| Top | B0 power, B1 / B2 user buttons, D53 / D54 status LEDs (F, top-left to centre); ESP32-S3 antenna (top-right) |
| Internal (no edge needed) | B3 BOOT / B4 RESET (near U9, may sit behind case pin-holes), J3 WIFI_OFF, BAT1 CR1225 (F) |
| Not on the rev-A PCB | J2, J6 legacy 2×20 headers (DNP, ≈ 51 mm long – do not fit) → set *Exclude from board*. DNP fallbacks U6/US1/US2/J4: keep footprints only if space remains after placement. |

#### 4.2 First board outline + mechanical placement (done 2026-11-07, not routed)
`FCL.kicad_pcb` was rebuilt from scratch (ULX3S placement/routing, tracks, zones and nets removed; 4-layer stack-up and design rules kept). Board origin = page (100, 100) = top-left corner; drill/grid origin set there. Coordinates below are board mm, front (top) view.

| Ref | Side | Position | Notes |
|---|---|---|---|
| Outline | – | 85.0 × 75.0, R3 corners | Edge.Cuts |
| H1 / H3 / H4 | – | (4, 4) / (4, 71) / (81, 71) | M3 ISO14580 pad; H2 excluded (antenna corner) |
| U22 IMU | F | (42.5, 37.5) – on the optical axis | under the camera module |
| J1 camera socket | F | pad centroid (42.5, 52.5), 2×9 along X | 15 mm lens-to-header offset is provisional – measure the OV7670 module |
| U1 ECP5 | F | (17, 28), rot −90 | courtyard x 7.9–26.1 |
| U9 ESP32-S3 | F | (68, 12.75), antenna at the top edge | library keep-out zone kept (no copper/footprints x 44–92, y < 6) |
| J7 display FFC | B | (42.5, 69.1), opening toward the bottom edge | |
| J17 USB-C | F | (62, 70.7) | |
| SD1 microSD | F | (25, 68.3), rot 180 | new footprint `fcl_local:microSD_Molex_104031-0811_FCL` |
| B0 / B1 / B2 | F | (14, 5.5) / (25, 5.5) / (36, 5.5) | top edge |
| J4 JTAG (DNP fallback) | F | (49, 12) | below the antenna band |
| TH1 NTC | B | (36, 37.5) | under cell 2 (moved in 4.4) |
| BT12 / BT22 / BT32 (− springs) | B | x 5.5, y 17 / 37.5 / 58 | spring tips reach x ≈ 18 (≈ 5.8 mm compression with a 65 mm cell) |
| BT11 / BT21 / BT31 (+ buttons) | B | x 79.5, y 17 / 37.5 / 58 | foot-to-foot 74 mm |

Reference drawings: optical-axis crosshair (Dwgs.User), OV7670 35 × 35 keep-out (F.Fab), three 65 × 18.6 cell outlines and a nominal Ø53.3 TFT circle (B.Fab).

Footprint work done for this step:
- 18650 contacts: real EasyEDA footprints + STEP models for **MY-18650-04-J (C19184125)** and **MY-18650-05-J (C19184124)** in `footprints/fcl_local.pretty` / `fcl_local.3dshapes` – both are **through-hole** (slotted tab + two SMD anchor pads).
- microSD: `fcl_local:microSD_Molex_104031-0811_FCL` (KiCad's Molex 104031-0811 pattern, pad 9 renamed GS4, shield tabs GM1–GM4 to match the SD1 symbol). The old dual SCHD3A0100/104031 footprint put extra pads past the card opening. Symbol pins 11, 12 (NC) and GS1–GS3 (extra GND) have no pads – *Update PCB* lists them as warnings.
- All 14 footprint-link issues fixed (PTS645 → `SW_SPST_PTS645Sx43SMTR92`, `MountingHole:` library, 2.54 mm sockets, RV2/RV3 pad name); J2/J6 and H2 set *Exclude from board*.

DRC after placement (mechanical categories): no courtyard overlaps, no keep-out violations, no edge-clearance violations. Remaining items are for the routing phase: pad-to-pad clearance / solder-mask bridges inside the fine-pitch U22 (0.5 mm LGA) and J17 (USB-C) with the inherited 0.2 mm clearance rule, J17 pad-to-peg hole clearance (footprint-inherent), and silkscreen cosmetics.

#### 4.4 Battery bay, NTC, IMU and mechanical-stress constraints (2026-11-07)
**Cell contacts (confirmed):**
- Three identical pairs, **all cells the same way round**: − springs (MY-18650-05-J) at the left end x 5.5, + buttons (MY-18650-04-J) at the right end x 79.5; both stand on the back (B) and face the cell (checked in the 3D render). Reverse insertion is protected electrically by the AO3401A FETs; the bay should still carry "+ →" moulded marks.
- Row pitch widened 19.5 → **20.5 mm** (rows 17 / 37.5 / 58): 1.9 mm gap between cans leaves room for 1.6 mm printed ribs.
- Length: contact bases 74.0 mm apart; spring tip x ≈ 18.0, button face x ≈ 77.2 → 59.2 mm free gap. A 65.0 mm cell compresses the spring ≈ 5.8 mm of ≈ 12.4 mm free length. **Usable cell length ≈ 65.0–67.5 mm** (flat or button-top, unprotected). **Protected 69–70 mm cells do not fit.** Dimensions are from the EasyEDA footprints – confirm spring free/solid length on the MY-18650-05-J drawing.

**Battery bay (case part) – reserved on the PCB back as rule areas (no B-side footprints; tracks allowed):**

| Rule area | Region (x, y) | Purpose |
|---|---|---|
| `BAY_END_WALL_L` | 0.3–3.3, 8–67 | wall behind the springs takes the spring load |
| `BAY_END_WALL_R` | 82.3–84.7, 8–67 | wall behind the buttons |
| `BAY_RIB_1` / `BAY_RIB_2` | 19–76, y 27.25 ± 0.9 / 47.75 ± 0.9 | 1.6 mm ribs between cells rest on the PCB (also stiffen the board centre) |
| `CASE_BOSS_TR` | 78.5–84.7, 3.5–9 | case boss / ledge replacing the removed H2 at the antenna corner |

- Cradle height: cells sit **2.5 mm above the PCB** → B-side parts under the cells ≤ **1.5 mm** tall (0402–0805 passives, SOT-23 OK; no inductors / electrolytics / tall connectors under the bay).
- The bay's bottom side-wall must **bridge x ≈ 28–57** (no contact with the PCB) where J7 and the TFT FPC pass; J7 sits ≈ 7 mm below the bottom cell's edge.
- Notes for the bay are on Dwgs.User beside the board outline; bay outline and rib lines on B.Fab.

**NTC (TH1):** *(superseded by 4.8 – three NTCs beside the − springs)* moved to (36, 37.5) on B, under the bottom line of the middle cell (cell 2 – the warmest, surrounded by the other two). Thermal coupling through a **2 mm compressible silicone thermal pad** (≈ 3 W/m·K, ≈ 5 × 5 mm) between TH1 and the can; nothing else in a 6 × 6 mm area around it. One NTC = bay temperature only, not per-cell.

**IMU (U22) – confirmed at (42.5, 37.5):**
- On the optical axis at the board centre: not at an edge, between the three screws and directly over the cell-2 cradle and both ribs, so the stiffest region once the bay is fitted.
- Distances as placed: FPGA courtyard ≈ 14.6 mm, ESP32-S3 module ≈ 15 mm (antenna ≈ 30 mm), USB-C / charge input ≈ 27 mm, display boost (U8/L4, next to J7) ≈ 30 mm.
- **Quiet radius 15 mm (F.Fab circle):** no switchers (TLV62569 + L1–L3, AP3032 + L4, TP4056s) or VSYS/charging high-current paths inside it; no vias/traces under the LGA; solid GND plane beneath; C76–C78 right at the part. The camera module sits ≈ 8.5 mm above it on J1 – fine for an IMU, but keep its mass secured (below).

**Vibration / mechanical-stress concerns (to design out in the case and placement):**
1. **Spring load:** 6 contacts at ≈ 5.8 mm compression push the board ends outward (order of 3–6 N each). The contact plates must bear on the bay end walls (`BAY_END_WALL_*`); the slotted THT tabs and SMD anchors must not carry the spring force.
2. **Top-right corner (no H2):** the top-row button contact BT11 loads a corner without a screw → the case boss/ledge `CASE_BOSS_TR` is mandatory.
3. **Camera module ≈ 25 mm tall on a friction-fit 2×9 socket:** a lever arm under vibration (socket fretting, intermittent pixels). Fix the module with its two M2 holes on standoffs (reserve them once the module is measured) or a case clamp.
4. **BGA (U1) next to the left-end springs:** board flex at the left edge stresses the BGA balls. U1 keeps ≥ 2.4 mm from the contact tabs; the left bay wall must be stiff and flush.
5. **USB-C J17:** plug insertion/levering at the bottom edge – THT shell legs help; the case should surround the receptacle so the case, not the PCB, takes side loads.
6. **TFT:** held by the bay/case, never by its FPC; FPC strain relief and minimum bend radius at the board edge; J7 latch closed.
7. **Heavy parts** (inductors, C73 100 µF 1210, J4 if fitted) not at the unsupported top-right corner or mid-span away from ribs.
8. **Hot-swap door:** opening/closing must not load the PCB; door hinge and latch on the case.
9. Firmware: run the IMU with a suitable low-pass / ODR so residual board resonance (plate modes between supports) is filtered.

#### 4.5 Netlist import + rough functional placement (2026-11-07, not routed)
- *Update PCB from Schematic* done in KiCad (after renumbering duplicate `#PWR01–04` on the camera sheet). All 21 pre-placed parts kept their positions.
- **Excluded from the rev-A board** (*Exclude from board*, DNP or obsolete; no room on 85 × 75): FT231X fallback U6 + micro-B US1/US2 and their parts (D8, D9, D20, D21, D23–D26, R9, R40, R49, R50, R52–R54, R63, R64); D51/D52 (5 V links for the already-excluded J6); J5 (obsolete VCCIO jumper); J3 WIFI_OFF header (its pins would enter the battery bay; B4 RESET and the FPGA's `WIFI_EN` cover it). **J4 stays as the JTAG fallback.**
- **RP1–RP3** (NC solder jumpers on the 1V1/2V5/3V3 rails, cut to measure current) now use `fcl_local:R_0805_Jumper_NC_NetTie` – the same copper-bridge jumper with pads 1–2 declared as a **net tie**, so DRC accepts the intentional short.
- 246 footprints, all inside the outline. Rough placement by functional group into the 4.1 zones (front unless noted):

| Group | Where |
|---|---|
| Flash U10, 25 MHz Y1, AE1, flash/config resistors | top-left above U1 |
| Regulators U3–U5, L1–L3, their caps and feedback | top-centre between U1 and J4 (outside the IMU quiet radius); feedback parts partly on B |
| SDRAM U2 | below U1 (15, 50); decoupling on B under U2 |
| FPGA decoupling, RV2/RV3 | B, under/next to U1 |
| RTC U7 + Y2, power-button / wake logic, D11 | around the IMU under the camera module (low-noise logic only) |
| CR1225 holder BAT1 | bottom-centre (43.5, 67.6) |
| IMU C76–C78, R76/R77 | ring around U22 |
| Camera R7, R14–R17, C18, C36 | just below J1 |
| Chargers U11/U13/U15, LM66100 U12/U14/U18/U19, Q3–Q5, sense dividers, C73, charge LEDs | right strip x ≈ 58–78 |
| ADC U21, REF U17, LDO U20 and passives | B, right end under cell 1 (all ≤ 1.5 mm) |
| USB-C group U24, R84, R85, C79, C80, U16, +5V caps | above / beside J17; CH224K U23 on B bottom strip; D55 right of J17 |
| Servo J_SRV1–6 (DNP) | 2 × 3 block x ≈ 59–77, y ≈ 48–61 (pins clear of `BAY_RIB_2` and the BT31 plate); R78–R83 on B |
| Display boost U8, L4, D1, C37, C38, R18, R19, C74, C75 | B bottom strip right of J7 (not under the cells) |
| BOOT/RESET B3/B4, button/LED/I²C pull-ups | B top strip (above the cells) |
| Status LEDs D53/D54 | F top edge next to B2 |

- Checks: no courtyard overlaps, no shorts, no keep-out / rule-area / edge violations; every back-side part under the cells is a low-profile package. DRC remaining: 199 solder-mask bridges + 13 clearance hits **all inside single fine-pitch parts** (U2, U21, J7, J17, U22, SOICs) → design-rule task; 499 unrouted connections; silkscreen overlaps (cosmetic). Schematic parity: only the 5 expected SD1 pins without pads (11, 12, GS1–GS3).
- **Placement concerns to address while refining:** the three TP4056s sit close together (up to ≈ 3 × 1.3 W at 1 A charge each) → spread them, add thermal vias/copper, or lower the charge current; FPGA decoupling should move directly under the BGA ball field once the fan-out is planned; silkscreen cleanup.

#### 4.6 Placement reset – controlled re-placement order (2026-11-07)
- The 4.5 rough placement was cleared: every footprint except the fixed/edge set below was moved **off the board** into a staging field below the outline (grouped by sheet, front side, 0°, servo headers last). Footprints keep their nets and schematic links, so nothing needs re-importing; they are brought back in a controlled order.
- **On the board (unchanged X/Y/rotation from 4.5; locked unless noted):**

| Part | Role | Note |
|---|---|---|
| SD1 | microSD at the bottom-left edge | locked, no rotation |
| J17 | USB-C at the bottom-right edge | locked, no rotation; nudged 0.15 mm up to clear the corner radius (edge clearance) |
| B0 / B1 / B2 | buttons, back top strip | **not locked** – may rotate, stay within ±0.5 mm |
| J7 | display FFC, back bottom edge | locked |
| J1 | camera header on the optical axis | locked |
| BT11–BT32 | 18650 spring/button pairs, rows 17 / 37.5 / 58 (pitch 20.5) | locked |
| H1 / H3 / H4 | M3 case screws | locked |

- Housing clearance: `CASE_BOSS_TR` trimmed to y 3.5–8.3 so BT11's top tab no longer intrudes; board outline and all bay rule areas otherwise unchanged.
- Re-placement order from here: U1 (FPGA) + U9 (ESP32-S3, antenna in the top-right keep-out) + U22 (IMU, axis) + TH1 + J4 → SDRAM / flash / clock → regulators → chargers / power path → ADC → USB-C and display support → passives/decoupling → servo headers (last).

#### 4.7 Digital core placement (2026-11-07, not routed)
- Digital section on the front, in the "near" digital zone: left strip (FPGA, SDRAM, flash, clock) plus the ESP32-S3 top-right. Analog/sensor items (IMU on the axis, ADC, chargers on the right) stay outside it; the inner GND plane is continuous under the digital block.
- Rotations and positions chosen by **ratsnest length** (MST of every signal net to the parts already on the board) with ≥ 1 mm routing channels between chips, ≥ 10 mm from the IMU spot, and clear of the BT tab slots, H1, SD1, J1 and the antenna keep-out. Comparing SDRAM *below* vs *above* the FPGA: above is ≈ 12 % shorter in total (U1 then sits nearer J1 / J7 for the camera and display buses), so the 4.1 "SDRAM below U1" note is superseded.

| Ref | Part | Position (board mm, F) | Rot | Note |
|---|---|---|---|---|
| U2 | SDRAM TSOP-54 | (17.0, 12.5) | 0° | top-left, above U1 |
| U1 | ECP5 BGA-381 | (22.0, 34.0) | 180° | box x 12.7–31.3, y 24.7–43.3; 11 mm from the IMU spot |
| U10 | config flash SOIC-8 | (29.0, 20.0) | 180° | between U2 and U1, next to the SPI-config bank |
| Y1 | 25 MHz oscillator | (25.0, 48.0) | 0° | below U1, next to the clock input |
| J4 | JTAG 2×3 (DNP fallback) | (37.0, 23.0) | 90° | between U1 and U9, outside the antenna band |
| U9 | ESP32-S3-WROOM-1 | (66.0, 12.75) | 0° | antenna flush with the top edge (moved 2 mm left of 4.2) |

- No USB bridge chip any more (FT231X excluded in 4.5; the ESP32-S3 native USB is the bridge).
- **Long nets left (straight-line MST):** SD bus SD_CLK/CMD/D0–D3/CD ≈ 73–90 mm (SD1 is fixed bottom-left, the ESP32 top-right, the FPGA taps the same bus) → route as a grouped bus down the left/centre on one inner-adjacent layer, keep the FPGA tap short or consider moving SD1 later; ESP32↔FPGA UART/SPI/GPIO (`WIFI_*`) ≈ 30–59 mm and JTAG ≈ 31–35 mm (low speed, OK); camera/display `GPn/GNn` ≈ 27–41 mm; SDRAM data ≈ 25–33 mm (length-match the SDRAM group during routing); BTN1n/BTN2n ≈ 41 mm to the top buttons (slow).
- DRC: no courtyard, keep-out, edge or short violations; parity unchanged (5 SD1 pins).

#### 4.8 Analog + power-management placement (2026-11-07, not routed)
- Far side = **right half (front) + back**, opposite the digital strip (U1/U2/U10/Y1 left, U9 top-right). Every part placed by minimum ratsnest to the already-placed pins, with: switchers, inductors and TP4056s ≥ 15 mm from the IMU spot; back-side parts under the cells ≤ 1.5 mm (0402–0805, SOT-23/363, TSOT, LFCSP, 1008 / SWPA3015 inductors); nothing on the bay ribs / end walls / boss; through-pad parts (TP4056 EP vias, BT tabs, H3/H4) treated as obstacles on both sides.

| Block | Side | Where (board mm) | Parts |
|---|---|---|---|
| Reverse FETs | B | next to each + button, x 75.5, y 15.5 / 36 / 56.5 | Q3/Q4/Q5 + C40/C42/C46 |
| Chargers | F | right strip below the ESP32, ≥ 3 mm apart for heat: U11 (64, 33.5), U13 (72.5, 37.5), U15 (73, 47) | + PROG R20/R22/R41, LEDs D2–D4 + R21/R23/R42, input caps C39/C41/C43 |
| Ideal diodes / power path | F | U12 (69, 28.5), U14 (74.5, 31.5), U18 (75, 52), U16 (70.5, 55.5), U19 (73.5, 55.5), C73 (67.5, 40) | + ST 0R links, CE links R71–R73, VSYS caps |
| USB-C input | F / B | U24 ESD (74.5, 64.5) F and D55 (67, 59.5) F next to J17; CH224K U23 (73.5, 70.5) B under J17 | + C79, C80, R84, R85 |
| Regulators | B | under cell 1, one column each: U3 (50.5, 13), U4 (56, 13), U5 (66, 10.5) with L1–L3 | + input/output caps, feedback RA/RB/Cff, RP1–RP3 net-tie jumpers |
| ADC + reference | B | under cell 3: U21 (61, 52), REF U17 (66.5, 52.5), LDO U20 (67, 56.5) – ≥ 6 mm from the J1 camera pins | + VADC/VREF decoupling, cell/VSYS dividers R24–R26, R36, R37, R39, R44, R45 + filter caps, NTC pull-ups R43/R60/R61 + C62/C82/C83 |
| Backlight boost | B (+F) | right of J7: U8 (53.9, 63.3), L4 (58.2, 63.2), D1 (57.7, 70.8) in the gap J7–H4; C38 (1206, 1.6 mm) on F directly above | + R18, R19, C37, C74, C75 |
| IMU | F | U22 on the optical axis (42.5, 37.5), rot 0 (X/Y = board X/Y) | C76–C78, R76, R77 ring |
| Power-on / wake / shutdown logic | F | bottom band below J1, x 38–61 | Q1, Q2, D10–D17, D27, R1–R8, R10, R13, R66, C13, C14, C60, D11, D12 |

**Battery NTCs (TH1–TH3, one per cell, read by U21 via `TEMP_BAT_CELL1–3`)** *(moved to the cell centres in 4.10)*: on the back at x 10, y 23.4 / 43.9 / 64.4 – directly beside each − spring (MY-18650-05-J; its courtyard covers x 3.8–18 so nothing can sit under the coil), 6.5 mm below its own cell axis. The NTC's second pin is GND, the same copper as the spring tab: pour GND from the spring tab to the NTC pad (short and wide) so the cell's − cap heats the NTC through the spring and tab. All three sit left of the U1 ball field (x < 12.7) so FPGA heat does not bias them; TH1 is under the SDRAM edge (low power). This replaces the 4.4 single-NTC thermal-pad spot at (36, 37.5).

- **Still staged off-board:** FPGA/SDRAM decoupling and rail caps (C16, C17, C19, C20, C25–C35, C47–C53, RV2, RV3 – go on B under U1/U2 with the BGA fan-out), RTC group (U7, Y2, C54–C57, R65, BAT1), flash/config, camera, ESP32 support (B3, B4 …), LEDs D53/D54, AE1, servo J_SRV1–6 + R78–R83 (last).
- DRC: no courtyard, keep-out, edge, short or inter-part clearance violations; remaining items are inside fine-pitch footprints + silkscreen. Parity unchanged (5 SD1 pins).

#### 4.9 Decoupling + local bulk caps (2026-11-07, not routed)
- Every cap placed against the power pin it serves (search over both sides and 4 rotations, cost = cap power pad to the nearest *unserved* pin of that net + 0.3 × GND pad to the IC's nearest GND pin, so caps spread over a BGA's supply balls). No IC or locked part moved.
- **U1 ECP5:** all caps on the back inside the ball field – +1V1 C27, C28 (+ C17 2.2 µF), +2V5 C29, C30 (+ C19), VCCIO `2V5_3V3` C26, C48, C49, C53 (+ C47), +3V3 C25, C31, C32, C50, C51 (+ C20); RV2/RV3 (VCCIO select) beside them. Small caps 0–2 mm from their ball, bulk ≤ 6 mm. `BAY_RIB_1` crosses under U1 (y 26.4–28.2) and stays empty.
- **U2 SDRAM:** C33 on B, C34/C35/C16 on F in the 3 mm strip between U2 and the BT12 tab, C52 on F right of U2 (the BT12 spring courtyard and B0 block most of the back under U2).
- **New in the schematic:** **C84** 100 nF 0402 (C1525) for the config flash U10 (`flash` sheet) and **C85** 100 nF 0402 for the 25 MHz oscillator Y1 (`usb` sheet) – neither had a local cap. Both on B directly under their supply pin; footprints added to the PCB with schematic links (parity clean).
- Re-targeted from the 4.8 satellite pass to the actual pins: TP4056 input caps C39/C41/C43 (+5V, VCC pin) and BAT caps C40/C42/C46; display logic caps C74/C75 to J7's +3V3 pins; CH224K VDD cap C79.
- Others: ESP32 C21 under the module's 3V3 pin; camera C18 (F) / C36 (B) at J1's 3V3 pin; SD supply R38 + C15 at SD1.
- **Coverage (worst pin → nearest same-net cap):** U1 ≤ 6.5 mm (+2V5 corner ball), all other U1 rails ≤ 4 mm; U2 ≤ 6.5 mm; U9 0.7; U10 0 (C84); Y1 4.5 (second +3V3 pin; C85 is at the VDD pin); IMU 3.5; ADC/REF/LDO ≤ 3; regulators 2.1; boost 2.5; TP4056 VCC 0.2 (CE pin tied to +5V ~6 mm); CH224K VDD 0.03; J7 1.8; J1 2.3; SD1 2.4. LM66100 VBAT_OR outputs (U12/U14) are 10 mm from C73 – a shared OR-bus with 100 µF + 10 µF bulk, no per-device cap needed. J4 (DNP header) has none.
- DRC: no courtyard, keep-out, edge, short or inter-part clearance violations; ERC unchanged (153); parity unchanged (5 SD1 pins).

#### 4.10 Remaining parts + servo headers – all 250 footprints on the board (2026-11-07, not routed)
- **Battery NTCs moved to the middle of each cell** (supersedes 4.8): TH1 (47.6, 20.0), TH2 (47.6, 37.5), TH3 (47.6, 58.0) on B – midway between spring tip (x 18) and button (x 77.2), on the cell axis (TH1 is 3 mm off-axis: the regulator column sits on cell 1's axis). Couple each to its can with the 2 mm compressible thermal pad from 4.4 (≈ 5 × 5 mm); keep 3 mm around each NTC free of other parts. Shorter `TEMP_BAT_CELLn` runs to U21.
- **Status LEDs** D53/D54 on F at the top edge (25 / 27, 2.5) with R69/R70 – as locked in 4.1.
- **RTC:** CR1225 holder BAT1 on F top-centre (43.5, 13.2), between U10/J4 and the ESP32, outside the camera module; MCP7940 U7 (34.5, 36.5) and 32 kHz Y2 (39.7, 30.2) on F under the camera module (≤ 6 mm parts allowed there), C54–C57, R65 beside; I²C pull-ups R74/R75 at U7. ⚠ BAT1's metal holder ends ≈ 2–3 mm left of the ESP32 antenna keep-out – check RF; alternative is BAT1 on the bottom-left once the servo block is dropped.
- **Pull-ups / small parts:** flash/config R11, R12, R27–R33, D28, D29 next to U10 / under U1 (B); camera R7, R14–R17 at J1; ESP32 strapping R34, R35, C81, R56 at U9; SD_CD R86 at SD1; button pull-ups R67/R68; 433 MHz pad AE1 at U1.
- **ESP32 BOOT/RESET** B3 (16, 49) and B4 (7, 27.5) on F left side (tall 4.3 mm parts; outside the camera module; press through case pin-holes). Native USB programming does not need them.
- **Servo headers J_SRV1–6 (DNP):** one ganged 3 × 6 grid at 2.54 mm pitch on F, (20.5–33.2, 58) between Y1, SD1, J1 and H3, series resistors R78–R83 beside. This was the only spot with both sides free for through-hole pins outside the camera module. The headers' courtyards overlap by design (butted 2.54 mm bodies) → **5 expected `courtyards_overlap` DRC items**. Under cell 3 on B: if ever fitted, trim the pin tails to ≤ 1.5 mm (cells sit 2.5 mm above the PCB).
- No test points in the schematic besides AE1; mounting holes unchanged (H1, H3, H4; H2 excluded). Camera-module M2 standoffs still to reserve once the module is measured.
- DRC: no keep-out, edge, short or inter-part clearance violations; courtyard overlaps only inside the servo gang; remaining mask/clearance items are inside fine-pitch footprints; silkscreen overlaps to clean up. Parity: only the 5 SD1 pins. ERC unchanged.

#### 4.11 Routing step 1 – JLCPCB rules, planes, fan-out, decoupling (2026-11-07)
**Fab rules (JLCPCB 4-layer, high reliability):** default track/space **0.15 / 0.15 mm**; fine-pitch exceptions in `FCL.kicad_dru` – **0.10 / 0.10 mm** inside rule area `U1_BGA` (ball field + 0.6 mm) and on the pads of the 0.5 mm-pitch parts (U2, U21, U22, U23, U24, J7, J17, LM66100s); mask expansion **0.05 mm**, minimum mask web **0.10 mm** (U22 LGA: footprint mask margin 0 – 0.15 mm pad gap); hole-to-hole **0.5 mm**, copper-to-edge 0.5 mm; vias 0.6/0.3 (default) and 0.4/0.2 (BGA / FAST); text ≥ 0.8 mm / 0.15 mm.
**Stackup JLC04161H-7628 (1.6 mm):** L1 35 µm · 7628 prepreg 0.2104 mm (εr 4.4) · L2 15.2 µm · core 1.065 mm · L3 15.2 µm · 7628 prepreg 0.2104 mm · L4 35 µm; HASL lead-free. Order with 1 oz inner copper if the price allows (planes carry the rails).

**Net classes (IPC-2152, 1 oz outer, ~10 °C rise):**

| Class | Nets | Track | Clearance | Via |
|---|---|---|---|---|
| PWR_HIGH (≈ 3 A) | `VBUS_C`, `+5V`, `VSYS`, `VBAT_OR` | 1.0 mm (or pour) | 0.2 | 0.6/0.3, ≥ 3 per layer change |
| PWR_CELL (≈ 1–1.5 A) | `CELL*_RAW`, `VBAT1–3` | 0.8 mm | 0.2 | 0.6/0.3, ≥ 2 |
| PWR_SW | `L1–L3`, `LCD_BL_SW` | 0.6 mm, short | 0.2 | – |
| USB | `USB_DP/DN`, `USB_C_DP/DN`, `USB_FPGA_D±` | 0.2 mm pair, 0.15 mm gap (≈ 90 Ω) | 0.2 | 0.6/0.3 |
| ANALOG | `*_SENSE`, `TEMP_BAT_CELL*`, `VREF_2V5`, `VADC` | 0.2 mm | 0.2 | 0.6/0.3 |
| PWR_RAIL | `+3V3`, `+1V1`, `+2V5`, `2V5_3V3`, `P1V1/P2V5/P3V3`, `SD3V3`, RTC `VBAT`, `LCD_BL_A/K`, `PD_VDD` | 0.4 mm | 0.15 | 0.6/0.3 |
| FAST | `SDRAM_*`, `SD_CLK/CMD/D0–3`, `CLK_25MHz`, `CAM_XCLK`, `GP*`, `GN*` | 0.15 mm | 0.15 | 0.4/0.2 |
| Default | everything else | 0.15 mm | 0.15 | 0.6/0.3 |

**Planes:** L2 `GND_L2` solid over the whole board (one island). L3 `3V3_L3` main plane (priority 0) + `1V1_U1_core` island over the 20 core balls (priority 2) + `VSYS_powerpath` band x 66–77.6, y 27.5–66 over the charger / power-path block (priority 1, clear of RP3's +3V3 output, the ESP32 and the ADC's +3V3 cap). **+2V5 has no island:** its four balls (F6, F15, P6, P15) are the corners of the core ring with +3V3 and VCCIO balls between them – an island would cut those off the +3V3 plane, so +2V5 (VCCAUX, low current) and VCCIO `2V5_3V3` are routed as tracks in the power pass. Antenna keep-out stays free of copper.

**U1 fan-out (dogbone, 0.4/0.2 vias, interstitial, outward quadrant first):** 90 power/GND balls with their own via, 55 more power/GND balls joined to a same-net neighbour (B-side decoupling occupies some via sites), 91 inner signal balls with vias, 43 signal balls on the two outer rings left to escape on L1, 68 NC. **Still without a via (for the routing passes):** 16 power balls – VCCIO `2V5_3V3` H6, H7, J6, F9, F10 (fed by tracks), +2V5 F6, +3V3 F11, F12, GND J2, G4, R4, B7, D4, K6, J7, K7 – and 26 inner signal balls (listed in the run log; they need a via site freed or an L1 escape).

**Decoupling / IC fan-out:** every IC power and GND pin that sits on a plane net got a via beside it (U2, U9, U10, U21, U22, regulators, chargers, LM66100s, U23, U24, Y1, J1, J7, SD1, J17), exposed pads got 2 × 2 GND via arrays (TP4056s already carry thermal vias); each cap got its own GND via and a straight / L-shaped / cross-side connection to its pin. **62 of 69 decoupling/bulk caps fully connected.** Open (power pass): C17 (+1V1 bulk), C19/C29/C30 (+2V5), C26 (VCCIO GND side), C51 (+3V3, under U1), C70 (ADC REFIN). Filter / timing caps (sense filters, crystal load caps, RC on SHUT/PWRBTn) are left for the analog pass.
- **Power stubs widened to their class** (38 tracks): VBAT1–3 0.3–0.4 → 0.6–0.8 mm, +5V / VBAT_OR / VSYS 0.3–0.4 → 0.6–1.0 mm, VBUS_C → 0.54 mm (pad-limited), +3V3 / SD3V3 → 0.4 mm; capped at the landing pad's width, stepped down only where clearance required. Stubs inside `U1_BGA` stay 0.2 mm. New tracks drawn in KiCad pick up the class width automatically (router: *Use net class values*).
- ⚠ **Edit the rules with KiCad closed:** the open project overwrote `FCL.kicad_pro` once (net classes, patterns, pre-defined sizes lost) and was restored from git. Net classes appear in *Board Setup → Net Classes*, the pattern table in *Netclass Assignments*, and the 0.1–1.5 mm track / 0.4–0.8 mm via presets in *Pre-defined Sizes*.
- Result: 351 vias (223 × 0.4/0.2, 128 × 0.6/0.3), 448 short tracks, all in group `FANOUT_5_1`. DRC: **no clearance, mask-bridge, short, hole or edge violations**; 91 `via_dangling` = U1 signal fan-out vias awaiting routes; silkscreen + 5 servo-gang courtyard items as before. Parity: 5 SD1 pins. ERC unchanged (153).

#### 4.12 Routing step 2 – high-speed nets (partial, 2026-11-08)
- Routed with a scripted grid maze router (A*, 0.1 mm grid, net-class widths/clearances, BGA 0.1 mm escape, rip-up and re-route) – no autorouter. Copper in group `ROUTE_2_HIGHSPEED`; DRC-pruned (no clearance / hole / short violations).
- **Fixes made on the way:** `FCL.kicad_dru` was silently ignored by KiCad 10 (rule values need explicit `mm` units) – rewritten, the BGA and fine-pitch exceptions now apply in DRC; ESP32 RESET **B4 moved to (7, 44.5)** to open the corridor left of U1; SDRAM decoupling **C34, C35, C16 moved to the back under U2** (they walled in U2's left pin row) and reconnected.
- The inner layer In2 (+3V3 plane) is used for some bus segments where F/B ran out; the +3V3 plane is still one island.
- **Routed:** USB (J17 → U24 → ESP32), 25 MHz clock, part of the SDRAM bus, part of the camera/LCD `GPn/GNn` bus.
- **Still open (59 nets):** most of the SDRAM bus (A0–A3, A6, A10, A11, BA0/1, CKE, nCS/nRAS/nCAS/nWE, DQM0/1, D1, D3–D6, D9–D11, D13, D15), the SD bus (SD_CLK/CMD/D0–D2) and ~28 camera/LCD `GPn/GNn` nets.
- **Root cause:** placement. With U1 at 180° all 39 SDRAM balls face **left** (toward the board edge and the spring tabs), while U2 sits above U1 – the bus has to squeeze through a ~3.5 mm corridor (≈ 11 tracks per layer). The original 4.1 plan (U1 rotated so the SDRAM bank faces down, U2 below U1) avoids this. Recommended before finishing these buses: either restore that orientation (and redo the U1 fan-out), or finish the buses with KiCad's interactive push-and-shove router.

#### 4.13 Routing step 3 – power paths (2026-11-08)
- Groups `ROUTE_3_POWER` / `ROUTE_3_POWER_B`. Power nets routed at their class width (PWR_HIGH 1.0, PWR_CELL 0.8, PWR_SW 0.6, PWR_RAIL 0.4 mm), necking only where a pad forces it, 0.6/0.3 vias; every pad on a plane net (GND, +3V3, +1V1 island, VSYS band) that was not yet on its plane got a short stub + via. Planes still one island each. DRC clean (no clearance / short / hole items).
- Unconnected items 447 → 282.
- **Still open (36):** +2V5 ×5 and VCCIO `2V5_3V3` ×5 (BGA balls F6/F15/P6/P15, H6/H7/J6/F9/F10 with no via site – need the fan-out reworked under U1), GND ×9 / +3V3 ×8 / +1V1 ×1 (mostly balls and caps under U1 with no free via site), `VBUS_C` ×4 and +5V ×2 (J17 / D55 / U16 area), VBAT_OR ×1, P1V1 ×1.

#### 4.14 Routing step 4 – analog and sensing (2026-11-08)
- Group `ROUTE_4_ANALOG`: RTC crystal (OSCI/OSCO), regulator feedback, ADC reference / supply, part of the cell / VSYS sense dividers and NTC lines, IMU + RTC I²C where space allowed. ANALOG class 0.2 mm / 0.2 mm clearance. DRC clean, planes one island each. Unconnected 282 → ~270.
- **Still open:** long cross-board runs – `TEMP_BAT_CELL1–3` (NTCs at x 47.6 to U21 on the right), `VBAT1–3_SENSE`, `VSYS_SENSE`, `VREF_SENSE`, `VADC` ×3, `FB1/FB2`, U21 REFIN, IMU I²C / INT and RTC I²C (`FPDI_*`) to U1. These cross the camera/IMU zone and the congested left half; they need the high-speed buses settled first.

#### 4.15 Routing step 5 – low-speed nets, test vias (2026-11-08)
- Group `ROUTE_5_LOWSPEED`: second pass over every remaining net (buttons, LEDs, flash/config, JTAG, ESP32 strapping, power-on logic, servo PWM, CC lines, plus retries of earlier failures) with rip-up. DRC clean (no clearance / short / hole violations), planes one island each.
- **Unconnected items: 492 (before routing) → 197.** 134 nets still have at least one open connection: most of the SDRAM bus, the SD bus, ~26 camera/LCD `GPn/GNn`, ESP32↔FPGA (`WIFI_*`, JTAG), flash/config straps, the long NTC / sense lines to U21, IMU / RTC I²C, servo PWM, and the +2V5 / VCCIO / some GND and +3V3 balls under U1.
- **Test vias on unused FPGA balls:** only 4 fit (group `TESTVIAS_UNUSED_FPGA_IO`, 0.4/0.2, untented). The other 54 NC balls have no free via site – the BGA area is full.
- **Assessment:** the board does not close with this placement on 4 layers. The decisive problem is U1's orientation (SDRAM bank facing the board edge, U2 above) plus the camera/LCD bus leaving the bottom-left; together they saturate the left half. Recommended next step: restore the 4.1 placement intent (U1 rotated so SDRAM faces down, U2 below U1, camera bank toward J1), redo the U1 fan-out, then re-run steps 2–5 – or finish interactively in KiCad (push-and-shove) starting from this state.

#### 4.16 Step 6 – silkscreen (2026-11-08)
- Reference designators 0.8 mm (1.0 mm on large parts), 0.15 mm stroke, centred, on the part's own side (mirrored on B), placed at the nearest spot that clears pads, exposed vias, other refdes and the board edge; values hidden.
- **207 refdes on silkscreen** (95 front, 112 back). **45 kept on the Fab layer only** (no free silk area – mostly 0402/0603 caps under U1 and in the dense power block): C8, C10, C11, C25–C29, C31, C32, C37, C47–C53, C59, C61, C66, C68, C70, C72, C82–C84, D3, D11, D12, D53, R1, R43, R45, R51, R55, R60, R66, R67, R71, R83, RA1, RA2, RV3, U14 – use the assembly drawing (Fab) for those.
- Silk DRC: silk_overlap 199 → 81 (footprint outlines touching neighbours), silk_over_copper 143 → 12, silk_edge 7 → 2.

#### 4.17 ULX3S FPGA/SDRAM core staged off-board (2026-11-08)
- The ULX3S reference layout (board before Phase 4, commit `7a6d82ec`) has the same U1/U2 parts and an **identical SDRAM pin-to-net mapping (78/78)**. Its core is copied **above-left of the outline** (U1 at page (30, 22)), in the **original orientation**: U1 0°, U2 90°, 26.6 mm to the right of U1.
- **Moved to the staging area** (same refdes and nets as the reference, so no renames were needed): U1, U2, C16, C17, C19, C20, C25–C34, D28, D29, R31–R33.
- **Copied (group `ULX3S_CORE_COPY`):** all SDRAM routing, the BGA fan-out / escapes and decoupling connections, the +1V1, +2V5 and 2V5_3V3 islands. Copper only copied where the net exists in our design and lands on a pad of the same net; copper on nets we no longer use (FTDI, ULX3S buttons, unused GP/GN, FPGA USB) dropped.
- **Stackup now matches the reference:** In1 = +3V3 plane + VSYS / +1V1 / +2V5 / 2V5_3V3 islands, In2 = GND (all inner tracks and zones swapped). Zones unfilled.
- Our old U1/U2 dogbones, decoupling stubs and the old `1V1_U1_core` island removed. `U1_BGA` rule area moved with U1; new rule area `ULX3S_CORE` + custom rule (clearance 0.127 mm, hole-to-hole 0.3 mm, hole clearance 0.15 mm) for the reference geometry.
- **Regulator blocks staged too:** 1V1 (U3, L1, C2–C5, C22, RA1, RB1, RP1) and 3V3 (U5, L3, C6–C9, C24, RA3, RB3, RP3) at their reference positions beside the core; reference copper copied with `+5V` → `VSYS` (the only net difference). RP1/RP3 keep our net-tie footprint (3 solder-mask-bridge items where the reference tracks enter it differently). `ULX3S_CORE` rule area extended over them.
- DRC: one 0.125 mm hit (C27 GND pad vs a +3V3 via), 8 courtyard overlaps between the reference's tightly packed caps under the BGA, 147 dangling escape stubs (the ULX3S escapes continue outside the copied window). Next: decide where the core goes on the board and integrate.

#### 4.18 Step 1 – ULX3S core placed on the board (2026-11-08)
- Staged core rotated **90° clockwise** as one unit (parts, copied copper, islands, rule areas): **U1 at board (28, 11.2), U2 below at (28, 37.8)** – SDRAM bank faces down to U2, camera/LCD bank faces right (J1 / IMU), ESP32/SD banks face up.
- Regulator blocks placed separately on B by search (clear of ribs/springs, switchers ≥ 15 mm from the IMU, near the core): **1V1 block (U3) at (41, 15)**, **3V3 block (U5) at (45, 61)**, each with its copied copper.
- B0/B1/B2 stay put: the three core parts that would have hit them (R32, R33, C30) and the three on the bay ribs (C16, D28, D29) were parked instead, their copied stubs dropped.
- **Parked off-board (right of the outline) for step 2:** AE1, BAT1, C1, C14, C16, C30, C48, C51, C52, C54, C84, D12, D14, D15, D28, D29, D53, D54, R7, R11–R13, R18, R27–R29, R32, R33, R66–R70, R75, R80, U7, U8, U10, Y1.
- Our copper inside the new areas removed; conflicting copied escape stubs removed (policy: ours yields to copied SDRAM/core copper, copied stubs yield to our parts). DRC: no clearance / short / hole / edge / keep-out items; remaining courtyard overlaps are the reference's tight cap packing + the servo gang; dangling items are escape stubs and plane vias (zones unfilled).

#### 4.19 Step 1 redone – core rotated 180° from the reference, per the owner's mock-up (2026-11-08)
- Supersedes the 4.18 placement. Block = reference geometry turned 180°: **U1 at board (45.5, 17) rot 180°, U2 at (18.9, 17) rot −90° (horizontal), 26.6 mm left of U1** – the copied SDRAM routing stays valid.
- Signal flow: SDRAM → left into U2; camera/LCD bank → down to J1 (directly below) and J7; ESP32 / SD banks → right, ESP32 alongside. Of 80 FPGA signals with on-board targets only 23 need to route backwards (was 37), 3214 mm straight-line total (was 3552).
- Raised from the mock-up's y 28.8 to **y 17** so the BGA (ball field y ≈ 8.5–25.5) clears bay rib 1 (y 26.4–28.2) and the IMU stays on the optical axis ~12 mm below U1. U2's left end clears the cell-1 spring tab; B0–B2 untouched.
- U1 overlaps the ESP32 footprint's courtyard only (the library courtyard includes the RF clearance band to x = 42; module body starts at x = 56.6, antenna keep-out y < 6.6 is respected).
- Regulator blocks re-placed on B: **1V1 (U3) at (59, 43)** between the bay ribs, **3V3 (U5) at (45, 61)**; switchers ≥ 15 mm from the IMU. The +1V1 feed to the core island now needs a ~30 mm path (step 2).
- `ULX3S_CORE` rule area split into three tight areas (core, 1V1 block, 3V3 block) so the 0.127 mm reference rule does not override the fine-pitch exception on nearby parts.
- Parked off-board for step 2: AE1, BAT1, C1, C14, C16, C30, C45, C48, C51, C52, C54, C81, C84, D12, D14, D15, D28, D29, D53, D54, J4, R7, R11–R13, R18, R24, R25, R27–R30, R32, R33, R35, R66–R70, R75, R80, TH1, U4, U7, U8, U10, Y1.
- DRC: no clearance / short / hole / edge / keep-out items; courtyard overlaps are the reference's tight cap packing + servo gang; dangling items are escape stubs and plane vias. Zones unfilled.

#### 4.20 Step 1, final – core lowered between the bay ribs (2026-11-08)
- Supersedes 4.19. Same orientation, moved down ~one FPGA width: **U1 at (45.5, 37.5) rot 180°, U2 at (18.9, 37.5) rot −90°**. Frees the ESP32's left pin column and the top of the board; the BGA ball field (y ≈ 29–46) sits between bay ribs 1 and 2, no back-side core parts on a rib; the camera bank is ~4 mm above J1.
- **IMU moved off the optical axis** (owner OK; pins can be swapped later): U22 + C76–C78, R74, R76, R77 parked, to be placed above U1 near (45, 18) in step 2. Regulator search used that spot for the 15 mm switcher quiet zone.
- Regulators on B: **1V1 block (U3) at (26, 20)** next to the core, **3V3 block (U5) at (45, 61)**.
- **SDRAM routing re-copied in full from the reference** with the exact 180° transform (U2 position check 0.000 mm): 334 tracks + 24 vias, **all SDRAM nets connected**. (A first attempt lost SDRAM pieces to a bad copper classification; redone from a3929f60.)
- Orphaned copied copper (pieces touching no pad after the moves) removed. `ULX3S_CORE` rule areas re-split (core / 1V1 / 3V3).
- Parked off-board for step 2 (adds to 4.19): B3, B4, C55–C57, R15, R65, RV3, TH2, Y2 and the IMU group.
- DRC: no clearance / short / hole / edge / keep-out items; courtyard overlaps = reference cap packing + servo gang; dangling = escape stubs and plane vias. Zones unfilled.

#### 4.3 Phase 4 checklist
- [x] Optical axis, outline, zone placement and edge assignment locked (4.1)
- [x] Footprint-link issues fixed; BT11–BT32 footprints added; J2/J6/H2 excluded from board
- [x] 85 × 75 outline, holes, axis marker, camera / cell / TFT reference outlines; antenna keep-out from the ESP32-S3 footprint
- [x] Major mechanical items placed (4.2)
- [x] Update PCB from Schematic (4.5); fallback/obsolete parts excluded from board; RP1–RP3 as net-tie jumpers
- [x] Rough functional placement of all parts into the 4.1 zones (4.5)
- [ ] Measure: NHD TFT outline / FPC (datasheet p.3), OV7670 lens-to-header offset → adjust J1 / J7
- [x] Battery bay geometry on the PCB: contact pitch 20.5 mm, cell-length window, bay rule areas, NTC thermal pad, IMU quiet zone, stress list (4.4)
- [ ] Confirm spring free/solid length and contact plate dimensions on the MY-18650-04/05-J drawings; bay CAD (ribs, end walls, J7 bridge, boss)
- [x] Fine-pitch design rules, net classes, JLC stackup, planes, BGA fan-out, decoupling (4.11)
- [ ] Placement refinement: TP4056 thermal spread, decoupling under the BGA, short CAM_PCLK / LCD_PCLK, silkscreen
- [ ] 3D-print case concept

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