"""
FCL monocular - mechanical assembly model (PCB + OV7670 + 3x18650 + round TFT + FPC).

Builds two STEP assemblies (and GLB meshes for viewing) from the KiCad board export:

  build/FCL_assembly_asplaced.step  J7 exactly as placed in FCL.kicad_pcb. The TFT FPC is
                                    drawn along the path it would need; the part beyond the
                                    real 27.0 mm FPC length is a separate red solid
                                    "FPC_SHORTFALL".
  build/FCL_assembly_j7flip.step    Proposal: J7 rotated 180 deg (opening toward the cells)
                                    and moved toward the bottom edge, so the FPC makes a
                                    simple L down past cell 3 and reaches with slack.

Coordinate frame = KiCad STEP export frame:
  X = 78 + board_x,  Y = -(55.5 + board_y)   (board_x/board_y = mm from the top-left board
  corner, front view, +y down, same as ROADMAP.md)
  Z: PCB back face (B.Cu, eye side) at Z = 0, front face (F.Cu, scene side) at Z = +1.6.
  The eye looks toward +Z; the camera looks toward +Z out of the front.

Run (from the repo root):
  "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb export step --subst-models \
      --include-tracks --no-dnp -f -o case/build/FCL_board.step FCL.kicad_pcb
  python case/assembly/build_assembly.py
"""
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BUILD = os.path.join(REPO, "case", "build")
BOARD_STEP = os.path.join(BUILD, "FCL_board.step")
CONTACT_DIR = os.path.join(REPO, "footprints", "fcl_local.3dshapes")

# --------------------------------------------------------------------------------------
# Parameters (mm). Sources: FCL.kicad_pcb (2026-11-22, 3be99b7d), ROADMAP 4.1/4.4,
# NHD-2.1-480480AF-ASXP mechanical drawing rev 2A (doc/NHD-2.1-480480AF-ASXP.pdf p.3).
# --------------------------------------------------------------------------------------
OX, OY = 78.0, 55.5            # page position of the board's top-left corner
BOARD_W, BOARD_H, PCB_T = 85.0, 79.0, 1.6

PCB_AXIS = (34.88, 37.5)       # axis the PCB was laid out for (keep-out / TFT circle drawings)
J1_SOCKET_CENTRE = (34.88, 52.50)  # centroid of the 2x9 socket pins (J1 origin is pin 1)
CAM_LENS_ABOVE_HEADER = 15.46  # real OV7670 (Onshape model): lens axis -> header centre
# Real lens axis on this PCB. The TFT is centred on this, not on PCB_AXIS.
AXIS = (J1_SOCKET_CENTRE[0], J1_SOCKET_CENTRE[1] - CAM_LENS_ABOVE_HEADER)   # (34.88, 37.04)

# Onshape draft (case/models/Onshape_Assembly_1.step): its frame -> board coordinates
#   board_x = x + 57.4, board_y = z + 23.69, Z = y + 2.91   (old 85x75 PCB at y -2.91..-1.64)
ONSHAPE_STEP = os.path.join(REPO, "case", "models", "Onshape_Assembly_1.step")
OS_HEADER_CENTRE = (43.96, 47.52)  # camera 2x9 header centre, mapped board coords
OS_CAM_PCB_BOTTOM_Z = 5.30
OS_TFT_CENTRE = (44.955, 34.13)    # TFT circle / active-area centre, mapped
OS_TFT_BACK_Z = -22.20             # TFT face toward the cells, mapped
OS_TFT_MAX_BY = 66.6               # bodies reaching below this are the straight FPC -> dropped

# 18650 cells (contacts BT11..BT32 in the PCB)
CELL_ROWS = (15.5, 36.0, 56.5)
CELL_D, CELL_L = 18.6, 65.0
CELL_GAP = 2.5                 # cradle: can 2.5 mm above the PCB back face (ROADMAP 4.4)
CELL_PLUS_X = 77.2             # + button face (x), cell lies from 12.2 to 77.2
CELL_AXIS_Z = -(CELL_GAP + CELL_D / 2)          # -11.8
CONTACT_BUMP_Z = 1.22          # button-bump centre height in the MY-18650-04-J model

# NHD-2.1-480480AF-ASXP
TFT_OD = 58.18                 # LCM outer diameter
TFT_FLAT_W = 33.4              # width of the flat bottom extension
TFT_BELOW = 60.71 - TFT_OD / 2 # 31.62: AA centre -> LCM bottom edge
TFT_T = 2.26
TFT_AA_D = 53.28
TFT_FOAM = 0.5                 # foam/adhesive pad between the cans and the TFT back
TFT_BACK_Z = -(CELL_GAP + CELL_D + TFT_FOAM)    # -21.6 (side facing the PCB)
TFT_EYE_Z = TFT_BACK_Z - TFT_T                  # -23.86

FPC_LEN = 27.0                 # LCM bottom edge -> contact end (+-0.5)
FPC_W_WIDE, FPC_WIDE_LEN = 33.4, 13.2  # wide part with the component area
FPC_W_TAIL = 20.5
FPC_T, FPC_STIFF_T, FPC_STIFF_LEN = 0.12, 0.30, 5.5
FPC_R = 1.5                    # fold radius (static fold, ~12-15x the 0.1-0.12 mm FPC)
FPC_Z0 = TFT_BACK_Z + FPC_T / 2  # FPC leaves the LCM on its PCB-facing side

# J7 Hirose FH12-40S-0.5SH as placed (measured from the board STEP)
J7_BODY_Y = (67.08, 73.48)     # opening (slider) at the +y side
J7_SLOT_Z = -1.0               # cable slot centre height (B side)
J7_INSERT = 3.5                # contact insertion depth from the opening face
J7_GAP = 0.5                   # clearance between FPC fold and J7 face
J7_FLIP_OPENING = 72.10        # proposal: J7 rotated 180 deg, opening face at y 72.10 (body 72.10-78.50, 0.5 mm to the edge)

# OV7670 module (generic 2x9 no-FIFO board) - APPROXIMATE, measure the real module
CAM_PCB = 35.0
CAM_PCB_T = 1.6
SOCKET_TOP_Z = PCB_T + 8.5     # J1 2x9 socket top (matches the board STEP)
CAM_HEADER_PLASTIC = 2.5
CAM_HOLDER = (14.0, 14.0, 5.0)
CAM_BARREL_D, CAM_BARREL_H = 12.0, 8.5
J1_CENTRE = (34.88, 51.23)


# --------------------------------------------------------------------------------------
def P(bx, by):
    """board (x, y) -> STEP (X, Y)"""
    return (OX + bx, -(OY + by))


def colour(r, g, b, a=1.0):
    return cq.Color(r, g, b, a)


def rigid(shape, rows, t):
    """apply a 3x3 rotation (rows) + translation t to a shape"""
    from OCP.gp import gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    tr = gp_Trsf()
    tr.SetValues(rows[0][0], rows[0][1], rows[0][2], t[0],
                 rows[1][0], rows[1][1], rows[1][2], t[1],
                 rows[2][0], rows[2][1], rows[2][2], t[2])
    return cq.Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, tr, True).Shape())


# ---------------------------------------------------------------- cells + contacts ----
def make_cells():
    parts = []
    for i, row in enumerate(CELL_ROWS, 1):
        x0 = CELL_PLUS_X - CELL_L
        X0, Y = P(x0, row)
        can = (cq.Workplane("YZ", origin=(X0, Y, CELL_AXIS_Z))
               .circle(CELL_D / 2).extrude(CELL_L - 0.8)
               .faces(">X").workplane().circle(4.0).extrude(0.8))   # + nub
        parts.append((f"CELL{i}", can.val(), colour(0.85, 0.45, 0.75)))
    return parts


def make_contacts():
    parts = []
    spring = cq.importers.importStep(os.path.join(CONTACT_DIR, "BAT-TH_MY-18650-05-J.step")).val()
    button = cq.importers.importStep(os.path.join(CONTACT_DIR, "BAT-TH_MY-18650-04-J.step")).val()
    dz = -(CELL_GAP + CELL_D / 2) - (-CONTACT_BUMP_Z)  # model z -> STEP Z, bump on the cell axis
    for i, row in enumerate(CELL_ROWS, 1):
        # spring (- end, x 3.8..17.9): X = 84 - my, Y = -(55.5+row) - mx, Z = -mz + dz
        s = rigid(spring, [[0, -1, 0], [-1, 0, 0], [0, 0, -1]],
                  (OX + 6.0, -(OY + row), dz))
        parts.append((f"BT{i}2_spring", s, colour(0.8, 0.8, 0.82)))
        # button (+ end, x 77.2..81.2): X = 157 + my, Y = -(55.5+row) + mx, Z = -mz + dz
        b = rigid(button, [[0, 1, 0], [1, 0, 0], [0, 0, -1]],
                  (OX + 79.0, -(OY + row), dz))
        parts.append((f"BT{i}1_button", b, colour(0.8, 0.8, 0.82)))
    return parts


# ----------------------------------------------------------------------------- TFT ----
def make_tft():
    ax, ay = P(*AXIS)
    flat_bottom_y = -(OY + AXIS[1] + TFT_BELOW)
    outline = (cq.Workplane("XY", origin=(0, 0, TFT_EYE_Z))
               .moveTo(ax, ay).circle(TFT_OD / 2).extrude(TFT_T)
               .union(cq.Workplane("XY", origin=(0, 0, TFT_EYE_Z))
                      .center(ax, (ay + flat_bottom_y) / 2)
                      .rect(TFT_FLAT_W, ay - flat_bottom_y).extrude(TFT_T)))
    glass = (cq.Workplane("XY", origin=(0, 0, TFT_EYE_Z - 0.02))
             .moveTo(ax, ay).circle(TFT_AA_D / 2).extrude(0.02))
    return [("TFT_NHD-2.1-480480AF", outline.val(), colour(0.75, 0.42, 0.10)),
            ("TFT_active_area", glass.val(), colour(0.05, 0.05, 0.08))]


def tft_lcm_bottom_y():
    return AXIS[1] + TFT_BELOW            # board y of the flat bottom edge (69.12)


# ----------------------------------------------------------------------------- FPC ----
class Path2D:
    """centre line in the (board_y, Z) plane built from straights and 90 deg arcs"""

    def __init__(self, y, z, heading):
        self.pts = [(y, z)]
        self.s = [0.0]
        self.h = heading                  # unit vector (dy, dz)

    def line(self, length, step=0.5):
        n = max(1, int(math.ceil(length / step)))
        y, z = self.pts[-1]
        for k in range(1, n + 1):
            f = length * k / n
            self.pts.append((y + self.h[0] * f, z + self.h[1] * f))
            self.s.append(self.s[-1] - length * (k - 1) / n + length * k / n)
        return self

    def arc(self, r, turn, angle_deg=90.0, step_deg=3.0):
        """bend of radius r (centre line) through angle_deg; turn=+1 / -1 picks the side.
        Arc length = r * angle, so the ribbon is never stretched or shrunk."""
        if angle_deg <= 1e-9:
            return self
        y, z = self.pts[-1]
        hy, hz = self.h
        ny, nz = -hz * turn, hy * turn    # toward the centre
        cy, cz = y + ny * r, z + nz * r
        a0 = math.atan2(y - cy, z - cz)
        th = math.radians(angle_deg)
        n = max(2, int(math.ceil(angle_deg / step_deg)))
        for k in range(1, n + 1):
            a = a0 - turn * th * k / n
            self.pts.append((cy + r * math.sin(a), cz + r * math.cos(a)))
            self.s.append(self.s[-1] + r * th / n)
        # heading rotates by th (counter-clockwise in (y, z) for turn=+1)
        c, s = math.cos(turn * th), math.sin(turn * th)
        self.h = (hy * c - hz * s, hy * s + hz * c)
        return self

    @property
    def end(self):
        return self.pts[-1]

    @property
    def length(self):
        return self.s[-1]

    def sub(self, s0, s1):
        """sampled points + normals between arc-length s0 and s1"""
        out = []
        for i in range(len(self.pts) - 1):
            sa, sb = self.s[i], self.s[i + 1]
            if sb < s0 or sa > s1 or sb == sa:
                continue
            ya, za = self.pts[i]
            yb, zb = self.pts[i + 1]
            ty, tz = (yb - ya) / (sb - sa), (zb - za) / (sb - sa)
            for s in (max(sa, s0), min(sb, s1)):
                f = (s - sa) / (sb - sa)
                out.append(((ya + (yb - ya) * f, za + (zb - za) * f), (-tz, ty)))
        dedup = [out[0]]
        for p in out[1:]:
            if abs(p[0][0] - dedup[-1][0][0]) + abs(p[0][1] - dedup[-1][0][1]) > 1e-6:
                dedup.append(p)
        return dedup


def ribbon(path, s0, s1, width, thick, xc_board):
    pts = path.sub(s0, s1)
    left = [(OY_to_Y(y + n[0] * thick / 2), z + n[1] * thick / 2) for (y, z), n in pts]
    right = [(OY_to_Y(y - n[0] * thick / 2), z - n[1] * thick / 2) for (y, z), n in pts]
    poly = left + right[::-1]
    X0 = OX + xc_board - width / 2
    wp = cq.Workplane("YZ", origin=(X0, 0, 0)).polyline(poly).close().extrude(width)
    return wp.val()


def OY_to_Y(by):
    return -(OY + by)


def fpc_parts(path, real_len):
    xc = AXIS[0]
    parts = []
    L = path.length
    wide_end = min(FPC_WIDE_LEN, L)
    parts.append(("FPC_wide", ribbon(path, 0, wide_end, FPC_W_WIDE, FPC_T, xc), colour(0.95, 0.62, 0.12)))
    tail_end = min(real_len, L)
    stiff0 = real_len - FPC_STIFF_LEN
    parts.append(("FPC_tail", ribbon(path, wide_end, min(stiff0, tail_end), FPC_W_TAIL, FPC_T, xc),
                  colour(0.95, 0.62, 0.12)))
    if stiff0 < tail_end:
        parts.append(("FPC_stiffener", ribbon(path, stiff0, tail_end, FPC_W_TAIL, FPC_STIFF_T, xc),
                      colour(0.85, 0.55, 0.10)))
    if L > real_len + 1e-3:
        parts.append(("FPC_SHORTFALL", ribbon(path, real_len, L, FPC_W_TAIL, FPC_STIFF_T, xc),
                      colour(1.0, 0.0, 0.0)))
    return parts


def fpc_path_asplaced():
    """J7 opening faces +y (bottom edge): FPC goes out past J7, down, and back in (J shape)."""
    y0 = tft_lcm_bottom_y()
    yv = J7_BODY_Y[1] + J7_GAP + FPC_R             # vertical run (centre line)
    insert_end = J7_BODY_Y[1] - J7_INSERT
    p = Path2D(y0, FPC_Z0, (1, 0))
    p.line(yv - FPC_R - y0)
    p.arc(FPC_R, 1)                                # turn toward +Z (the PCB)
    p.line((J7_SLOT_Z - FPC_R) - (FPC_Z0 + FPC_R))
    p.arc(FPC_R, 1)                                # turn toward -y, into J7
    p.line((yv - FPC_R) - insert_end)
    return p


def _flip_path(phi, rb, r1, r2, insert_end):
    y0 = tft_lcm_bottom_y()
    p = Path2D(y0, FPC_Z0, (1, 0))
    p.arc(r1, 1, 90.0 - phi)                       # fold toward the PCB, still leaning outward
    p.arc(rb, 1, 2 * phi)                          # gentle outward bow takes up the spare length
    p.arc(r2, -1, 90.0 + phi)                      # fold back toward +y, into J7
    p.line(max(0.0, insert_end - p.end[0]))
    return p


def fpc_path_j7flip():
    """J7 rotated 180 deg (opening toward the cells) at J7_FLIP_OPENING.
    The FPC keeps its real length FPC_LEN: two R=FPC_R folds plus an outward bow whose
    size is solved so the centre line is exactly FPC_LEN long and enters J7 at the slot height."""
    opening = J7_FLIP_OPENING
    insert_end = opening + J7_INSERT
    r1 = r2 = FPC_R

    def dz_after_bends(phi, rb):
        p = _flip_path(phi, rb, r1, r2, insert_end)
        return p.end[1]

    def solve_rb(phi):
        # end height is linear in rb: z(rb) = z(0) + k*rb
        z0, z1 = dz_after_bends(phi, 0.0), dz_after_bends(phi, 1.0)
        return (J7_SLOT_Z - z0) / (z1 - z0)

    def length(phi):
        return _flip_path(phi, solve_rb(phi), r1, r2, insert_end).length

    lo, hi = 0.05, 60.0
    if length(lo) > FPC_LEN:
        raise SystemExit(f"FPC too short even straight: needs {length(lo):.2f} mm")
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if length(mid) < FPC_LEN else (lo, mid)
    phi = (lo + hi) / 2
    rb = solve_rb(phi)
    p = _flip_path(phi, rb, r1, r2, insert_end)
    ys = [pt[0] for pt in p.pts]
    info = {"bow_angle_deg": round(2 * phi, 2), "bow_radius": round(rb, 2),
            "bow_max_y": round(max(ys), 2), "fold2_end_y": None,
            "end_z": round(p.end[1], 3), "length": round(p.length, 3)}
    return p, opening, info


# J7 vertical (Hirose FH12-40S-0.5SV) as placed by scripts/swap_j7_vertical.py
J7V_CENTRE_Y = 67.80           # footprint centre (board y); x = AXIS x
J7V_SLOT_Y = J7V_CENTRE_Y + 0.5  # FPC slot is ~0.5 mm toward the contact (odd-pad) side
J7V_END_Z = -0.8               # height of the inserted FPC end above the PCB back face


def fpc_path_vertical():
    """TFT -> vertical ZIF: bend R through (90+phi), short straight d, reverse bend R through
    phi, then the stiffened end straight down into J7. Largest R with exact length FPC_LEN."""
    y0 = tft_lcm_bottom_y()
    depth = J7V_END_Z - FPC_Z0
    def geom(R1, R2, phi):
        d = (FPC_LEN - depth - R1 * (math.pi / 2 + phi - 1 - math.sin(phi)) - R2 * (phi - math.sin(phi))) / (1 - math.cos(phi))
        st = FPC_LEN - R1 * (math.pi / 2 + phi) - R2 * phi - d
        yc = y0 + R1 * math.cos(phi) - d * math.sin(phi) - R2 * (1 - math.cos(phi))
        return d, st, yc

    best = None
    for i in range(10, 100):
        R1 = i * 0.1
        for k in range(10, 100):
            R2 = k * 0.1
            if best and min(R1, R2) <= best[0]:
                continue
            prev = None
            for j in range(20, 880):
                phi = math.radians(j * 0.1)
                d, st, yc = geom(R1, R2, phi)
                ok = d >= 0 and st >= FPC_STIFF_LEN
                cur = (phi, yc - J7V_SLOT_Y, ok)
                if prev and prev[2] and ok and prev[1] * cur[1] <= 0:
                    lo, hi = prev[0], phi
                    for _ in range(40):
                        mid = (lo + hi) / 2
                        if (geom(R1, R2, mid)[2] - J7V_SLOT_Y) * prev[1] > 0:
                            lo = mid
                        else:
                            hi = mid
                    ph = (lo + hi) / 2
                    d2, st2, yc2 = geom(R1, R2, ph)
                    if d2 >= 0 and st2 >= FPC_STIFF_LEN:
                        best = (min(R1, R2), R1, R2, ph, d2, st2)
                prev = cur
    if best is None:
        raise SystemExit("no vertical FPC path found")
    _, R1, R2, phi, d, st = best
    R = min(R1, R2)
    p = Path2D(y0, FPC_Z0, (1, 0))
    p.arc(R1, 1, 90 + math.degrees(phi))
    p.line(d)
    p.arc(R2, -1, math.degrees(phi))
    p.line(st)
    info = {"bend_radius": round(R, 2), "R1": round(R1, 2), "R2": round(R2, 2), "overshoot_deg": round(math.degrees(phi), 1), "diag": round(d, 2),
            "straight_end": round(st, 2), "slot_y": round(p.end[0], 2), "end_z": round(p.end[1], 2),
            "length": round(p.length, 3), "max_y": round(max(q[0] for q in p.pts), 2)}
    return p, info


# -------------------------------------------------------------------------- camera ----
def make_camera():
    ax, ay = P(*AXIS)
    z_pcb = SOCKET_TOP_Z + CAM_HEADER_PLASTIC
    parts = []
    pcb = cq.Workplane("XY", origin=(0, 0, z_pcb)).center(ax, ay).rect(CAM_PCB, CAM_PCB).extrude(CAM_PCB_T)
    parts.append(("OV7670_pcb", pcb.val(), colour(0.10, 0.35, 0.85)))
    jx, jy = P(*J1_CENTRE)
    hdr = (cq.Workplane("XY", origin=(0, 0, SOCKET_TOP_Z)).center(jx, jy)
           .rect(9 * 2.54, 2 * 2.54).extrude(CAM_HEADER_PLASTIC))
    parts.append(("OV7670_header", hdr.val(), colour(0.1, 0.1, 0.1)))
    z_top = z_pcb + CAM_PCB_T
    holder = (cq.Workplane("XY", origin=(0, 0, z_top)).center(ax, ay)
              .rect(CAM_HOLDER[0], CAM_HOLDER[1]).extrude(CAM_HOLDER[2]))
    barrel = (cq.Workplane("XY", origin=(0, 0, z_top + CAM_HOLDER[2])).center(ax, ay)
              .circle(CAM_BARREL_D / 2).extrude(CAM_BARREL_H))
    parts.append(("OV7670_lens_holder", holder.val(), colour(0.08, 0.08, 0.08)))
    parts.append(("OV7670_lens", barrel.val(), colour(0.15, 0.15, 0.15)))
    lens_glass = (cq.Workplane("XY", origin=(0, 0, z_top + CAM_HOLDER[2] + CAM_BARREL_H)).center(ax, ay)
                  .circle(CAM_BARREL_D / 2 - 1.5).extrude(0.05))
    parts.append(("OV7670_lens_glass", lens_glass.val(), colour(0.9, 0.6, 0.9)))
    return parts


def onshape_parts():
    """camera (whole sub-assembly) and TFT body (without its flat FPC) from the Onshape draft"""
    sys.path.insert(0, HERE)
    from step_tree import tree
    _, st, out = tree(ONSHAPE_STEP)
    cam, tft = [], []
    in_cam = False
    for d, nm, bb, loc, lab in out:
        if d == 1:
            in_cam = nm.startswith("Camera OV7670")
            if in_cam:
                cam.append(cq.Shape.cast(st.GetShape_s(lab).Moved(loc)))
            elif nm.startswith("NHD-2.1") and (bb[5] + 23.69) <= OS_TFT_MAX_BY:
                tft.append(cq.Shape.cast(st.GetShape_s(lab).Moved(loc)))
    rows = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]     # (x,y,z) -> (X=x, Y=-z, Z=y)

    def place(shapes, mapped_ref, target, dz):
        dbx, dby = target[0] - mapped_ref[0], target[1] - mapped_ref[1]
        t = (OX + 57.4 + dbx, -(OY + 23.69 + dby), 2.91 + dz)
        return rigid(cq.Compound.makeCompound(shapes), rows, t)

    cam_z = SOCKET_TOP_Z + CAM_HEADER_PLASTIC - OS_CAM_PCB_BOTTOM_Z
    camera = place(cam, OS_HEADER_CENTRE, J1_SOCKET_CENTRE, cam_z)
    display = place(tft, OS_TFT_CENTRE, AXIS, TFT_BACK_Z - OS_TFT_BACK_Z)
    return [("OV7670_module_onshape", camera, colour(0.10, 0.35, 0.85)),
            ("TFT_NHD-2.1-480480AF_onshape", display, colour(0.75, 0.42, 0.10))]


def make_axis_marker():
    ax, ay = P(*AXIS)
    rod = (cq.Workplane("XY", origin=(0, 0, TFT_EYE_Z - 15)).center(ax, ay)
           .circle(0.25).extrude(15 + 45))
    return [("OPTICAL_AXIS_marker", rod.val(), colour(0.0, 0.8, 0.0))]


# ------------------------------------------------------------------------- board ------
def load_board():
    print("loading board STEP ...", flush=True)
    return cq.importers.importStep(BOARD_STEP).val()


def split_j7(board):
    """return (board_without_J7_bodies, J7_body_compound)"""
    keep, j7 = [], []
    for s in board.Solids():
        b = s.BoundingBox()
        bx0, bx1 = b.xmin - OX, b.xmax - OX
        by0, by1 = -b.ymax - OY, -b.ymin - OY
        if (22.5 <= bx0 and bx1 <= 47.5 and 66.9 <= by0 and by1 <= 73.6
                and b.zmax <= 0.0 and b.zmin < -0.5):
            j7.append(s)
        else:
            keep.append(s)
    return cq.Compound.makeCompound(keep), cq.Compound.makeCompound(j7)


def split_substrate(board):
    """(pcb substrate, components) so they can be coloured differently"""
    sub, comp = [], []
    for sld in board.Solids():
        b = sld.BoundingBox()
        if b.xlen > 80 and b.ylen > 70 and b.zmin > -0.05 and b.zmax < 1.65:
            sub.append(sld)
        else:
            comp.append(sld)
    return cq.Compound.makeCompound(sub), cq.Compound.makeCompound(comp)


def add_board(assy, board):
    sub, comp = split_substrate(board)
    assy.add(sub, name="PCB_substrate", color=colour(0.18, 0.45, 0.22))
    assy.add(comp, name="PCB_components", color=colour(0.55, 0.57, 0.60))


def build(variant, board):
    assy = cq.Assembly(name=f"FCL_monocular_{variant}")
    report = {}
    if variant == "vertical":
        add_board(assy, board)
        path, info = fpc_path_vertical()
        report.update(info)
    elif variant == "asplaced":
        add_board(assy, board)
        path = fpc_path_asplaced()
    else:
        rest, j7 = split_j7(board)
        path, opening, info = fpc_path_j7flip()
        report.update(info)
        cy = sum(J7_BODY_Y) / 2
        new_cy = opening + (J7_BODY_Y[1] - J7_BODY_Y[0]) / 2
        cX, cY = P(AXIS[0], cy)
        _, nY = P(AXIS[0], new_cy)
        # rotate 180 deg about Z through the old centre, then move to the new centre
        j7m = rigid(j7, [[-1, 0, 0], [0, -1, 0], [0, 0, 1]], (2 * cX, cY + nY, 0))
        add_board(assy, rest)
        assy.add(j7m, name="J7_FH12_rotated_moved", color=colour(0.95, 0.95, 0.95))
        report["J7_new_body_y"] = (round(opening, 2), round(opening + J7_BODY_Y[1] - J7_BODY_Y[0], 2))
        report["J7_edge_clearance"] = round(BOARD_H - (opening + J7_BODY_Y[1] - J7_BODY_Y[0]), 2)
    report["fpc_needed"] = round(path.length, 2)
    report["fpc_real"] = FPC_LEN
    report["fpc_margin"] = round(FPC_LEN - path.length, 2)
    real = onshape_parts() if os.path.exists(ONSHAPE_STEP) else (make_tft() + make_camera())
    parts_list = (make_cells() + make_contacts() + real + fpc_parts(path, FPC_LEN) + make_axis_marker())
    for name, shp, col in parts_list:
        assy.add(shp, name=name, color=col)
    build.last_parts = parts_list
    return assy, report


def export_views(variant, board):
    """light hidden-line SVG views of the key parts (no small components)"""
    sub, comp = split_substrate(board)
    j7 = [x for x in comp.Solids() if 22 <= x.BoundingBox().xmin - OX and x.BoundingBox().xmax - OX <= 47.5
          and 64.5 <= -x.BoundingBox().ymax - OY and -x.BoundingBox().ymin - OY <= 71 and x.BoundingBox().zmax <= 0.01
          and x.BoundingBox().zmin < -0.5]
    shapes = [sub] + j7 + [p[1] for p in build.last_parts if not p[0].startswith("OPTICAL")]
    comp2 = cq.Compound.makeCompound(shapes)
    for name, d in (("iso_eye", (0.75, -0.55, -1.0)), ("iso_scene", (-0.8, -0.5, 1.0)), ("side", (1, 0, 0))):
        cq.exporters.export(cq.Workplane(obj=comp2), os.path.join(BUILD, f"view_{variant}_{name}.svg"),
                            opt={"projectionDir": d, "showAxes": False, "showHidden": False,
                                 "width": 1500, "height": 1100, "marginLeft": 20, "marginTop": 20,
                                 "strokeWidth": 0.15})
        print("svg", name, flush=True)


def main():
    variants = sys.argv[1:] or ["asplaced", "j7flip"]
    board = load_board()
    for v in variants:
        assy, rep = build(v, board)
        print(v, rep, flush=True)
        step = os.path.join(BUILD, f"FCL_assembly_{v}.step")
        assy.export(step)
        try:
            assy.export(os.path.join(BUILD, f"FCL_assembly_{v}.glb"), tolerance=0.1, angularTolerance=0.5)
        except Exception as e:  # GLB is a convenience only
            print("GLB export failed:", e)
        print("wrote", step, flush=True)
        if v == "vertical":
            export_views(v, board)


if __name__ == "__main__":
    main()
