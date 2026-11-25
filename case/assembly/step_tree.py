"""List the parts of a STEP assembly (name, instance, bbox in mm) using OCP XCAF."""
import sys
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopLoc import TopLoc_Location

def load(path):
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    r = STEPCAFControl_Reader(); r.SetNameMode(True); r.SetColorMode(True)
    r.ReadFile(path); r.Transfer(doc)
    return doc, XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

def name(lab):
    n = TDataStd_Name()
    return n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else "?"

def walk(st, lab, loc, depth, out):
    if st.IsReference_s(lab):
        ref = TDF_Label(); st.GetReferredShape_s(lab, ref)
        loc = loc.Multiplied(st.GetLocation_s(lab))
        nm = name(lab) + " -> " + name(ref); lab2 = ref
    else:
        nm = name(lab); lab2 = lab
    shp = st.GetShape_s(lab2).Moved(loc)
    b = Bnd_Box(); BRepBndLib.Add_s(shp, b, True)
    out.append((depth, nm, b.Get(), loc, lab2))
    if st.IsAssembly_s(lab2):
        ch = TDF_LabelSequence(); st.GetComponents_s(lab2, ch)
        for i in range(1, ch.Length() + 1):
            walk(st, ch.Value(i), loc, depth + 1, out)

def tree(path):
    doc, st = load(path)
    roots = TDF_LabelSequence(); st.GetFreeShapes(roots)
    out = []
    for i in range(1, roots.Length() + 1):
        walk(st, roots.Value(i), TopLoc_Location(), 0, out)
    return doc, st, out

if __name__ == "__main__":
    _, _, out = tree(sys.argv[1])
    for d, nm, bb, loc, _ in out:
        if d <= int(sys.argv[2] if len(sys.argv) > 2 else 3):
            print("  " * d + nm[:90], [round(v, 2) for v in bb])
