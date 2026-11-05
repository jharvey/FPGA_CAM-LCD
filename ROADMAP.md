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
| 1 | Branch created, cleanup started | In progress |
| 2 | Power input redesign (3×18650 + monitoring) | **Mostly done** |
| 3 | Camera + display connectors / sheets | Pending |
| 4 | PCB mechanical outline (monocular form) | Pending |
| 5 | BOM / JLCPCB / first prototype | Pending |

---

## Decisions (locked)

- Full single PCB (not shield)
- Keep ECP5-85F, SDRAM, flash, USB, WiFi (ESP32), SD card
- Remove GPDI, large GPIO headers, audio
- 3 independent 18650 cells with ideal-diode OR-ing (LM66100), hot-swap capable
- Per-cell reverse-polarity protection (AO3401A) + TP4056 chargers
- Per-cell voltage sensing via ADS1115 (I²C shared with ESP32/FPGA)
- ADS1115 powered from a small always-on 3.3 V LDO fed from VSYS (correct I²C levels even when USB is present)
- ST pins of all LM66100s tied to GND through 0 Ω links (removable later)
- VSYS = OR of (VBAT_OR + USB 5 V)
- Soft-shutdown path (Q2 / SHUT) retained
- Individual cell enable/control (CE pins) planned so the most-depleted cell can be consumed first (firmware-driven, later)
- Bulk capacitance after ideal-diode OR-ing for contact bounce / vibration
- Optional later boost stage to recover the bottom ~5–15 % capacity once cells fall below ~3.5 V
- Camera: OV7670 parallel + SCCB
- Display: NHD-2.1-480480AF-ASXP (40-pin FFC, RGB + SPI)
- Case: 3D-printed first → metal later

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
- [x] ADS1115 (0x48) on WIFI_GPIO21/22 with 47 kΩ/150 kΩ dividers + 10 kΩ NTC
- [x] ADS1115 powered from dedicated always-on 3.3 V LDO from VSYS
- [x] ST pins of all five LM66100s linked to GND via 0 Ω (removable)
- [x] TLV62569 inputs and wake circuit moved to VSYS
- [x] LCD backlight boost input renamed to VSYS
- [ ] Break out / control LM66100 CE pins for true “most-dead-first” sequential discharge (firmware later)
- [ ] Expose TP4056 CE / status pins if desired
- [ ] Add bulk capacitance on VBAT_OR / VSYS for vibration robustness
- [ ] (Optional later) Boost stage to extract remaining capacity below ~3.5 V
- [ ] Final ERC clean-up and visual layout review of the new power area

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

---

## Power architecture notes (current)

- Cell negatives common (GND). Positives individual (CELLx_RAW → VBATx after reverse FET).
- VSYS powers the main regulators and the LCD boost. CR1225 VBAT is unrelated.
- 3.3 V rail needs ≥ ~3.4 V on VSYS → practical cutoff ≈ 3.5–3.6 V on the highest cell.
- ADS1115 shares I²C with ESP32/FPGA; firmware must use ±4.096 V range.
- CHGx LEDs are local only; charger enable/status not yet routed to a processor.
- Ideal-diode OR-ing currently prefers the highest cell. True sequential “dead-first” requires CE control.

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
- Next power-related work: CE pin control for sequential discharge + bulk caps + final ERC/layout polish.