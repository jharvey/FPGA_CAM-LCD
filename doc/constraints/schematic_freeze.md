# Schematic freeze – monocular-strip (before Phase 4)

Status: **schematic frozen for mechanical / placement work.** Changes after this point should be
layout-driven (pin swaps, footprint choices) or fixes, each with its own commit.

ERC (KiCad 10, `kicad-cli sch erc --severity-all`): **179 violations, all classified below.**
None are "must fix". The three must-fix items found in the hygiene pass were fixed in the freeze commit.

## Fixed in the freeze pass (must fix)

| Issue | Fix |
|---|---|
| U1 unit H (SERDES balls) was not placed anywhere (lost with the deleted ULX3S `serdes` sheet). On the fitted **LFE5U-85F** (no SERDES), 28 of those balls are **GND** per the ECP5U-85 CABGA381 pinout – they were floating. | Unit placed on `fpga-io`; 28 GND balls → `GND`; 8 HDTX balls (`RESERVED`) → no-connect. |
| Y1 25 MHz oscillator (FNETHE025: 1 OE, 2 GND, 3 OUT, 4 VDD) drawn with a `Crystal_GND24` symbol whose cached version stacks pins 2 + 4 → **GND pad tied to +3V3, no ground**. FPGA main clock would not run. | Symbol replaced by `Oscillator:ASE-xxxMHz` (same 1/2/3/4 numbering), footprint unchanged (`Crystal_SMD_7050_4Pads`); pin 2 now GND. |
| RTC U7 (MCP7940N) I²C `FPDI_SCL` / `FPDI_SDA` only reached U7 (other end was on the deleted GPDI sheet) – RTC unreachable. | Restored ULX3S pins: SDA → U1 B19, SCL → U1 E12 (no-connect flags removed); 4.7 k pull-ups R74/R75 to +3V3 (0402, C25900). |

## Remaining ERC items – acceptable / intentional

| Count | Type | Where | Why acceptable |
|---|---|---|---|
| 49 | multiple_net_names | display (28), camera (16), fpga-io (1), power (4) | Descriptive local aliases (`LCD_*`, `CAM_*`, `ADC_*`) on `GN*`/`GP*`/`WIFI_GPIO*` global nets. Net names follow the globals. |
| 1 | same_local_global_label | `CAM_XCLK` | Local alias on camera sheet + global on fpga-io for the same net. |
| 3 | pin_to_pin (power out ↔ power out) | power: U12/U14/U18 VOUT, U16/U19 VOUT | Intentional ideal-diode OR-ing (LM66100). |
| 25 | pin_not_driven | ram: SDRAM address/BA/control (23); usb: `FTDI_RXD`, `FTDI_nRTS` (2) | Nets are complete; ECP5 and SDRAM/FTDI symbol pins are all typed *input*, so ERC sees no driver. |
| 19 + 19 | pin_not_driven + isolated_pin_label | ram/flash/usb: `ADC_*` (4), `BTN_F1/F2/U/D/L/R` (6), `OLED_*` (6), `SD_CD`/`SD_WP` (2), AE1 433 MHz pad (driven count only), `FTDI_nTXLED` (label only) | Orphan ULX3S labels on otherwise-unused FPGA pins (sheets removed in Phase 1). Electrically = unconnected FPGA pins. Cosmetic clean-up optional. |
| 6 | isolated_pin_label | fpga-io: `GN25..27`, `GP25..27` | Only on J6 (legacy header, DNP). |
| 5 | power_pin_not_driven | `+1V1`, `+2V5` (TLV62569 via inductor), `RTCVDD` (via R65), `SD3V3` (via R38 0.47 Ω), US2 ID (symbol pin typed power) | Rails are driven through passives; ERC cannot see the source. PWR_FLAGs optional. |
| 14 | lib_symbol_issues | legacy ULX3S cached symbols (jumpers, Q1/Q2, LEDs, zeners) | Cached symbols differ from KiCad 10 libraries; schematic is self-contained. |
| 23 | unconnected_wire_endpoint | mainly flash sheet | Wire stubs extend 1.27 mm past their net labels; connectivity verified (all `FLASH_*`/`FPGA_*` config nets complete). Cosmetic. |
| 1 | no_connect_dangling | power: Y2 (32 kHz crystal) | Second no-connect left from the old `Crystal_GND23` pin layout; pins 2/3 are flagged. Cosmetic. |
| 1 + 1 | pin_not_connected + pin_not_driven | flash: U1 R3 DOUT/CSOn | Unused configuration daisy-chain output; no flag. Cosmetic. |

## Defer to layout (Phase 4 start)

| Count | Type | Items | Action |
|---|---|---|---|
| 12 | footprint_link_issues | H1–H4 (`Mounting_Holes` lib not configured), J2/J4/J6 (`Socket_Strips` lib), RV2/RV3 (`R_0805…HandSolder` name), B0/B1/B2 (`SW_SPST_PTS645` renamed in KiCad 10) | **Must be resolved before "Update PCB from Schematic"**: add the legacy libraries to `fp-lib-table` or reassign to KiCad 10 footprints. |
| 6 | (no footprint) | BT11–BT32 18650 contacts MY-18650-04-J / -05-J (added after freeze, see below) | Footprint field empty – create/import before PCB update. |

## Known limitations at freeze

- **Battery contacts (post-freeze change)** – JST-PH J8/J9/J10 removed and replaced by PCB contacts BT11/BT21/BT31 (+ button, MY-18650-04-J, LCSC C19184125) and BT12/BT22/BT32 (− spring, MY-18650-05-J, LCSC C19184124). Mechanical retention and length tolerance come from the plastic battery bay (Phase 4).

- **ESP32 shares display SPI pins** – `LCD_SCK`/`LCD_DC` also on ESP32 IO32/IO33; firmware must keep them Hi-Z.
- **LM66100 ~CE control** – broken out via R71–R73 (0 Ω) only. Firmware-driven cell selection needs a level-shifted driver (~CE is VIN-referenced, up to ~4.3 V).
- **RTC I²C pull-ups to +3V3** – the bus is unpowered when +3V3 is off (RTC runs from VBAT then; I²C access only with the system on).
- **SD card detect / write protect** – socket switch (SD1 pad 10) not wired; `SD_CD`/`SD_WP` FPGA labels orphaned. Add if needed.
- **LCD VDD at 3.3 V** – at the panel's maximum (typ 3.0 V).
- **J7 FFC contact side** and **J1 camera socket type** depend on the Phase 4 PCB orientation.
- **AP3032 on AP3019A symbol**, **L4 = 4.7 µH** – verify against AP3032 datasheet before ordering.
- **Status LEDs** – red 0603, ~1–1.5 mA; colour / brightness to revisit with the case.
- **USB-C PD** – deferred (Phase 2b / later); USB stays micro-B (US1, US2).
- **PCB** not yet synced to the schematic (no footprints for the camera/display/user-I/O parts yet).
