# FreeCAD models (FreeCAD 1.1)

## Battery block: FCL_BatteryBlock_MS3181_A.FCStd and _B.FCStd (fully parametric)
- Open the **Params** spreadsheet, change a value (boss_d, pin_from_tip, pin_a1, dowel_y and so on), then press **Recompute** (Ctrl+R).
- The tree is built from Part primitives driven by expressions on those spreadsheet cells:
  - **BlockBody** fuses the plate, flange, two face bosses and the bayonet boss.
  - **Cutters** fuses the bore, O-ring groove, 3 pin holes, tap drill, dowel hole and pocket.
  - **BatteryBlock_A/B** = BlockBody minus Cutters.
- Frame = the machining drawing: origin at datums A, B and C (Z = 0 on face A, X = 0 on plate face B, Y = 0 on the bore centre plane).
- A and B differ only in Params.dowel_y (A 9.3, B 7.5).
- Export: select BatteryBlock_A, then File > Export (STEP, IGES, STL...).
- Checked against the CadQuery model (scripts/make_battery_block_ms3181.py): it matches to 0.5 mm3. The only difference is that the pin holes here are nominal 2.4 mm, where the CadQuery model uses 2.38 mm for the press fit.
- The M2.5 thread is shown as the 2.05 mm tap drill. Add a cosmetic thread or note in TechDraw if needed.
- Regenerate: flatpak run --command=freecadcmd org.freecad.FreeCAD scripts/freecad_battery_block.py docs/mech/freecad
