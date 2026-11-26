#!/usr/bin/env python3
"""MY-18650-05-J spring contacts (C19184124) back on the board next to the battery block mounts: BT13, BT23, BT33.

JLC fits the springs (fixed cells).  For removable cells: unsolder the spring at that cell and fit the block + cap.
Same place the springs had before the blocks (slot 6.18 mm in from the board edge on the cell axis).
  * footprints BAT-TH_MY-18650-05-J_L / _LM (mirror): one land is L-shaped round the 2 mm block pin hole (cell 3, cell 2)
  * schematic: three Conn_01x01 symbols on GND, right of BT12 / BT22 / BT32
  * cell 3: the thermistor track TEMP_BAT_CELL3 (In1) moves below the slot

    flatpak run --command=python3 org.kicad.KiCad scripts/add_spring_option.py /path/to/old_power.kicad_sch
    (repo root, run once; the argument is power.kicad_sch from commit 614fa5fd, the template for the symbol)
"""
import re
import sys
import uuid
import pcbnew

BOARD, SCH = "FCL.kicad_pcb", "power.kicad_sch"
LIB = "footprints/fcl_local.pretty"
OX, OY = 78.0, 55.5
DX = 40.64
mm, MM = pcbnew.ToMM, pcbnew.FromMM
# new ref: (block ref beside it, footprint, footprint centre, slot centre, block pin hole or None)
SITES = {"BT13": ("BT12", "BAT-TH_MY-18650-05-J", (5.5, 15.5), (6.18, 15.5), None),
         "BT33": ("BT32", "BAT-TH_MY-18650-05-J_L", (5.5, 56.5), (6.18, 56.5), (3.2, 62.75)),
         "BT23": ("BT22", "BAT-TH_MY-18650-05-J_L", (79.5, 36.0), (78.82, 36.0), (81.8, 29.75))}
DESCR = "18650 battery contact, negative (spring), MYOUNG. Fitted for fixed cells; remove when the battery block + cap is fitted"

# ---- 1. footprint with the L-shaped land: sign +1 = the land on the footprint +x side is cut, -1 = the -x side
def variant(sign):
    name = "BAT-TH_MY-18650-05-J_L" if sign > 0 else "BAT-TH_MY-18650-05-J_LM"
    s = open(f"{LIB}/BAT-TH_MY-18650-05-J.kicad_mod").read()
    full = "(pad 1 smd rect (at %s 0.68 90.00) (size 3.000 4.000) (layers F.Cu F.Paste F.Mask))" % ("4.95" if sign > 0 else "-4.95")
    assert s.count(full) == 1
    s = s.replace(full, "(pad 1 smd rect (at %.3f 0.68) (size 1.95 3.0) (layers F.Cu F.Paste F.Mask))\n"
                  "\t(pad 1 smd rect (at %.3f 0.08) (size 2.05 1.8) (layers F.Cu F.Paste F.Mask) (zone_connect 2))"
                  % (sign * 3.925, sign * 5.925))
    s = s.replace("easyeda2kicad:BAT-TH_MY-18650-05-J ", "easyeda2kicad:%s " % name, 1)
    rect = crt([(-7.05, -1.45), (7.05, -1.45), (7.05, 2.3), (-7.05, 2.3)])
    assert rect in s
    s = s.replace(rect, crt([(-7.05 * sign, -1.45), (7.05 * sign, -1.45), (7.05 * sign, 1.1), (5.05 * sign, 1.1),
                             (5.05 * sign, 2.3), (-7.05 * sign, 2.3)]))
    open(f"{LIB}/{name}.kicad_mod", "w").write(s)
    return name


def crt(pts):
    return "".join("\t(fp_line (start %.2f %.2f) (end %.2f %.2f) (layer F.CrtYd) (width 0.05))\n" % (p + q)
                   for p, q in zip(pts, pts[1:] + pts[:1]))


# courtyard of the spring = its soldered base only (as on the -04-J contact).  The coil stands about 5 mm off the
# board, over the small parts, like the cell itself.  Was the whole 13.8 x 14.1 mm outline.
p = f"{LIB}/BAT-TH_MY-18650-05-J.kicad_mod"
s = open(p).read()
oldc = crt([(-6.90, 1.67), (-6.90, -12.43), (6.90, -12.43), (6.90, 1.67)])
if oldc in s:
    open(p, "w").write(s.replace(oldc, crt([(-7.05, -1.45), (7.05, -1.45), (7.05, 2.3), (-7.05, 2.3)])))
else:
    assert "-7.05 -1.45" in s, "courtyard lines not found"

# the spring and the block are alternatives on the same spot: no courtyard check between the two
RULE = '''
# Spring contact (BT13 / BT23 / BT33) or battery block (BT12 / BT22 / BT32): one or the other is fitted at a cell
(rule "spring_or_block"
	(severity ignore)
	(constraint courtyard_clearance (min 0mm) )
	(condition "(A.Reference == 'BT?3' && B.Reference == 'BT?2') || (A.Reference == 'BT?2' && B.Reference == 'BT?3')" )
)
'''
d = open("FCL.kicad_dru").read()
if "spring_or_block" not in d:
    open("FCL.kicad_dru", "w").write(d.rstrip("\n") + "\n" + RULE)


# which side is cut at each site: found by trying both on a scratch board position (see section 3)
# ---- 2. schematic
t = open(SCH).read()
assert '"BT13"' not in t, "already done"
old = open(sys.argv[1]).read()
k = old.index('(property "Reference" "BT22"')
tmpl = old[old.rindex("\n\t(symbol\n", 0, k):old.index("\n\t(symbol\n", k)]
assert '"fcl_local:BAT-TH_MY-18650-05-J"' in tmpl and '"d7b7c55d' in tmpl


def num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def shift(blk, dy=0.0):
    return re.sub(r"\((at|xy) ([\d.]+) ([\d.]+)",
                  lambda m: "(%s %s %s" % (m.group(1), num(float(m.group(2)) + DX), num(float(m.group(3)) + dy)), blk)


def fresh(blk):
    return re.sub(r'\(uuid "[0-9a-f-]+"\)', lambda m: '(uuid "%s")' % uuid.uuid4(), blk)


def top_block(text, start):
    """the top-level s-expression that starts at text[start] == '(' (after a newline + tab)"""
    end = text.index("\n\t)", start) + 3
    return text[start - 2:end]


# pick the variant per site: place both on the board in memory and see which puts the small land next to the pin hole
_b = pcbnew.LoadBoard(BOARD)
for ref, (blockref, fpname, pos, slot, hole) in list(SITES.items()):
    if hole is None:
        continue
    ok = None
    for sign in (1, -1):
        name = variant(sign)
        fp = pcbnew.FootprintLoad(LIB, name)
        _b.Add(fp)
        fp.SetPosition(pcbnew.VECTOR2I(MM(OX + pos[0]), MM(OY + pos[1])))
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        for ang in (0, 90, 180, 270):
            fp.SetOrientationDegrees(ang)
            q = [(round(mm(p.GetPosition().x) - OX, 2), round(mm(p.GetPosition().y) - OY, 2), mm(p.GetSize(pcbnew.F_Cu).x) * mm(p.GetSize(pcbnew.F_Cu).y)) for p in fp.Pads()]
            small = [c for c in q if abs(c[2] - 2.05 * 1.8) < 0.01]
            if (slot[0], slot[1]) in [(c[0], c[1]) for c in q] and (small[0][1] - pos[1]) * (hole[1] - pos[1]) > 0:
                ok = name
    assert ok, ref
    SITES[ref] = (blockref, ok, pos, slot, hole)
    print(ref, "uses", ok)

SYM_UUID = {}
add = ""
for ref, (blockref, fpname, _, _, _) in SITES.items():
    k = t.index('(property "Reference" "%s"' % blockref)
    y = float(re.search(r"\(at [\d.]+ ([\d.]+) 0\)", t[t.rindex("\n\t(symbol\n", 0, k):k]).group(1))
    blk = fresh(shift(tmpl, y - 143.51))
    blk = blk.replace('"BT22"', '"%s"' % ref).replace('"fcl_local:BAT-TH_MY-18650-05-J"', '"fcl_local:%s"' % fpname)
    blk = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "%s"' % DESCR, blk, count=1)
    SYM_UUID[ref] = re.search(r'\(dnp no\)\s*\(uuid "([0-9a-f-]+)"\)', blk).group(1)
    add += blk
    # the wire and the GND global label of the block symbol on the same row
    m = re.search(r"\n\t\(wire\s+\(pts\s+\(xy 337\.82 %s\) \(xy 340\.36 %s\)" % (re.escape(num(y)), re.escape(num(y))), t)
    assert m, ("wire", ref)
    add += fresh(shift(top_block(t, m.start() + 2)))
    found = False
    for m in re.finditer(r'\n\t\(global_label "GND"', t):
        g = top_block(t, m.start() + 2)
        if re.search(r"\(at 337\.82 %s \d+\)" % re.escape(num(y)), g):
            add += fresh(shift(g))
            found = True
            break
    assert found, ("label", ref)
i = t.index("\n\t(symbol\n", t.index('(property "Reference" "BT12"'))
t = t[:i] + add + t[i:]
open(SCH, "w").write(t)
print("schematic: added", SYM_UUID)

# ---- 3. board
b = pcbnew.LoadBoard(BOARD)
KEEP = []
gnd = b.FindNet("GND")


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(p):
    return (round(mm(p.x) - OX, 2), round(mm(p.y) - OY, 2))


def area(p):
    sz = p.GetSize(pcbnew.F_Cu)
    return mm(sz.x) * mm(sz.y)


like = b.FindFootprintByReference("BT11")          # the positive contact: same kind of part
sheet_path = "/".join(like.GetPath().AsString().split("/")[:-1])
for ref, (blockref, fpname, pos, slot, hole) in SITES.items():
    fp = pcbnew.FootprintLoad(LIB, fpname)
    KEEP.append(fp)
    b.Add(fp)
    fp.SetPosition(V(*pos))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    for ang in (0, 90, 180, 270):
        fp.SetOrientationDegrees(ang)
        pp = [xy(p.GetPosition()) for p in fp.Pads()]
        small = [xy(p.GetPosition()) for p in fp.Pads() if abs(area(p) - 2.05 * 1.8) < 0.01]
        if slot in pp and (hole is None or (small and (small[0][1] - pos[1]) * (hole[1] - pos[1]) > 0)):
            break
    else:
        raise AssertionError((ref, pp))
    fp.SetReference(ref)
    fp.SetValue("MY-18650-05-J")
    fp.SetPath(pcbnew.KIID_PATH(sheet_path + "/" + SYM_UUID[ref]))
    fp.SetSheetname(like.GetSheetname())
    fp.SetSheetfile(like.GetSheetfile())
    fp.SetFPID(pcbnew.LIB_ID(pcbnew.UTF8("fcl_local"), pcbnew.UTF8(fpname)))
    fp.SetAttributes(like.GetAttributes())
    for f in like.GetFields():
        k = f.GetName()
        if k in ("Reference", "Value", "Footprint"):
            continue
        v = {"LCSC": "C19184124", "LCSC Part": "C19184124", "MPN": "MY-18650-05-J", "Description": DESCR}.get(k, f.GetText())
        fp.SetField(k, v)
    for f in fp.GetFields():
        if f.GetName() not in ("Reference", "Value"):
            f.SetVisible(False)
    for p in fp.Pads():
        p.SetNet(gnd)
    print(ref, fpname, "rot", fp.GetOrientationDegrees(), sorted(pp))

# ---- 4. cell 3: TEMP_BAT_CELL3 on In1 crossed the slot at y 57.3 -> below it at y 59.85
N, in1 = "/power/TEMP_BAT_CELL3", b.GetLayerID("In1.Cu")
done = 0
for tr in list(b.GetTracks()):
    if tr.GetClass() == "PCB_VIA" or tr.GetNetname() != N or tr.GetLayer() != in1:
        continue
    e = {xy(tr.GetStart()), xy(tr.GetEnd())}
    if e in ({(13.8, 57.3), (2.2, 57.3)}, {(2.2, 57.3), (1.4, 58.1)}):
        KEEP.append(tr)
        b.Remove(tr)
        done += 1
    elif e == {(1.4, 58.1), (1.4, 72.5)}:
        if xy(tr.GetStart()) == (1.4, 58.1):
            tr.SetStart(V(1.4, 60.45))
        else:
            tr.SetEnd(V(1.4, 60.45))
        done += 1
assert done == 3, done
pts = [(13.8, 57.3), (11.0, 57.3), (8.45, 59.85), (2.0, 59.85), (1.4, 60.45)]
for p0, p1 in zip(pts, pts[1:]):
    tr = pcbnew.PCB_TRACK(b)
    tr.SetStart(V(*p0))
    tr.SetEnd(V(*p1))
    tr.SetWidth(MM(0.15))
    tr.SetLayer(in1)
    tr.SetNet(b.FindNet(N))
    b.Add(tr)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("saved")
