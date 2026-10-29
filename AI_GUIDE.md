# AI Collaboration Guide – FPGA_CAM-LCD Monocular

This document tells an AI assistant (or a human) how to work on this repo productively.

## Project goal (short)

Single PCB monocular:
- ECP5-85F + SDRAM + flash
- OV7670 camera
- Newhaven 2.1" TFT (40-pin)
- 3×18650 sequential / hot-swap + USB charge
- Keep USB (FTDI), WiFi (ESP32), SD (on wifi sheet)

Base: stripped ULX3S. Branch: `monocular-strip`.

## Rules for the AI

1. **Always work on branch `monocular-strip`.** Never commit design changes to `master` unless asked.
2. **Prefer hierarchical sheets.** Do not move everything onto the root schematic.
3. **Keep these sheets:** power, usb, ram, flash, wifi.  
   Camera and display will be added as new sheets later.
4. **Power strategy:** keep the existing TLV62569 rails (1.1 / 2.5 / 3.3 V). Replace only the *input* stage with 3×18650 + ideal diodes (LM66100 family) + sense dividers + USB charging.
5. **Every time you deliver file changes, also provide a ready-to-paste commit message.**
6. Prefer small, reviewable commits over large dumps.
7. When suggesting deletions, name exact files or ref des when possible.
8. Do not assume barrel jack or single-LiPo input; redesign around 3 independent 18650s.
9. JLCPCB / LCSC part numbers are preferred when recommending components.
10. Update `ROADMAP.md` status when a phase is finished.

## Commit message convention

Always supply a commit message with any change set. Preferred style:
