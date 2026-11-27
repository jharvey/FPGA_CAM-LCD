# FPGA_CAM-LCD: single-board FPGA monocular

A hand-held monocular on one PCB, based on a stripped ULX3S:

- Lattice ECP5-85F FPGA, SDRAM, flash, ESP32-S3 (WiFi, USB, programming), SD card
- OV7670 camera module on the scene side, Newhaven 2.1" round TFT (NHD-2.1-480480AF-ASXP) on the eye side
- Three 18650 cells, each hot-swappable through its own quarter-turn cap, plus USB-C charging
- 3D-printed case with a 1/4-20 tripod thread

## Where things stand (2026-11-27)

| Area | State |
|---|---|
| Schematic | Frozen, with later additions listed in `doc/constraints/schematic_freeze.md` |
| PCB | Routed. KiCad DRC: 0 errors, 0 unconnected (branch `merged-board`) |
| Battery end blocks | One common machined aluminium block at all three cells, MS3181-16 bayonet caps. Mounting-hole pattern still under review |
| Case | Draft 4 modelled (not printed yet): two shells, two cell cradles, snap-in buttons, camera screwed to the lid |
| Ordering | **Not ready.** See "Open before ordering" in `ROADMAP.md` |
| FPGA and software | Written and tested in simulation only, no board exists. One bitstream (camera to TFT, overlay with text and graphics, sensor bridge) that meets timing; the ESP32 software (hub, pages, phone page) runs under MicroPython on a PC. `doc/DEVELOPER_GUIDE.md` |

**Try it without hardware** (Python 3): `python firmware/sim/fcl_sim.py --web 8080`, then open `http://127.0.0.1:8080`.
Start reading at `doc/QUICK_START.md`.

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
| `doc/BRINGUP.md` (`.pdf`) | First power-up checklist (first article): test points, rails, programming, stage-by-stage checks |
| `doc/PRODUCTION_TEST.md` | Short per-board check once the design is validated, compared with BRINGUP golden values |
| `doc/QUICK_START.md` (`.pdf`) | One page: buttons, pages, first use, the PC tools |
| `doc/USER_MANUAL.md` | Using the unit: buttons, the screen and its graphics, the Level / Height / Bearing / Survey pages, menu, phone page, updates over Wi-Fi, logging, calibration (pictures in `doc/manual/`) |
| `doc/TROUBLESHOOTING.md` | What to look at, by symptom |
| `doc/DEVELOPER_GUIDE.md` | Software layers, writing a page of your own, graphics, scripting from a PC, the phone page's addresses, FPGA builds and clocks, tests |
| `doc/lessons/README.md` | Six lessons with the simulator: readings, slopes, heights, the compass, a room plan, a page of your own |
| `doc/FIRMWARE_GUIDE.md` | Reference made from a simulator run: USB stream, dashboard, LCD overlay, commands (pictures in `doc/fw/`) |
| `fpga/prebuilt/` | Stored build outputs: the three bitstreams, intermediates, checksums, tool versions, timing, test logs. `python fpga/make_prebuilt.py --check` compares your build with them |
| `fpga/bridge/`, `fpga/osd/`, `fpga/full/` | FPGA bridge to the ESP32 (sensors, ADC, servos, buttons), the LCD overlay, and the full design with its whole-design simulation |
| `doc/PROBE_POINTS.md` | Bare-copper probe vias on the back: spare FPGA balls, spare ESP32 pins, key nets (map: `doc/probe_points.png`) |
| `doc/jlc_check_2026-11-22.md` | JLCPCB build check (a dated snapshot; see the note at its top) |
| `fpga/IO_REMAP.md`, `fpga/ESP32_PINS.md` | FPGA and ESP32 pin maps; the camera project's clocks and what was changed in it |
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