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
| 3 | Camera + display connectors / sheets | In progress |
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
- [ ] Constraints note for later FPGA work

### Phase 4 – Mechanical & PCB
- [ ] Board outline for monocular (camera + TFT inline, batteries side-by-side)
- [ ] Placement for vibration robustness (NTC next to cells)
- [ ] 3D-print case concept

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