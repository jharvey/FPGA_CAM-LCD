# FCL battery end block (MS3181-16 bayonet): drawing and editable models

> **Out of date since 2026-11-26. Do not machine from these files yet.**
> The drawing, the `_edit` STEP/STL files and the FreeCAD files show the earlier block with two variants (A and B). The board now uses **one common block** at all three cells:
>
> | | Earlier A/B block (these files) | Common block (on the board) |
> |---|---|---|
> | Mounting face | relieved 0.6 mm, two raised bosses | flat, 0.5 mm off the PCB, no bosses; a small M2.5 washer (4.5 OD x 0.5) at each screw is the spacer |
> | Tapped M2.5 holes | one, at (4.6, -9.7) | two: T1 (4.4, -9.7) and T2 (2.6, +9.3) |
> | 2 mm pin hole | (3.2, +9.3) for A, (3.2, +7.5) for B, 3.5 deep | one, D (3.2, +6.25), 3.0 deep |
> | Pocket | from X 4.2 | from X 4.3 |
>
> Positions are (X into the board from the board edge, Y along the edge from the cell axis). The bayonet boss, bore, O-ring groove and bayonet pins are unchanged.
>
> The hole pattern is still under review (two screws per site chosen from three tapped holes, instead of a screw and a pin). The current geometry is in `scripts/make_battery_block_ms3181.py`, which also writes the KiCad 3D model. `draw_battery_block.py` and `freecad_battery_block.py` have not been updated to it and will be regenerated when the pattern is final.

| File | Use |
|---|---|
| `FCL_BatteryBlock_MS3181_drawing.pdf` | Machining drawing, A3, page 1 = variant A, page 2 = variant B |
| `FCL_BatteryBlock_MS3181_A_edit.step`, `_B_edit.step` | Solid for editing or CAM. Origin is at datums A, B and C: Z = 0 on the mounting face A (block at negative Z), X = 0 on the plate face B (+X toward the board), Y = 0 on the bore centre plane C |
| `FCL_BatteryBlock_MS3181_A_edit.stl`, `_B_edit.stl` | Viewing only |
| `../../scripts/make_battery_block_ms3181.py` | Parametric source: every dimension is a named constant at the top |
| `../../scripts/draw_battery_block.py` | Regenerates the drawing and the edit STEPs from those constants |

Red dimensions marked * are **provisional**: boss OD, bayonet pin position, angles and protrusion. Measure a real MS3181-16 cap first.

## Editing

**Small changes (Onshape, IronCAD, Fusion, SolidWorks): import the STEP and edit faces directly**
- **Onshape:** Insert, then Import, then pick the STEP. Change it with *Move face*, *Offset face*, *Delete face* and *Modify fillet*, or add new features on top, such as a sketch with an extrude/cut or a hole.
  - Example: to change the boss OD, use *Offset face* on the boss cylinder.
  - Example: to move a pin hole, use *Move face* on the hole.
- **IronCAD:** File, then Import, then STEP. Edit faces with the TriBall, or run **Feature Recognition** to turn the imported solid back into editable features: extrudes, holes, the pocket.
- **Fusion 360:** the same direct-edit tools (Press Pull, Move face). Or right-click the body and use *Remove features* / *Convert to features*.

**Large changes: rebuild as native features (about 15 min) using this list, then delete the import**
Rebuild in this order. All numbers are from the drawing:
1. **Plate:** sketch on the YZ plane, a rectangle 28 × 28 (Y ±14, Z −25.8 to +2.2). Extrude X −2.8 (from X 0 to −2.8).
2. **Flange:** a rectangle Y ±12.5, Z −25.8 to −0.6. Extrude X 0 to +7.2.
3. **Bosses on face A:** Ø4.6 at (4.6, −9.7) and Ø3.2 at (3.2, +9.3 for A / +7.5 for B). Extrude from Z −0.6 up to Z 0.
4. **Bayonet boss:** Ø24.0 on the cell axis (Y 0, Z −11.8). Extrude from X −2.8 outward 10.5, so the end face is at X −13.3.
5. **Bore:** Ø19.2 through all, on the same axis.
6. **O-ring groove:** in the boss end face, Ø20.2 to Ø23.0, 0.75 deep.
7. **Bayonet pin holes:** 3 × Ø2.4, radial through the boss wall, 6.5 from the boss end face. One at 90° (toward face A), the others at ±120° from it. Use a circular pattern around the bore axis.
8. **Screw hole:** at (4.6, −9.7) from face A. M2.5 × 0.45 tapped, drill Ø2.05, 5.5 deep (use the Hole feature with *Tapped*).
9. **Dowel hole:** Ø2.0 H7, 3.5 deep, at (3.2, +9.3 / +7.5).
10. **Pocket:** X 4.2 to 7.2, Y 9.9 to 12.5, 4.0 deep from face A.
11. Make the dowel Y position, boss OD, pin X and pin angle into *Variables* (Onshape `#name`, IronCAD parameters). A and B then become a single part with configurations.

**Regenerating from the script (keeps the drawing, KiCad 3D model and case in step)**

Edit the constants in `make_battery_block_ms3181.py`, then run:
```
venv/bin/python scripts/make_battery_block_ms3181.py
venv/bin/python scripts/draw_battery_block.py
```
After that, rebuild the case (`case/assembly/build_case.py` with `FCL_MS3181_DIR`).
