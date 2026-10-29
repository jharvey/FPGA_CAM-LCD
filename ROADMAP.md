# Monocular FPGA Vision Device – Roadmap

**Repo**: https://github.com/jharvey/ULX3S_FPGA_CAM-LCD  
**Branch**: `monocular-strip`  
**Base**: ULX3S open hardware (emard)  
**Goal**: Single-board monocular with ECP5 + OV7670 + Newhaven 2.1" TFT + 3×18650 + USB charging + WiFi + SD

---

## Current status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Architecture decisions locked | Done |
| 1 | Branch created, cleanup started | In progress |
| 2 | Strip unused sheets (GPDI, GPIO, analog, serdes) | Pending |
| 3 | Rework power input for 3×18650 | Pending |
| 4 | Add camera + TFT connectors / sheets | Pending |
| 5 | PCB mechanical outline (monocular form) | Pending |
| 6 | BOM / JLCPCB / first prototype | Pending |

---

## Decisions (locked)

- Full single PCB (not shield)
- Keep ECP5-85F, SDRAM, flash, USB, WiFi (ESP32), SD card
- Remove GPDI, large GPIO headers, audio
- 3 independent 18650 cells, sequential discharge, hot-swap
- Ideal-diode priority (LM66100 family preferred)
- USB charging (independent single-cell chargers)
- Voltage sense of each cell to FPGA
- Camera: OV7670 parallel + SCCB
- Display: NHD-2.1-480480AF-ASXP (40-pin FFC, RGB + SPI)
- Case: 3D-printed first → metal later

---

## Phase details

### Phase 1 – Branch & cleanup (NOW)
- [x] Create `monocular-strip` branch
- [ ] Update `.gitignore`
- [ ] Delete unused sheets: gpdi, gpio, analog, serdes (optionally blinkey)
- [ ] Remove corresponding hierarchical blocks from root sheet
- [ ] Commit: "strip unused ULX3S sheets for monocular"

### Phase 2 – Power input redesign
- [ ] On `power.sch`: identify and remove single-battery / old power-path input
- [ ] Keep 1.1 V / 2.5 V / 3.3 V regulators and support parts
- [ ] Add 3×18650 holders + LM66100 ideal diodes + sense dividers
- [ ] Add USB charging path (3× single-cell chargers)
- [ ] Document nets: VBAT_OR, VBATx_SENSE, +3V3, +2V5, +1V1

### Phase 3 – Camera & Display
- [ ] Add OV7670 connector / sheet
- [ ] Add 40-pin FFC for Newhaven TFT
- [ ] Map pins (reuse known mappings from existing projects)
- [ ] Constraints note for later FPGA work

### Phase 4 – Mechanical & PCB
- [ ] Board outline for monocular (camera + TFT inline, batteries side-by-side)
- [ ] Placement for vibration robustness
- [ ] 3D-print case concept

### Phase 5 – Prototype
- [ ] BOM with LCSC / JLCPCB numbers
- [ ] Gerbers + CPL
- [ ] First order

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