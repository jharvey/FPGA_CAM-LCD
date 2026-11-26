"""Copy the BOM fields of BT12 / BT32 from the schematic onto their footprints (keeps schematic parity clean)."""
import pcbnew
b = pcbnew.LoadBoard("FCL.kicad_pcb")
SRC = {"BT12": "A", "BT32": "B"}
for ref, v in SRC.items():
    fp = b.FindFootprintByReference(ref)
    for k, val in (("Category", "Machined"), ("Qty", "1"), ("Material", "6061-T6, electroless nickel"),
                   ("Source_File", f"case/battery_blocks/ms3181/FCL_BatteryBlock_MS3181_{v}_boardframe_for_machining.step")):
        fp.SetField(k, val)
        f = fp.GetField(k) if hasattr(fp, "GetField") else None
        for fld in fp.GetFields():
            if fld.GetName() == k:
                fld.SetVisible(False)
                fld.SetLayer(b.GetLayerID("B.Fab"))
    print(ref, fp.GetValue(), [x.GetName() for x in fp.GetFields()])
b.Save("FCL.kicad_pcb")
