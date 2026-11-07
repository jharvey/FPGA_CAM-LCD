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
| 2 | Power input redesign (3×18650 + monitoring) | **Core done** – 3 open items (ADC ref loading, CE breakout, KiCad ERC pass) |
| 3 | Camera + display connectors / sheets | **Schematic done** – 5 open decisions before layout (see Phase 3) |
| 4 | PCB mechanical outline (monocular form) | Pending |
| 5 | BOM / JLCPCB / first prototype | Pending |

---

## Decisions (locked)

- Full single PCB (not shield)
- Keep ECP5-85F, SDRAM, flash, USB, WiFi (ESP32), SD card
- Remove GPDI, large GPIO headers, audio
- 3 independent 18650 cells with ideal-diode OR-ing (LM66100), hot-swap capable
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
- **Near-term**: Add USB-C PD sink / trigger chip that requests highest available **5 V** current (ideally 3 A). Keeps existing TP4056 linear chargers.
- **Longer-term**: Evaluate higher-voltage / higher-wattage PD path (9–20 V) together with switching chargers or a multi-cell charger IC for significantly higher total charge power.

### Sensors (longer-term)
- Add IMU (e.g. ICM-42688, BMI270, or similar) for orientation / motion sensing once core power + camera + display are stable.

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
- [x] Per-cell: JST-PH (placeholder), AO3401A reverse protection, TP4056 charger, LM66100 ideal diode
- [x] VBAT_OR + USB → VSYS via additional LM66100s
- [x] ~~ADS1115 (0x48) on WIFI_GPIO21/22~~ – superseded by AD7689 (below)
- [x] Always-on 3.3 V LDO from VSYS for the ADC (U20 XC6206 → VADC)
- [x] ST pins of all five LM66100s linked to GND via 0 Ω (R46, R47, R48, R51, R55)
- [x] TLV62569 inputs and wake circuit moved to VSYS
- [x] LCD backlight boost input renamed to VSYS
- [x] **Replace ADS1115 with 8-channel ADC** – U21 AD7689BCPZ, SPI to ESP32: SDO=WIFI_GPIO19, DIN=WIFI_GPIO21, SCK=WIFI_GPIO22, CNV=WIFI_GPIO26
  - IN0–IN2: VBAT1–3 via 47 k / 56 k dividers (4.2 V → 2.28 V), 100 nF filter caps
  - IN3: TEMP_BAT, 10 k pull-up (R43) + 10 k NTC (TH1)
  - IN4: REF3025 (U17) output – absolute-reference cross-check
  - IN5: VSYS_SENSE via 100 k / 68 k (5.25 V → 2.13 V)
  - IN6, IN7 spare and COM tied to GND via 0 Ω (R57, R58, R59) – lift to use
- [x] Add resistor divider for +V / VSYS rail sensing into the new ADC (R44/R45 → IN5)
- [x] Absolute reference / non-ratiometric: AD7689 internal 2.5 V reference (REF + 10 µF C68, REFIN + 100 nF C70). Firmware must set CFG.REF = internal 2.5 V.
- [ ] **Review ADC reference loading**: the NTC pull-up R43 is fed from the AD7689 REF pin (DC load on the conversion reference), and REF3025 is only measured, not used as the reference. Options: (a) feed R43 from REF3025 OUT (VREF_SENSE), or (b) drive REF from REF3025 and use external-reference mode. Needs a wiring change on the power sheet – decide before layout.
- [x] Bulk capacitance: VBAT_OR = C58 10 µF + **C73 100 µF 1210 (CL32A107MPVNNNE, LCSC C23742)**; VSYS = 3× 22 µF (C1/C5/C9) + C63 10 µF. Revisit at layout (X5R DC-bias derating).
- [ ] Break out / control LM66100 CE pins for true “most-dead-first” sequential discharge (firmware later). Currently CE = VOUT (plain ideal-diode OR). Needs a GPIO / IO-expander decision.
- [ ] Expose TP4056 CE / ~CHRG status (currently CE tied to +5 V, ~CHRG drives LEDs only)
- [x] Schematic clean-up: 4 dangling wire stubs fixed (PWREN ×3, VBAT1)
- [ ] Final KiCad ERC run + visual review of the power area (remaining known items: unused ADS1115 symbol in the power-sheet library cache – drops on re-save; orphan ADC_SCLK/ADC_MOSI/ADC_CSn/ADC_MISO global labels on `ram` from the removed MAX11123 analog sheet – ask before removing)
- [ ] ~~Add USB-C PD sink/trigger chip~~ → moved to **Phase 2b** (below)
- [ ] (Optional later) Boost stage to extract remaining capacity below ~3.5 V

### Phase 2b – USB-C 5 V PD trigger (deferred, not started)
- [ ] Add USB-C PD sink/trigger chip requesting max 5 V current (preferably 3 A); keep TP4056s
- Higher-voltage / higher-wattage PD stays under *Later / stretch goals*

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

**Open before Phase 4 (schematic decisions)**
- [ ] **CAM_PCLK on a clock pin** – CAM_PCLK (`GP16`, N16) is plain I/O; CAM_PWDN (`GP17`) occupies GR_PCLK3_0 (L16). Recommend swapping the two labels on the `camera` sheet.
- [ ] **J6 legacy 2×20 header** – still fitted and on every camera net plus IN5V/OUT5V (D51/D52). Decide DNP (like J2) or keep for debug; D51/D52 follow that decision.
- [ ] **J5 VCCIO jumper (power sheet)** – 3-pin header across +2V5 / 2V5_3V3 / +3V3. With RV3 fitted, a jumper on 1–2 shorts +2V5 to +3V3 → mark DNP (or remove).
- [ ] **User I/O for the monocular** – orphan global labels on `fpga-io` from stripped ULX3S sheets: `SW1..4` (buttons), `LED0..7`, `AUDIO_*` (12). Decide which buttons / status LEDs the monocular needs (only B0 power button exists today); delete the rest and add no-connect flags (also U1 D9).
- [ ] **ERC clean-up** – `+5V` power-input not driven (#PWR015 on `fpga-io`, needs PWR_FLAG or goes away with the J6/D51/D52 decision). Remaining `multiple_net_names` warnings are the intentional `LCD_*`/`CAM_*` aliases.

**Verify (no schematic change expected)**
- [ ] U8 uses the `AP3019AKTR` symbol with value AP3032KTR-G1 – confirm identical SOT-23-6 pinout; confirm L4 4.7 µH against the AP3032 datasheet recommendation.
- [ ] J7 footprint is Hirose FH12-40S-0.5SH; NHD recommends Molex 54104 (datasheet lists both -4031 and -4096). Pick contact side (top/bottom) once the FPC fold direction is fixed in Phase 4.
- [ ] LCD VDD = +3V3 is at the panel's 3.3 V maximum (typ 3.0 V) – accepted, note only.
- [ ] ESP32 IO32/IO33 share LCD_SCK/LCD_DC – firmware must keep them Hi-Z.

**Sheet map (camera / display area)**

| Sheet file | Contents | Connects via |
|---|---|---|
| `display.kicad_sch` | J7 NHD-2.1-480480AF-ASXP 40-pin FFC, C74/C75 VDD decoupling, backlight boost U8 AP3032 (L4, D1, C37, C38, R18, R19) from VSYS | Global `GN0..13`/`GP0..13` (RGB, sync, SPI, reset), `GP13` (BL PWM), `+3V3`, `VSYS`, `GND` |
| `camera.kicad_sch` | J1 OV7670 2×9 header, SCCB pull-ups R7/R14, R15 XCLK series, R16/R17, C18/C36 decoupling | Global `GN14..17,21..24`/`GP14..17,21..24` (XCLK via `GN16`, net named `CAM_XCLK`), `+3V3`, `GND` |
| `fpga-io.kicad_sch` | U1 ECP5 bank units (BANK0/7 and BANK1 I/O), legacy ULX3S headers J2 (DNP) and J6, D51/D52 5 V links | Global labels to the sheets above |

Local labels (`LCD_*`, `CAM_*`) are descriptive aliases on each sheet; the `GN*`/`GP*` global labels carry the connections.

### Phase 4 – Mechanical & PCB
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
- *Batteries.* 3×18650 (Ø18.6 × 65 mm each, ≈ 56 × 65 mm side-by-side + holder walls) are
  off-board in case holders and connect through JST PH 2-pin J8 / J9 / J10. Place J8–J10 at the
  board edge facing the cell bay, near the reverse-FET / LM66100 input stage. The NTC must
  physically touch or sit next to the cells. Hot-swap needs a cell door that does not stress
  the PCB.
- *Edge-accessible parts.* US1 (FTDI micro-B, programming), US2 (OTG micro-B), the microSD
  slot (SCHD3A0100), B0 power button (PTS645), J3 WIFI_OFF, J4 JTAG 2×3, BAT1 CR1225 holder.
  The USB-C PD rework is deferred (Phase 2b / later), so leave edge room where US1 / US2 sit.
- *ESP32 antenna.* Board edge with copper keep-out under the antenna, away from the cells and
  any future metal case (the metal case will need an RF window).
- *Large / optional parts.* J2 (DNP) and J6 2×20 angled headers are ≈ 51 mm long; keep or drop
  per the layout space (J2 decision deferred to layout).
- *Mounting.* H1–H4 M3 holes exist but are still at ULX3S positions; re-place them for the case.
  Avoid putting tall or heavy parts (headers, inductors, cell connectors) at unsupported spans
  (vibration).

### Phase 5 – Prototype
- [ ] BOM with LCSC / JLCPCB numbers
- [ ] Gerbers + CPL
- [ ] First order

### Later / stretch goals
- [ ] Higher-voltage / higher-wattage USB-C PD path + switching or multi-cell charger (max charging power)
- [ ] IMU (orientation / motion)
- [ ] Firmware-driven cell prioritisation (CE control) using the new 8-ch ADC data
- [ ] Optional bottom-capacity boost stage

---

## Power architecture notes (current)

- Cell negatives common (GND). Positives individual (CELLx_RAW → VBATx after reverse FET).
- VSYS powers the main regulators and the LCD boost. CR1225 VBAT is unrelated.
- 3.3 V rail needs ≥ ~3.4 V on VSYS → practical cutoff ≈ 3.5–3.6 V on the highest cell.
- AD7689 8-ch ADC on SPI (WIFI_GPIO19/21/22/26, also routed to FPGA pins on the usb sheet). Internal 2.5 V reference; REF3025 measured on IN4.
- CHGx LEDs are local only; charger enable/status not yet routed to a processor (open item).
- Ideal-diode OR-ing currently prefers the highest cell. True sequential “dead-first” requires CE control.
- Near-term PD chip will request highest available 5 V current while keeping the existing TP4056s.

---

## What we keep from original ULX3S

- ECP5-85F + config flash + SDRAM
- USB (FTDI) programming / serial
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