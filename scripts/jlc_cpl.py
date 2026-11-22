"""Write JLCPCB assembly files (BOM + CPL) for FCL.kicad_pcb.

Run with KiCad's Python:
    "C:/Program Files/KiCad/10.0/bin/python.exe" scripts/jlc_cpl.py [board] [out_dir]
Defaults: FCL.kicad_pcb next to this folder, output in production/.

Per-footprint fields (set in the schematic, carried to the board):
  LCSC                 JLC/LCSC part number; parts without one are left out.
  FT Rotation Offset   degrees added so JLC's (EasyEDA) footprint lines up with ours.
  FT Position Offset   "x,y" mm in the footprint's own frame, +y up, from our pad centre
                       to JLC's footprint origin.
These are the field names the Fabrication Toolkit plugin reads, with the same meaning.
If you use that plugin instead, turn its automatic translation (rotation database) off,
or the offsets are applied twice.

Conventions (same as Fabrication Toolkit / kicad-jlcpcb-tools):
  Mid X/Y  = centre of the pads' bounding box (+ position offset), absolute board
             coordinates in mm, Y up (the Gerbers do not use the aux origin).
  Rotation = top:    orientation + offset
             bottom: 180 - orientation + offset
DNP parts and parts excluded from position files are skipped.
"""
import csv, math, os, sys, collections
import pcbnew

here = os.path.dirname(os.path.abspath(__file__))
board = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, '..', 'FCL.kicad_pcb')
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, '..', 'production')
os.makedirs(out, exist_ok=True)
stem = os.path.splitext(os.path.basename(board))[0]


def field(fp, name):
    for f in fp.GetFields():
        if f.GetName() == name:
            return f.GetText().strip()
    return ''


def local_to_board(fp):
    """Return (pads_local, M, pos): local pad centres, 2x2 local->board matrix, footprint position (mm, Y down)."""
    g = pcbnew.FOOTPRINT(fp)
    if g.GetLayer() == pcbnew.B_Cu:
        g.Flip(g.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    g.SetOrientationDegrees(0)
    g.SetPosition(pcbnew.VECTOR2I(0, 0))
    loc = [(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, p.GetSize().x / 1e6, p.GetSize().y / 1e6,
            p.GetOrientation().AsDegrees()) for p in g.Pads()]
    px, py = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    brd = [((p.GetPosition().x / 1e6) - px, (p.GetPosition().y / 1e6) - py) for p in fp.Pads()]
    t = fp.GetOrientation().AsDegrees()
    best = None
    for ang in (t, -t, 180 + t, 180 - t):
        for mirror in (1, -1):
            a = math.radians(ang)
            c, s = math.cos(a), math.sin(a)
            M = ((c * mirror, s), (-s * mirror, c))  # rotation (screen, Y down) after optional X mirror
            err = sum(math.hypot(M[0][0] * x + M[0][1] * y - bx, M[1][0] * x + M[1][1] * y - by)
                      for (x, y, *_), (bx, by) in zip(loc, brd))
            if best is None or err < best[0]:
                best = (err, M)
    return loc, best[1], (px, py)


def pad_centre(loc):
    xs, ys = [], []
    for x, y, w, h, o in loc:
        a = math.radians(o)
        hw = abs(w / 2 * math.cos(a)) + abs(h / 2 * math.sin(a))
        hh = abs(w / 2 * math.sin(a)) + abs(h / 2 * math.cos(a))
        xs += [x - hw, x + hw]
        ys += [y - hh, y + hh]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


b = pcbnew.LoadBoard(board)
cpl, bom, skipped = [], collections.OrderedDict(), []
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    ref = fp.GetReference()
    lcsc = field(fp, 'LCSC')
    if fp.IsDNP() or (fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES) or not fp.Pads():
        continue
    if not lcsc:
        skipped.append(ref)
        continue
    loc, M, (px, py) = local_to_board(fp)
    cx, cy = pad_centre(loc)
    po = field(fp, 'FT Position Offset')
    if po:
        ox, oy = (float(v) for v in po.split(','))
        cx, cy = cx + ox, cy - oy  # field is +y up, local frame is +y down
    mx = px + M[0][0] * cx + M[0][1] * cy
    my = py + M[1][0] * cx + M[1][1] * cy
    rot = fp.GetOrientation().AsDegrees()
    bottom = fp.GetLayer() == pcbnew.B_Cu
    if bottom:
        rot = 180 - rot
    ro = field(fp, 'FT Rotation Offset')
    rot = (rot + (float(ro) if ro else 0)) % 360
    cpl.append([ref, '%.4f' % mx, '%.4f' % -my, 'Bottom' if bottom else 'Top', '%g' % round(rot, 3)])
    # one BOM line per LCSC number: JLC leaves lines unselected when several lines match the same part
    e = bom.setdefault(lcsc, [[], str(fp.GetFPID().GetLibItemName()), []])
    if fp.GetValue() not in e[0]:
        e[0].append(fp.GetValue())
    e[2].append(ref)

with open(os.path.join(out, stem + '_cpl_jlc.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    w.writerows(cpl)
with open(os.path.join(out, stem + '_bom_jlc.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC'])
    for lcsc, (vals, fpn, refs) in bom.items():
        w.writerow(['/'.join(vals), ','.join(refs), fpn, lcsc])
print('placed %d parts (%d BOM lines) -> %s' % (len(cpl), len(bom), out))
print('no LCSC number (not in BOM/CPL): %d: %s' % (len(skipped), ' '.join(skipped)))
