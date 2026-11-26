# FPGA_CAM-LCD: single-board FPGA monocular

A hand-held monocular on one PCB, based on a stripped ULX3S:

- Lattice ECP5-85F FPGA, SDRAM, flash, ESP32-S3 (WiFi, USB, programming), SD card
- OV7670 camera module on the scene side, Newhaven 2.1" round TFT (NHD-2.1-480480AF-ASXP) on the eye side
- Three 18650 cells, each hot-swappable through its own quarter-turn cap, plus USB-C charging
- 3D-printed case with a 1/4-20 tripod thread

## Where things stand (2026-11-26)

| Area | State |
|---|---|
| Schematic | Frozen, with later additions listed in `doc/constraints/schematic_freeze.md` |
| PCB | Routed. KiCad DRC: 0 errors, 0 unconnected (branch `merged-board`) |
| Battery end blocks | One common machined aluminium block at all three cells, MS3181-16 bayonet caps. Mounting-hole pattern still under review |
| Case | Draft 4 modelled (not printed yet): two shells, two cell cradles, snap-in buttons, camera screwed to the lid |
| Ordering | **Not ready.** See "Open before ordering" in `ROADMAP.md` |

## Branches

- `merged-board`: the newest board and case. Open `FCL.kicad_pro` here.
- `monocular-strip`: the long-running design branch. `merged-board` has not been merged back into it yet.
- `battery-blocks`, `j7-vertical-wip`: the two lines of work that were combined into `merged-board`. Kept for history.
- `master`: the original ULX3S files.

## Documents

| Document | What it covers |
|---|---|
| `ROADMAP.md` | Decisions, phase status, dated change log, open items |
| `AI_GUIDE.md` | Working rules for an AI assistant or a new contributor |
| `case/README.md` | How to print, assemble and regenerate the case; hardware list |
| `docs/mech/README.md` | Battery end block: machining drawing and editable models |
| `docs/mech/freecad/README.md`, `case/freecad/README.md` | The FreeCAD files |
| `doc/constraints/camera_display_pinmap.md` | FPGA pins for the display, camera and user I/O |
| `doc/constraints/schematic_freeze.md` | Schematic freeze record and what changed after it |
| `doc/jlc_check_2026-11-22.md` | JLCPCB build check (a dated snapshot; see the note at its top) |
| `fpga/IO_REMAP.md`, `fpga/ESP32_PINS.md` | FPGA and ESP32 pin maps |
| `mechanical.kicad_sch` | Mechanical bill of materials (screws, caps, springs, printed and machined parts) |

`doc/MANUAL.md`, `doc/MINIMAL.md`, `doc/TODO.txt` and the other files in `doc/` come from the original ULX3S project and describe that board, not this one.

## Phase order (do not skip)

1. Cleanup / hierarchy (done / finishing)
2. Power input redesign (3×18650)
3. Camera + display connectors/sheets
4. Mechanical outline / placement
5. BOM + JLCPCB

## When unsure

- Ask before deleting anything on `power`, `usb`, `ram`, `flash`, or `wifi`.
- Prefer “mark for deletion” + commit message over silent large deletes.
- Reference `ROADMAP.md` for locked decisions.