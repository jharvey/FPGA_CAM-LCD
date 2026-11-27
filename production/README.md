# Production files

Generated 2026-11-26 from `FCL.kicad_pcb` by `bash scripts/make_production.sh`. Regenerate after any board change.

One bare board serves both battery variants. Only the assembly BOM and the mechanical parts differ.

| File | Removable cells (blocks + bayonet caps) | Fixed cells (soldered spring contacts) |
|---|---|---|
| Gerbers + drill | `FCL_gerbers_V0.1.zip` | `FCL_gerbers_V0.1.zip` (same) |
| JLC assembly BOM | `removable/FCL_bom_jlc.csv` | `fixed/FCL_bom_jlc.csv` |
| JLC placement (CPL) | `removable/FCL_cpl_jlc.csv` | `fixed/FCL_cpl_jlc.csv` |
| Mechanical parts (not JLC) | `removable/FCL_mech_bom.csv` | `fixed/FCL_mech_bom.csv` |
| **Complete BOM, with who supplies each line** | `removable/FCL_full_bom.csv` | `fixed/FCL_full_bom.csv` |

**Difference in the JLC files:** the fixed set includes the three spring contacts BT13 / BT23 / BT33
(MY-18650-05-J, C19184124). The removable set leaves them out; the aluminium blocks and caps mount there instead.

**Difference in the mechanical BOM:**
- Removable: 3 blocks, caps and contact stack (slug, disc, spring, O-ring, bayonet pins), 6 x M1.6 x 5 block screws and 0.5 mm spacers, and the standard printed shells and cradle.
- Fixed: no blocks or caps. Print `FCL_case_rear_fixed`, `FCL_case_front_fixed` and `FCL_cell_cradle_fixed` instead of the plain ones.

## Who supplies what

`FCL_full_bom.csv` lists every part of a finished unit. Its first column says where the line comes from:

| Supplier | Meaning |
|---|---|
| JLC PCB (bare board) | the Gerber zip |
| JLC PCB assembly | fitted by JLCPCB from the BOM / CPL files (LCSC number given) |
| JLC assembly, check | same, but out of stock at JLC on 2026-11-22: pre-order into the JLC parts library, or supply the part |
| You supply to JLC | fitted by JLCPCB, part consigned by you: the FPGA U1 (no LCSC number in the BOM) |
| JLC 3D printing | case shells, cradles, button parts: order from JLC3DP with the STEP / STL file |
| JLC CNC | battery end blocks, brass slugs and discs (removable-cell build only) |
| Buy: electronics | display, camera module, speaker, coin cell, SD card, cable, bayonet caps and springs |
| Buy: hardware | screws, washers, heat-set inserts, O-rings, pins, 18650 cells |
| Consumable | thread locker, RTV |

## Ordering at JLC

- 4 layers, 1.6 mm, ENIG suggested (0.8 mm BGA), parts on both sides, tented vias.
- Check in the placement preview: J7 (rotation offset 180, matched against JLC's footprint 2026-11-26), the battery contacts (BT11 / BT21 / BT31 and, fixed only, BT13 / BT23 / BT33), and the parts listed in ROADMAP.
- The battery contacts are through-hole: JLC fits them with its through-hole service, or solder them by hand.
- Not in the JLC files (no LCSC number): AE1, H3, H4, RP1, RP2, RP3, U1.
