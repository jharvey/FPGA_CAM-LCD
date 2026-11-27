#!/usr/bin/env python3
"""FCL monocular - battery end block, cell cradle and clamshell case (draft 1).

Run on top of build_assembly.py (same frame: board (x, y) -> STEP (78 + x, -(55.5 + y)),
PCB back face = eye side at Z 0, front/camera side at Z +1.6).

    python case/assembly/build_case.py            # parts + checks + assembly STEP
    python case/assembly/build_case.py --noassy   # parts + checks only
    FCL_BATTERY=fixed python case/assembly/build_case.py     # fixed cells: spring contacts BT13 / BT23 / BT33, no blocks
                                                             # or caps, closed side walls -> FCL_case_rear_fixed / _front_fixed

Outputs
    case/print/FCL_battery_block.step/.stl   metal block (three open bores, cells exit at x < 0)
    case/print/FCL_cell_cradle.step/.stl     printed cradle between PCB and TFT
    case/print/FCL_case_rear.step/.stl       eye-side shell (TFT window)
    case/print/FCL_case_front.step/.stl      camera-side shell (lens turret)
    case/build/FCL_case_assembly.step        everything together
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_assembly as A  # noqa: E402
import cadquery as cq  # noqa: E402

PRINT = os.path.join(A.REPO, "case", "print")
if os.environ.get("FCL_BOARD_STEP"):
    A.BOARD_STEP = os.environ["FCL_BOARD_STEP"]      # e.g. the battery-blocks board with J7 vertical
BLOCK_STEP = os.environ.get("FCL_BLOCK_STEP", os.path.join(A.REPO, "case", "models", "ms3181", "blockms_A_boardframe.step"))      # aluminium block, board frame (scripts/make_battery_block_step.py)
LEFT_AXES = (15.5, 56.5)                               # cells 1 and 3 leave on the left (blocks BT12 / BT32 on the PCB)
RIGHT_AXIS = 36.0                                      # cell 2 is reversed and leaves on the right
RING_X, RING_HALF = (-3.0, -0.2), 14.0                 # block shoulder plate (MS3181 bayonet boss sticks out beyond)
MS_DIR = os.environ.get("FCL_MS3181_DIR", os.path.join(A.REPO, "case", "models", "ms3181"))          # tmp3d with blockms_*_boardframe.step + ms3181_*.step
BLK_ZB = A.CELL_AXIS_Z - 14.0                          # -25.8
RIGHT_LIFT = 0.0                                       # right block: screwed down like the others
PARTS = os.path.join(A.BUILD, "case_parts")
FIXED = os.environ.get("FCL_BATTERY", "") == "fixed"   # cells soldered in between the + contact and the MY-18650-05-J spring
SUFFIX = "_fixed" if FIXED else ""
if FIXED:
    PARTS = os.path.join(A.BUILD, "case_parts_fixed")
    MS_DIR = ""                                        # no blocks, no MS3181 caps

# ------------------------------------------------------------------ parameters --------
W, H, T = 85.0, 79.0, A.PCB_T        # board
PCB_R = 3.0                          # board corner radius
ROWS = A.CELL_ROWS
CZ = A.CELL_AXIS_Z                   # -11.8

# battery end block (metal, on the common / - side; replaces BT12, BT22, BT32)
BLK_X = (-3.0, 5.5)                  # flush with the case outside, stops short of the TFT
BLK_Y = (2.2, 68.5)
BLK_Z = -23.1                        # 2.0 mm of metal beyond the cells
BLK_BORE = 19.2                      # generic through bore, 18650 slides out
H1 = (5.7, 4.1)                      # M3 GND hole -> tapped foot
H4 = (10.2, 47.9)                    # M3 GND hole -> thin tab under cells 2/3
BLK_S1, BLK_S2 = (3.2, -10.3), (3.5, 9.3)   # block screws, block frame (x in from the edge, y along it, from the cell axis)

# cell cradle (printed, sits on the PCB back, open toward the TFT)
CR_X = (15.0, 75.0)
CR_Y = (4.4, 67.6)
CR_Z = -17.0                         # 5.2 mm past the cell axis: lips keep the cells in
CR_BORE = 19.1

# case
CLR = 0.5                            # PCB edge -> wall
WALL = 2.5
OFF = CLR + WALL                     # 3.0
LEDGE = 1.0                          # PCB overlap on the rear ledge / front lip
OUT_R = 4.0
Z_REAR_IN = -24.2                    # TFT eye face is at -23.87
Z_REAR_OUT = Z_REAR_IN - 2.0
Z_FRONT_IN = 19.2                    # camera PCB parts reach 18.6
Z_FRONT_OUT = Z_FRONT_IN + 2.0
LENS_C = (34.88, 36.29)              # centre of the lens holder body (24 x 17.5)
LENS_R_IN = 15.3
LENS_TOP = 33.2                      # lens reaches 32.6
WINDOW_D = 54.0                      # TFT active area is 53.28
LOBES = ((-1.5, -1.5), (86.5, -1.5), (-1.5, 80.5), (86.5, 80.5))   # case screws, inside the square outline
LOBE_R = 4.0
OUT_X, OUT_Y = (-6.0, 91.0), (-6.0, 85.0)  # outer outline (board 85 x 79 + 6 mm all round)
OUT_RC = 6.5                         # vertical corner radius
# camera: the OV7670 board (34 x 35, from the Onshape model) is located by a frame round its edges and held down
# onto the J1 header by four corner posts (0.05 mm preload) from the front shell
CAM_PLATE = (17.88, 24.04, 51.88, 59.04, 12.6, 14.1)
# tripod: 1/4"-20 UNC heat-set insert (e.g. 9.5 OD x 9.5 long class; check the insert datasheet for the hole)
TRIPOD_X, TRIPOD_Z = 62.0, -12.0     # bottom face, rear shell; clear of the LCD ribbon (x 18-52)
TRIPOD_HOLE, TRIPOD_DEPTH = 8.2, 10.5
TRIPOD_BOSS_D, TRIPOD_BOSS_IN = 13.0, 73.5   # boss reaches in to board y 73.5 (insert fully supported)
CAM_FRAME_CLR, CAM_FRAME_W, CAM_FRAME_DOWN = 0.2, 1.4, 1.2
CAM_POST_D, CAM_PRELOAD = 6.0, 0.0
SPRING_ROOT = 6.8                    # x where the spring leaves its plate (plate back face is at 6.03)
CRF_X0 = 1.3                         # fixed cells: the PCB-side cradle runs to 0.3 mm from the shell side walls
RIB_X1 = 5.75                        # ... and its end wall is 0.28 mm behind each contact plate
RIB_Z1 = -2.0                        # pocket over the solder feet and fillets
PLATE_HY = 7.3                       # contact plate is 13.8 wide: 0.4 mm each side
SLOT_HY = 5.0                        # spring coil is 5.9 wide, + bump root 9.0: slot so the cradle drops over them
CAM_HOLES = ((20.4, 26.5), (49.4, 26.5), (20.4, 56.5), (49.4, 56.5))   # 3.0 mm holes in the OV7670 board (Onshape model)
INSERT_L = 4.0                       # M2.5 heat-set insert length
# button plunger snap: barb at the outer end clicks into a counterbore in the eye face
ACT_CB_D, ACT_CB_DEPTH = 5.2, 1.8    # counterbore in the rear face
ACT_BARB_D, ACT_BARB_GAP, ACT_SLOT = 4.4, 0.8, 0.9
# LCD-side cell cradle: between the cells and the TFT, top face supports the TFT back, outside the TFT it fills to the shell
TOPCR_Z = -17.2                      # meets the PCB-side cradle (which ends at -17.0)
TFT_SUPPORT_Z = -21.55               # 0.05 below the TFT back face (-21.6)
CHAMF = 2.0                          # chamfer round the outer (eye / camera) faces
SEAM = 0.6                           # small chamfer each side of the parting line -> V reveal
# camera hood / visor (part of the front shell); visor is longer on the top edge (board y = 0 side)
HOOD_HI, HOOD_LO = 11.0, 4.0         # above the lens turret top, top / bottom of the slanted lip
HOOD_WALL = 2.0
HOOD_HALF_ANGLE = 40.0               # deg: assumed lens half field (stock OV7670 lens ~70 deg diag) + margin
LENS_AP_R = 4.5                      # lens front glass radius (build_assembly: barrel 12 - 1.5)
LENS_FRONT = 32.6                    # lens front face Z
# buttons: B1 / B2 PTS645 on the PCB back (eye side) -> printed actuators through the rear face;
# B4 RESET / B3 BOOT (KMR2, camera side) -> 1.6 mm pin holes in the front face.  B0 PWR is under cell 3 (see notes).
ACT_STEM, ACT_HOLE, ACT_FLANGE = 3.4, 3.8, 5.0
ACT_PROUD = 0.6
# two-piece button: the plunger's split end and barb sit in the counterbore, under a cap pressed on from outside;
# the cap's tongue fills the split, so the barb can no longer close and the plunger is captive
CAP_D, CAP_PROUD, CAP_SEAT = 4.8, 0.8, 0.05     # cap disc, how far it stands out of the face, seat below the face
TONGUE_W, TONGUE_L, TONGUE_D = 0.8, 2.8, 1.15  # into the 0.9 mm split of the plunger
PINHOLES = ((53.2, 12.0), (80.1, 22.1))
GUIDE_OD = 5.6                       # guide tube for the actuators, from the rear inner face toward the PCB
GUIDE_TOP = -15.6                    # stops short of cell 1 (its can reaches y 6.2 at Z -11.8)
RET_Z = -17.2                        # cell retainer saddles: from the rear inner face down to 0.2 above the cradle
RET_TFT_CLR = 31.5                   # keep clear of the TFT + its locating ring (OD/2 + 1.9 + 0.5)
KO_T, KO_WEB, KO_RIM = 1.2, 0.4, 0.6 # break-out panels: thickness, outer skin left in the groove, groove width
INSERT_D = 3.6                       # M2.5 heat-set insert
SCREW_D = 2.9
HEAD_D = 5.2
USB_CUT = (82.0, 65.9, 92.5, 77.4, -0.2, 6.8)   # J17 mouth is 3.5 mm inside the right edge
SD_CUT = (28.0, -7.5, 42.0, 1.6, T, T + 2.6)
BUTTONS = ((16.0, 4.0), (26.5, 4.0), (9.0, 4.0))       # B1, B2, B0 (power, KMR2, moved here 2026-11-26)
BLK_KEEP = (-10.0, 2.7, 7.3, 29.0)        # cell-1 block flange (x <= 7.0 from y 3.0): plunger / guide of B0 cut clear
# ports: fully open for the prototype; the wall around them is pocketed from outside so the plug / card reaches
USB_POCKET = (87.0, 65.2, 92.0, 78.1, -1.0, 7.6)   # USB-C overmold (12.4 x 7 typ.): wall left 1.5 mm, plug reaches J17
SD_SCOOP = (26.5, -7.0, 43.5, -3.0, 0.4, 6.0)      # finger scoop in front of the microSD slot


# ------------------------------------------------------------------ helpers -----------
def box(x0, y0, x1, y1, z0, z1):
    X0, Y0 = A.P(x0, y0)
    X1, Y1 = A.P(x1, y1)
    return (cq.Workplane("XY").box(abs(X1 - X0), abs(Y1 - Y0), abs(z1 - z0), centered=False)
            .translate((min(X0, X1), min(Y0, Y1), min(z0, z1))))


def rrect(x0, y0, x1, y1, z0, z1, r):
    return box(x0, y0, x1, y1, z0, z1).edges("|Z").fillet(r)


def zcyl(x, y, r, z0, z1):
    X, Y = A.P(x, y)
    return cq.Workplane("XY").circle(r).extrude(abs(z1 - z0)).translate((X, Y, min(z0, z1)))


def xcyl(x0, x1, y, z, r):
    X0, Y = A.P(x0, y)
    return cq.Workplane("YZ").circle(r).extrude(x1 - x0).translate((X0, Y, z))


def bb(s):
    b = s.BoundingBox()
    return (b.xmin - A.OX, -b.ymax - A.OY, b.xmax - A.OX, -b.ymin - A.OY, b.zmin, b.zmax)


def classify(board):
    """-> substrate, kept component solids, removed spring contacts, back boxes, front boxes"""
    sub, comp, springs, back, front = [], [], [], [], []
    for s in board.Solids():
        x0, y0, x1, y1, z0, z1 = bb(s)
        yc = (y0 + y1) / 2
        is_spring = z0 < -4 and ((x1 < 25 and any(abs(yc - r) < 2 for r in LEFT_AXES)) or
                                 (x0 > 60 and abs(yc - RIGHT_AXIS) < 2))
        if x1 - x0 > 80 and y1 - y0 > 70:
            sub.append(s)
        elif FIXED and z1 - z0 > 20 and (x0 < -2 or x1 > W + 2):
            springs.append(("block", s))     # fixed cells: the blocks are not fitted
        elif is_spring and not (x0 < -2 and z1 - z0 > 20):
            springs.append(("spring" if FIXED else "bt22", s))   # MY-18650-05-J springs: kept only for fixed cells
        elif x0 < -2 and z1 - z0 > 20:
            springs.append(("block", s))     # left aluminium blocks (footprint 3D models)
        elif x1 > W + 2 and z1 - z0 > 20:
            springs.append(("blockR", s))    # right block model on the board: drawn by make_right_block() instead
        elif z0 < -10 and x0 > 60 and 28 < y0 < 30:
            springs.append(("bt22", s))      # BT22 spring: replaced by the right block
        else:
            comp.append(s)
            if z0 < -0.12:
                back.append((x0, y0, x1, y1, z0, min(z1, 0.0)))
            if z1 > T + 0.12:
                front.append((x0, y0, x1, y1, max(z0, T), z1))
    return sub, comp, springs, back, front


def cut_boxes(part, boxes, grow, zgrow, name):
    """subtract inflated component boxes that touch the part"""
    px0, py0, px1, py1, pz0, pz1 = bb(part.val())
    n = 0
    for (x0, y0, x1, y1, z0, z1) in boxes:
        if x1 + grow < px0 or x0 - grow > px1 or y1 + grow < py0 or y0 - grow > py1:
            continue
        if z1 + zgrow < pz0 or z0 - zgrow > pz1:
            continue
        tool = box(x0 - grow, y0 - grow, x1 + grow, y1 + grow, z0 - zgrow, z1 + zgrow)
        new = part.cut(tool)
        if abs(new.val().Volume() - part.val().Volume()) > 1e-6:
            n += 1
            part = new
    print(f"  {name}: relieved for {n} components", flush=True)
    return part


# ------------------------------------------------------------------ parts -------------
def make_right_block():
    """block part A turned 180 deg about the vertical axis so its ring faces +x, cell-2 axis (board y 36)"""
    from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    blk = cq.importers.importStep(BLOCK_STEP).val()         # board frame: x from the edge, y +down from the axis
    # board frame -> STEP for a left block on axis y0:  X = OX + x, Y = -(OY + y0 + y)   (a mirror in y, as the PCB frame)
    t1 = gp_Trsf()
    t1.SetValues(1, 0, 0, A.OX, 0, -1, 0, -(A.OY + RIGHT_AXIS), 0, 0, 1, 0)
    left = cq.Shape.cast(BRepBuilderAPI_Transform(blk.wrapped, t1, True).Shape())
    r = gp_Trsf()
    r.SetRotation(gp_Ax1(gp_Pnt(A.OX + 42.5, -(A.OY + RIGHT_AXIS), 0), gp_Dir(0, 0, 1)), 3.141592653589793)
    right = cq.Shape.cast(BRepBuilderAPI_Transform(left.wrapped, r, True).Shape())
    return cq.Workplane(obj=right.translate(cq.Vector(0, 0, -RIGHT_LIFT)))


def place(shape, y0, right=False):
    """block-frame shape -> assembly STEP frame for a cell axis at board y0 (left side, or right side turned 180 deg)"""
    from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    t1 = gp_Trsf()
    t1.SetValues(1, 0, 0, A.OX, 0, -1, 0, -(A.OY + y0), 0, 0, 1, 0)
    out = cq.Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, t1, True).Shape())
    if right:
        r = gp_Trsf()
        r.SetRotation(gp_Ax1(gp_Pnt(A.OX + 42.5, -(A.OY + y0), 0), gp_Dir(0, 0, 1)), 3.141592653589793)
        out = cq.Shape.cast(BRepBuilderAPI_Transform(out.wrapped, r, True).Shape())
    return out


def ms3181_parts():
    """left blocks (A at 15.5, B at 56.5) and the three cap stacks (cap, gasket, disc, O-ring, spring, pins, slug)"""
    imp = lambda n: cq.importers.importStep(os.path.join(MS_DIR, n)).val()
    blocks = [place(imp("blockms_A_boardframe.step"), 15.5), place(imp("blockms_B_boardframe.step"), 56.5)]
    common = [imp(f"ms3181_{n}.step") for n in ("cap", "gasket", "disc", "oring", "spring", "pins")]
    caps, slugs = [], []
    for y0, right in ((15.5, False), (56.5, False), (RIGHT_AXIS, True)):
        caps += [place(c, y0, right) for c in common]
        slugs.append(place(imp("ms3181_slug_R.step" if right else "ms3181_slug_L.step"), y0, right))
        if right:   # the right block is drawn RIGHT_LIFT off the PCB; its cap stack follows it
            caps[-6:] = [c.translate(cq.Vector(0, 0, -RIGHT_LIFT)) for c in caps[-6:]]
            slugs[-1] = slugs[-1].translate(cq.Vector(0, 0, -RIGHT_LIFT))
    return cq.Compound.makeCompound(blocks), cq.Compound.makeCompound(caps), cq.Compound.makeCompound(slugs)


def cap_clear():
    """clearance for the MS3181 caps (31.8 max OD + 0.7) where they pass the case corner lobes"""
    c = None
    for y0 in LEFT_AXES:
        k = xcyl(-21.0, -2.9, y0, A.CELL_AXIS_Z, 16.6)
        c = k if c is None else c.union(k)
    return c.union(xcyl(W + 2.9, W + 21.0, RIGHT_AXIS, A.CELL_AXIS_Z, 16.6))


def outline(z0, z1, outer_low):
    """square outer body with corner radius; CHAMF on the outer face, SEAM on the parting-line face"""
    o = rrect(OUT_X[0], OUT_Y[0], OUT_X[1], OUT_Y[1], z0, z1, OUT_RC)
    if outer_low:
        return o.faces("<Z").chamfer(CHAMF).faces(">Z").chamfer(SEAM)
    return o.faces(">Z").chamfer(CHAMF).faces("<Z").chamfer(SEAM)


def zcone(x, y, r0, r1, z0, z1):
    X, Y = A.P(x, y)
    return cq.Workplane(obj=cq.Solid.makeCone(r0, r1, z1 - z0, cq.Vector(X, Y, z0), cq.Vector(0, 0, 1)))


def make_hood():
    """lens turret extension with a slanted visor lip (high on the top edge), inner light-trap grooves"""
    import math
    cx, cy = LENS_C
    r_in, r_out = LENS_R_IN, LENS_R_IN + HOOD_WALL
    ztop = LENS_TOP + HOOD_HI
    h = zcyl(cx, cy, r_out, LENS_TOP - 0.01, ztop).cut(zcyl(cx, cy, r_in, LENS_TOP - 1, ztop + 1))
    # slanted cut: Z = LENS_TOP + HOOD_LO at the bottom side, LENS_TOP + HOOD_HI at the top side (STEP +Y = board top)
    X, Yc = A.P(cx, cy)
    zlo, zhi = LENS_TOP + HOOD_LO, LENS_TOP + HOOD_HI
    m = (zhi - zlo) / (2 * r_out)
    pts = [(Yc - 40, zlo - m * (40 - r_out)), (Yc + 40, zlo + m * (40 + r_out)), (Yc + 40, 200), (Yc - 40, 200)]
    wedge = cq.Workplane("YZ", origin=(X - 40, 0, 0)).polyline(pts).close().extrude(80)
    h = h.cut(wedge)
    for dz in (1.5, 4.0, 6.5):                                   # light-trap grooves inside
        h = h.cut(zcyl(cx, cy, r_in + 0.6, LENS_TOP + dz, LENS_TOP + dz + 0.8).cut(zcyl(cx, cy, r_in - 0.01, LENS_TOP, ztop)))
    # field-of-view check: the highest lip must stay outside the view cone from the lens front glass
    need = LENS_AP_R + (zhi - LENS_FRONT) * math.tan(math.radians(HOOD_HALF_ANGLE))
    print(f"  hood: lip {HOOD_LO}..{HOOD_HI} mm above the turret, view cone radius at the top lip {need:.1f} "
          f"<= bore {r_in:.1f}: {'OK' if need <= r_in else 'VIGNETTES'}", flush=True)
    return h


def cam_support():
    x0, y0, x1, y1, zb, zt = CAM_PLATE
    c, w = CAM_FRAME_CLR, CAM_FRAME_W
    zlo = zt - CAM_FRAME_DOWN
    frame = box(x0 - c - w, y0 - c - w, x1 + c + w, y1 + c + w, zlo, Z_FRONT_IN + 0.01).cut(
        box(x0 - c, y0 - c, x1 + c, y1 + c, zlo - 1, Z_FRONT_IN + 1))
    for (px, py) in CAM_HOLES:
        frame = frame.union(zcyl(px, py, CAM_POST_D / 2, zt - CAM_PRELOAD, Z_FRONT_IN + 0.01))
        frame = frame.cut(zcyl(px, py, INSERT_D / 2, zt - 1, zt + INSERT_L + 0.5))
    return frame


def ycyl(x, y0, y1, z, r):
    """cylinder along board y from y0 to y1 (board coords)"""
    X, Y0 = A.P(x, y0)
    _, Y1 = A.P(x, y1)
    d = cq.Vector(0, 1 if Y1 > Y0 else -1, 0)
    return cq.Workplane(obj=cq.Solid.makeCylinder(r, abs(Y1 - Y0), cq.Vector(X, Y0, z), d))


def tripod(part):
    part = part.union(ycyl(TRIPOD_X, OUT_Y[1] - 0.5, TRIPOD_BOSS_IN, TRIPOD_Z, TRIPOD_BOSS_D / 2))
    part = part.cut(ycyl(TRIPOD_X, OUT_Y[1] + 1, OUT_Y[1] - TRIPOD_DEPTH, TRIPOD_Z, TRIPOD_HOLE / 2))
    return part.cut(ycyl(TRIPOD_X, OUT_Y[1] + 0.01, OUT_Y[1] - 0.8, TRIPOD_Z, TRIPOD_HOLE / 2 + 0.6))   # lead-in


def make_top_cradle(tft_bb):
    """LCD-side cradle: cells enclosed with the PCB-side cradle; flat top supports the TFT back face; outside the
    TFT circle it rises to the rear shell so the stack is clamped when the case closes"""
    tx = (tft_bb[0] + tft_bb[2]) / 2
    ty = tft_bb[1] + A.TFT_OD / 2
    CX0, CX1 = (CRF_X0, W - CRF_X0) if FIXED else CR_X      # same length and width as the PCB-side support
    c = box(CX0, CR_Y[0], CX1, CR_Y[1], TFT_SUPPORT_Z, TOPCR_Z)
    outer = box(CX0, CR_Y[0], CX1, CR_Y[1], Z_REAR_IN + 0.2, TFT_SUPPORT_Z + 0.01).cut(
        zcyl(tx, ty, RET_TFT_CLR, Z_REAR_IN - 1, 1))
    c = c.union(outer)
    for row in ROWS:
        c = c.cut(xcyl(CX0 - 1, CX1 + 1, row, CZ, CR_BORE / 2))
    # crest slots under the TFT (the skin over each cell crest would be 0.2 mm): 8 mm wide, 1 mm into the bore
    tcyl = zcyl(tx, ty, RET_TFT_CLR - 0.5, Z_REAR_IN - 1, 1)
    for row in ROWS:
        slot = box(CX0 - 1, row - 4.0, CX1 + 1, row + 4.0, TFT_SUPPORT_Z - 0.3, CZ - CR_BORE / 2 + 1.0)
        c = c.cut(slot.intersect(tcyl))
    # TFT flat tail / ribbon exit (same opening as the locating ring in the rear shell)
    c = c.cut(box(tx - 18.5, ty + 18.0, tx + 18.5, H, Z_REAR_IN - 1, TFT_SUPPORT_Z))
    for (x, y) in BUTTONS:
        c = c.cut(zcyl(x, y, GUIDE_OD / 2 + 0.4, Z_REAR_IN - 1, 1))
        c = c.cut(zcyl(x, y, ACT_FLANGE / 2 + 0.4, Z_REAR_IN - 1, 1))
    print("  LCD-side cradle volume", round(c.val().Volume() / 1000, 2), "cm3", flush=True)
    return c


def hardware(back_lobe_z=None):
    """simplified fasteners: M2.5 socket head screws (head 4.5 x 2.5) and M2.5 heat-set inserts (3.6 x 4.0)"""
    def screw(x, y, z_head_bottom, length, up):
        # up=True: head below, shank going +Z; up=False: head above, shank going -Z
        if up:
            return zcyl(x, y, 2.25, z_head_bottom - 2.5, z_head_bottom).union(zcyl(x, y, 1.25, z_head_bottom, z_head_bottom + length))
        return zcyl(x, y, 2.25, z_head_bottom, z_head_bottom + 2.5).union(zcyl(x, y, 1.25, z_head_bottom - length, z_head_bottom))

    def union_all(ws):
        w = None
        for x in ws:
            w = x if w is None else w.union(x)
        return w
    out = {}
    out["hw_case_screws"] = union_all([screw(x, y, T + 3.0, 10.0, False) for (x, y) in LOBES])
    out["hw_case_inserts"] = union_all([zcyl(x, y, INSERT_D / 2 - 0.05, -5.0, -1.0) for (x, y) in LOBES])
    zt = CAM_PLATE[5]
    out["hw_cam_screws"] = union_all([screw(x, y, CAM_PLATE[4], 6.0, True) for (x, y) in CAM_HOLES])
    out["hw_cam_inserts"] = union_all([zcyl(x, y, INSERT_D / 2 - 0.05, zt + 0.3, zt + 0.3 + INSERT_L) for (x, y) in CAM_HOLES])
    # block screws: M1.6 x 5 socket head from the camera side, two per block (S1, S2); 0.5 mm washer under the block
    loc = (BLK_S1, BLK_S2)
    blk = [(x, y0 + y) for y0 in LEFT_AXES for (x, y) in loc] + [(W - x, RIGHT_AXIS - y) for (x, y) in loc]
    out["hw_block_screws"] = union_all([zcyl(x, y, 1.5, T, T + 1.6).union(zcyl(x, y, 0.8, T - 5.0, T)) for (x, y) in blk])
    out["hw_block_washers"] = union_all([zcyl(x, y, 2.25, -0.5, 0.0).cut(zcyl(x, y, 0.85, -1, 1)) for (x, y) in blk])
    return out


def guides():
    w = None
    for (x, y) in BUTTONS:
        t = zcyl(x, y, GUIDE_OD / 2, Z_REAR_IN - 0.01, GUIDE_TOP).cut(zcyl(x, y, ACT_HOLE / 2, Z_REAR_IN - 1, GUIDE_TOP + 1))
        w = t if w is None else w.union(t)
    return w.cut(box(*BLK_KEEP, Z_REAR_IN - 1, 2.0))


def retainer(tft_bb):
    """saddles over the cells where the TFT does not cover them (cells slide out along x, so plain bores)"""
    import math
    tx = (tft_bb[0] + tft_bb[2]) / 2
    ty = tft_bb[1] + A.TFT_OD / 2
    w = None
    for row in ROWS:
        dy = abs(row - ty)
        x0 = tx + math.sqrt(RET_TFT_CLR ** 2 - dy ** 2) if dy < RET_TFT_CLR else CR_X[0]
        if x0 > CR_X[1] - 3:
            continue
        y0, y1 = max(row - 11.0, CR_Y[0]), min(row + 11.0, CR_Y[1])
        b = box(x0, y0, CR_X[1], y1, Z_REAR_IN - 0.01, RET_Z)
        w = b if w is None else w.union(b)
    for row in ROWS:
        w = w.cut(xcyl(CR_X[0] - 1, CR_X[1] + 1, row, CZ, CR_BORE / 2))
    w = w.cut(zcyl(tx, ty, RET_TFT_CLR, Z_REAR_IN - 1, 1))
    print("  retainer saddles volume", round(w.val().Volume() / 1000, 2), "cm3", flush=True)
    return w


def knockout(part, cut, axis, face, sign, zlim):
    """thin break-out panel filling a port opening: KO_T thick at the outer face, held by a KO_WEB skin
    around a groove cut from the inside.  axis 'x' or 'y' (board coords), face = outer face coordinate,
    sign = +1 if the outside is toward +axis.  zlim = (z0, z1) of this shell."""
    x0, y0, x1, y1, z0, z1 = cut
    z0, z1 = max(z0, zlim[0]), min(z1, zlim[1])
    if z1 - z0 < 0.5:
        return part
    inner = face - sign * KO_T
    if axis == "x":
        a0, a1 = sorted((inner, face))
        panel = box(a0, y0, a1, y1, z0, z1)
        g0, g1 = sorted((inner - sign * 0.01, face - sign * KO_WEB))
        ring = box(g0, y0 - 0.01, g1, y1 + 0.01, z0 - 0.01, z1 + 0.01).cut(
            box(g0 - 1, y0 + KO_RIM, g1 + 1, y1 - KO_RIM, z0 + KO_RIM, z1 - KO_RIM))
    else:
        a0, a1 = sorted((inner, face))
        panel = box(x0, a0, x1, a1, z0, z1)
        g0, g1 = sorted((inner - sign * 0.01, face - sign * KO_WEB))
        ring = box(x0 - 0.01, g0, x1 + 0.01, g1, z0 - 0.01, z1 + 0.01).cut(
            box(x0 + KO_RIM, g0 - 1, x1 - KO_RIM, g1 + 1, z0 + KO_RIM, z1 - KO_RIM))
    return part.union(panel.cut(ring))


def button_z(back):
    """plunger top Z of the PTS645 buttons (lowest Z of the back-side box over each button position)"""
    zs = []
    for (bx, by) in BUTTONS:
        zz = [b[4] for b in back if b[0] <= bx <= b[2] and b[1] <= by <= b[3]]
        zs.append(min(zz) if zz else -4.3)
    return zs


def make_actuators(back):
    """two-piece buttons. Plunger: flange inside the rear shell, stem down the guide, split barb that clicks into the
    counterbore in the eye face. Cap: a plain disc pressed on from outside, its tongue into the plunger's split."""
    w = caps = None
    for (x, y), zb in zip(BUTTONS, button_z(back)):
        z_seat = Z_REAR_OUT + CAP_SEAT                       # plunger end = cap underside
        a = zcyl(x, y, ACT_STEM / 2, z_seat, zb - 0.1)
        a = a.edges(">Z").fillet(0.6)
        a = a.union(zcyl(x, y, ACT_FLANGE / 2, GUIDE_TOP + 0.2, GUIDE_TOP + 1.0))
        zf = Z_REAR_OUT + ACT_CB_DEPTH                       # counterbore floor
        zs = zf - ACT_BARB_GAP                               # barb catch face (travel ACT_BARB_GAP before it touches)
        a = a.union(zcone(x, y, ACT_STEM / 2, ACT_BARB_D / 2, zs - 0.9, zs))
        a = a.cut(box(x - ACT_SLOT / 2, y - 3, x + ACT_SLOT / 2, y + 3, z_seat - 1, zs + 4.0))
        a = a.cut(box(*BLK_KEEP, Z_REAR_IN - 1, 2.0))              # B0: flange flattened beside the cell-1 block
        w = a if w is None else w.union(a)
        c = zcyl(x, y, CAP_D / 2, Z_REAR_OUT - CAP_PROUD, z_seat).edges("<Z").fillet(0.3)
        c = c.union(box(x - TONGUE_W / 2, y - TONGUE_L / 2, x + TONGUE_W / 2, y + TONGUE_L / 2, z_seat - 0.01, z_seat + TONGUE_D))
        caps = c if caps is None else caps.union(c)
    print("  button plunger tops Z:", [round(z, 2) for z in button_z(back)], flush=True)
    return w, caps


def spring_parts(solids):
    """spring contacts from the board STEP; the spring itself is squeezed along x so it ends on the cell's - end
    (the model is the free spring, 11.1 mm long; fitted it is about 5.4 mm)"""
    from OCP.gp import gp_GTrsf, gp_Mat, gp_XYZ
    from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
    x_end = A.CELL_PLUS_X - A.CELL_L                     # 12.2
    out = []
    for sp in solids:
        b = bb(sp)
        left = b[0] < W / 2
        xs = SPRING_ROOT if left else W - SPRING_ROOT    # plate | spring
        xe = x_end if left else W - x_end
        f = (xe - xs) / ((b[2] if left else b[0]) - xs)
        lo, hi = box(-5, -5, xs, H + 5, -40, 10), box(xs, -5, W + 5, H + 5, -40, 10)
        try:
            plate = cq.Workplane(obj=sp).intersect(lo if left else hi).val()
            coil = cq.Workplane(obj=sp).intersect(hi if left else lo).val()
            g = gp_GTrsf()
            g.SetVectorialPart(gp_Mat(f, 0, 0, 0, 1, 0, 0, 0, 1))
            g.SetTranslationPart(gp_XYZ((A.OX + xs) * (1 - f), 0, 0))
            coil = cq.Shape.cast(BRepBuilderAPI_GTransform(coil.wrapped, g, True).Shape())
            print(f"  spring at x {b[0]:.1f}..{b[2]:.1f}: squeezed to {f * 100:.0f} % of its free length", flush=True)
            out += [plate, coil]
            continue
        except Exception as e:
            print("  spring not squeezed:", e, flush=True)
        out.append(sp)
    return cq.Compound.makeCompound(out)


def is_plus_contact(sol):
    """MY-18650-04-J: a 0.3 mm plate with a bump, at the + end of each cell"""
    x0, y0, x1, y1, z0, z1 = bb(sol)
    return z0 < -10 and x1 - x0 < 6 and z1 - z0 < 25 and any(abs((y0 + y1) / 2 - r) < 2 for r in ROWS)


def make_cells2():
    """cells 1 and 3: - end left (block), + nub right; cell 2 reversed: + nub left, - end right (block)"""
    parts = []
    x0, x1 = A.CELL_PLUS_X - A.CELL_L, A.CELL_PLUS_X
    for i, row in enumerate(ROWS, 1):
        X0, Y = A.P(x0, row)
        X1, _ = A.P(x1, row)
        if FIXED and i == 2:      # fixed: cell 2 sits against its + contact on the left (mirror of cells 1 and 3)
            X0, Y = A.P(W - A.CELL_PLUS_X, row)
        if i == 2:
            can = cq.Workplane("YZ", origin=(X0 + 0.8, Y, CZ)).circle(A.CELL_D / 2).extrude(A.CELL_L - 0.8)
            nub = cq.Workplane("YZ", origin=(X0, Y, CZ)).circle(4.0).extrude(0.8)
        else:
            can = cq.Workplane("YZ", origin=(X0, Y, CZ)).circle(A.CELL_D / 2).extrude(A.CELL_L - 0.8)
            nub = cq.Workplane("YZ", origin=(X1 - 0.8, Y, CZ)).circle(4.0).extrude(0.8)
        parts.append((f"CELL{i}", can.union(nub).val(), A.colour(0.85, 0.45, 0.75)))
    return parts


def ring_cut(y0, side, z0=None, z1=None):
    """opening in a shell for a block ring (left: x < 0, right: x > 85), 0.3 mm clearance"""
    zz0 = BLK_ZB - 0.3 if z0 is None else z0
    zz1 = A.CELL_AXIS_Z + RING_HALF + 0.3 if z1 is None else z1
    if side == "L":
        return box(RING_X[0] - 2, y0 - RING_HALF - 0.3, RING_X[1] + 0.3, y0 + RING_HALF + 0.3, zz0, zz1)
    return box(W - RING_X[1] - 0.3, y0 - RING_HALF - 0.3, W - RING_X[0] + 2, y0 + RING_HALF + 0.3, zz0, zz1)


def make_cradle(back):
    if not FIXED:
        c = box(CR_X[0], CR_Y[0], CR_X[1], CR_Y[1], CR_Z, 0)
        for row in ROWS:
            c = c.cut(xcyl(CR_X[0] - 1, CR_X[1] + 1, row, CZ, CR_BORE / 2))
    else:
        # fixed cells: the cradle goes on over the soldered contacts and backs up every contact plate, so the push of
        # the spring is carried from one end wall to the other inside the cradle (not by the solder joints).
        # Order: cradle onto the PCB, cells in, LCD-side cradle on, then the stack into the rear shell.
        c = box(CRF_X0, CR_Y[0], W - CRF_X0, CR_Y[1], CR_Z, 0)
        for i, row in enumerate(ROWS):
            c = c.cut(xcyl(RIB_X1, W - RIB_X1, row, CZ, CR_BORE / 2))
            for left in (True, False):
                spring_end = left == (i != 1)            # cells 1 and 3: spring on the left; cell 2: on the right

                def bx(x0, x1, hy, z0, z1):
                    if left:
                        return box(x0, row - hy, x1, row + hy, z0, z1)
                    return box(W - x1, row - hy, W - x0, row + hy, z0, z1)
                c = c.cut(bx(RIB_X1, 7.0, PLATE_HY, CR_Z - 1, 0.1))                 # the plate (0.3 mm, with its ribs)
                c = c.cut(bx(3.0, 7.0, PLATE_HY, RIB_Z1, 0.1))                      # solder feet and fillets
                c = c.cut(bx(RIB_X1, 13.2 if spring_end else 8.6, SLOT_HY, CR_Z - 1, 0.1))   # coil / bump passes through
        back = [q for q in back if not (q[4] < -15 and q[2] - q[0] < 6)]            # the + contacts: pockets above
    for (x, y) in BUTTONS:
        c = c.cut(zcyl(x, y, ACT_FLANGE / 2 + 0.4, CR_Z - 1, 1))
    return cut_boxes(c, back, 0.5, 0.4, "cradle")


def lobes(z0, z1):
    w = None
    for (x, y) in LOBES:
        c = zcyl(x, y, LOBE_R, z0, z1)
        w = c if w is None else w.union(c)
    return w


def make_rear(back, tft_bb):
    r = outline(Z_REAR_OUT, T, outer_low=True)
    r = r.cut(rrect(LEDGE, LEDGE, W - LEDGE, H - LEDGE, Z_REAR_IN, 0.01, PCB_R - LEDGE))
    r = r.cut(rrect(-CLR, -CLR, W + CLR, H + CLR, 0, T + 1, PCB_R + CLR))
    # TFT locating ring (open at the flat tail / ribbon)
    tx = (tft_bb[0] + tft_bb[2]) / 2
    ty = tft_bb[1] + A.TFT_OD / 2
    ring = zcyl(tx, ty, A.TFT_OD / 2 + 1.9, Z_REAR_IN - 0.1, -21.9).cut(
        zcyl(tx, ty, A.TFT_OD / 2 + 0.4, Z_REAR_IN - 0.2, -21.8))
    ring = ring.cut(box(tx - 18.5, ty + 18.0, tx + 18.5, H, Z_REAR_IN - 0.2, -21.8))
    r = r.union(ring)
    # cradle locating ribs from the top / bottom walls
    for x in (50.0, 70.0):
        r = r.union(box(x - 0.8, -CLR - 0.1, x + 0.8, CR_Y[0] - 0.3, Z_REAR_IN - 0.1, -5.0))
    for x in (56.0, 70.0):
        r = r.union(box(x - 0.8, CR_Y[1] + 0.3, x + 0.8, H + CLR + 0.1, Z_REAR_IN - 0.1, -5.0))
    r = r.cut(zcyl(A.AXIS[0], A.AXIS[1], WINDOW_D / 2, Z_REAR_OUT - 1, Z_REAR_IN + 1))    # eye window
    r = r.cut(zcone(A.AXIS[0], A.AXIS[1], WINDOW_D / 2 + 1.2, WINDOW_D / 2, Z_REAR_OUT - 0.01, Z_REAR_OUT + 1.2))
    for y0 in () if FIXED else LEFT_AXES:                                        # fixed cells: side walls stay closed
        r = r.cut(ring_cut(y0, "L"))
        r = r.cut(box(-0.5, y0 - 12.8, 7.3, y0 + 12.8, BLK_ZB - 0.3, 0.1))       # flange on the PCB
    if not FIXED:
        r = r.cut(ring_cut(RIGHT_AXIS, "R"))
    if MS_DIR:
        r = r.cut(cap_clear())
    if not FIXED:
        r = r.cut(box(W - 7.3, RIGHT_AXIS - 12.8, W + 0.5, RIGHT_AXIS + 12.8, BLK_ZB - 0.3, 0.1))
    for (x, y) in BUTTONS:
        r = r.cut(zcyl(x, y, ACT_HOLE / 2, Z_REAR_OUT - 1, Z_REAR_IN + 0.5))              # actuator holes
        r = r.cut(zcyl(x, y, ACT_CB_D / 2, Z_REAR_OUT - 0.01, Z_REAR_OUT + ACT_CB_DEPTH))
    for (x, y) in LOBES:
        r = r.cut(zcyl(x, y, INSERT_D / 2, -6.0, T + 1))
    r = r.cut(box(*USB_CUT))
    r = r.union(guides())
    r = tripod(r)
    r = cut_boxes(r, back, 0.4, 0.4, "rear shell")
    return r.cut(box(*USB_POCKET))


def make_front(front):
    f = outline(T, Z_FRONT_OUT, outer_low=False)
    f = f.cut(rrect(-CLR, -CLR, W + CLR, H + CLR, T - 1, Z_FRONT_IN, PCB_R + CLR))
    lip = rrect(-CLR - 0.1, -CLR - 0.1, W + CLR + 0.1, H + CLR + 0.1, T, T + 3.0, PCB_R + CLR).cut(
        rrect(LEDGE, LEDGE, W - LEDGE, H - LEDGE, T - 1, T + 4, PCB_R - LEDGE))
    f = f.union(lip)
    f = f.union(zcyl(LENS_C[0], LENS_C[1], LENS_R_IN + 2.0, Z_FRONT_IN, LENS_TOP))        # lens turret
    f = f.cut(zcyl(LENS_C[0], LENS_C[1], LENS_R_IN, Z_FRONT_IN - 1, LENS_TOP + 1))
    f = f.union(make_hood())
    f = f.union(cam_support())
    for (x, y) in PINHOLES:                                                                  # RESET / BOOT pin holes
        f = f.cut(zcyl(x, y, 0.8, Z_FRONT_IN - 1, Z_FRONT_OUT + 1))
        f = f.cut(zcone(x, y, 0.8, 1.6, Z_FRONT_OUT - 0.8, Z_FRONT_OUT + 0.01))
    for (x, y) in LOBES:
        f = f.cut(zcyl(x, y, SCREW_D / 2, T - 1, Z_FRONT_OUT + 1))
        f = f.cut(zcyl(x, y, HEAD_D / 2, T + 3.0, Z_FRONT_OUT + 1))
    f = f.cut(box(*USB_CUT))
    f = f.cut(box(*SD_CUT))
    for y0 in () if FIXED else LEFT_AXES:
        f = f.cut(ring_cut(y0, "L", z0=-1.0))
    if not FIXED:
        f = f.cut(ring_cut(RIGHT_AXIS, "R", z0=-1.0))
    if MS_DIR:
        f = f.cut(cap_clear())
    f = cut_boxes(f, front, 0.4, 0.4, "front shell")
    return f.cut(box(*USB_POCKET)).cut(box(*SD_SCOOP))


# ------------------------------------------------------------------ main --------------
def vol(a, b):
    try:
        return round(a.intersect(b).Volume(), 3)
    except Exception as e:
        return f"err {e}"


def main():
    os.makedirs(PRINT, exist_ok=True)
    os.makedirs(PARTS, exist_ok=True)
    board = A.load_board()
    sub, comp, springs, back, front = classify(board)
    print(f"board: {len(comp)} component solids kept, {len(springs)} spring-contact solids removed", flush=True)
    path, info = A.fpc_path_vertical()
    real = A.onshape_parts()
    tft = [p for p in real if p[0].startswith("TFT")][0]
    cam = [p for p in real if p[0].startswith("OV7670")][0]
    cells = make_cells2()
    left_blocks = cq.Compound.makeCompound([x[1] for x in springs if x[0] == "block"])
    print("left blocks from the board STEP:", len([x for x in springs if x[0] == "block"]),
          "| BT22 spring solids removed:", len([x for x in springs if x[0] == "bt22"]), flush=True)
    fpc = A.fpc_parts(path, A.FPC_LEN)
    caps = slugs = None
    if MS_DIR:
        left_blocks, caps, slugs = ms3181_parts()
        print("MS3181 blocks + cap stacks from", MS_DIR, flush=True)

    spr = None
    if FIXED:
        left_blocks = None
        spr = spring_parts([x[1] for x in springs if x[0] == "spring"])
        print("fixed cells: spring solids kept:", len([x for x in springs if x[0] == "spring"]), flush=True)
    block = None if FIXED else make_right_block()
    cradle = make_cradle(back)
    rear = make_rear(back, bb(tft[1]))
    frontshell = make_front(front)
    actuators, button_caps = make_actuators(back)
    topcradle = make_top_cradle(bb(tft[1]))
    hw = hardware()
    if FIXED:
        hw.pop("hw_block_screws")
        hw.pop("hw_block_washers")
    printed = (("FCL_battery_block_right", block, (0.62, 0.64, 0.68)), ("FCL_cell_cradle", cradle, (0.95, 0.75, 0.25)),
               ("FCL_case_rear", rear, (0.30, 0.50, 0.85)), ("FCL_case_front", frontshell, (0.35, 0.75, 0.55)),
               ("FCL_button_actuators", actuators, (0.85, 0.30, 0.25)), ("FCL_button_caps", button_caps, (0.20, 0.20, 0.22)),
               ("FCL_cell_cradle_top", topcradle, (0.98, 0.70, 0.20)))
    printed = tuple(q for q in printed if q[1] is not None)
    for name, w, _ in printed:
        s = w.val()
        b6 = [round(v, 2) for v in bb(s)]
        print(f"{name}: solids {len(s.Solids())}, volume {s.Volume() / 1000:.1f} cm3, bbox {b6}", flush=True)
        if FIXED and name not in ("FCL_case_rear", "FCL_case_front", "FCL_cell_cradle"):
            continue                       # the other printed parts are the same as for removable cells
        cq.exporters.export(w, os.path.join(PRINT, name + SUFFIX + ".step"))
        cq.exporters.export(w, os.path.join(PRINT, name + SUFFIX + ".stl"), tolerance=0.05, angularTolerance=0.2)

    # ---- interference checks (mm3, should all be ~0)
    solids = {n: w.val() for n, w, _ in printed}
    tb = bb(tft[1])
    tcx, tcy = (tb[0] + tb[2]) / 2, tb[1] + A.TFT_OD / 2
    tft_proxy = zcyl(tcx, tcy, A.TFT_OD / 2, tb[4], tb[5]).union(
        box(tcx - A.TFT_FLAT_W / 2, tcy, tcx + A.TFT_FLAT_W / 2, tb[3], tb[4], tb[5])).val()   # imported TFT is not a clean solid
    others = {"left_blocks": left_blocks, "PCB": cq.Compound.makeCompound(sub), "TFT": tft_proxy, "camera": cam[1],
              "cells": cq.Compound.makeCompound([c[1] for c in cells]),
              "ribbon": cq.Compound.makeCompound([p[1] for p in fpc])}
    others = {k: v for k, v in others.items() if v is not None}
    plus = None
    if spr is not None:
        others["springs"] = spr
        plus = cq.Compound.makeCompound([q for q in comp if is_plus_contact(q)])
        others["plus_contacts"] = plus
        rest = cq.Compound.makeCompound([q for q in comp if not is_plus_contact(q)])
        print(f"  + contacts: {len(plus.Solids())}", flush=True)
        print(f"  springs x cells: {vol(spr, others['cells'])}   springs x other PCB components: {vol(spr, rest)}", flush=True)
        print(f"  + contacts x cells: {vol(plus, others['cells'])}", flush=True)
    others["hw_case_screws"] = hw["hw_case_screws"].val()
    others["hw_cam_screws"] = hw["hw_cam_screws"].val()
    if "hw_block_screws" in hw:
        others["hw_block_screws"] = hw["hw_block_screws"].val()
    if caps is not None:
        others["caps"] = caps
        others["slugs"] = slugs
        for a, b in (("caps", "PCB"), ("slugs", "PCB"), ("slugs", "cells"), ("caps", "cells"), ("caps", "left_blocks")):
            print(f"  {a} x {b}: {vol(others[a], others[b])}", flush=True)
        print(f"  slugs x left_blocks: {vol(slugs, left_blocks)}", flush=True)
    names = list(solids)
    print("interference (mm3):")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            print(f"  {a} x {b}: {vol(solids[a], solids[b])}", flush=True)
        for b, shp in others.items():
            print(f"  {a} x {b}: {vol(solids[a], shp)}", flush=True)
    compc = cq.Compound.makeCompound(comp)
    for k in [k for k in ("hw_cam_screws", "hw_case_screws", "hw_block_screws") if k in hw]:
        print(f"  {k} x camera: {vol(hw[k].val(), cam[1])}  x PCB components: {vol(hw[k].val(), compc)}", flush=True)
    print(f"  FCL_cell_cradle_top x FCL_cell_cradle: {vol(topcradle.val(), cradle.val())}", flush=True)
    lim = [f for f in front if f[5] > Z_FRONT_IN and not (17 < f[0] and f[2] < 52)]
    print("front parts taller than the shell:", lim)

    # simplified parts for renders
    simple = [("left_blocks", left_blocks), ("PCB", cq.Compound.makeCompound(sub)), ("TFT", tft[1]), ("camera", cam[1]),
              ("cells", others["cells"]), ("ribbon", others["ribbon"])]
    simple = [q for q in simple if q[1] is not None]
    if spr is not None:
        simple.append(("springs", spr))
        simple.append(("plus_contacts", plus))
    simple += [(k, v.val()) for k, v in hw.items()]
    if caps is not None:
        simple += [("caps", caps), ("slugs", slugs)]
        mid = A.OX + W / 2
        for nm, comp_ in (("caps", caps), ("slugs", slugs)):
            sl = comp_.Solids()
            simple.append((nm + "_L", cq.Compound.makeCompound([x for x in sl if x.Center().x < mid])))
            simple.append((nm + "_R", cq.Compound.makeCompound([x for x in sl if x.Center().x >= mid])))
    for n, s in simple:
        cq.exporters.export(cq.Workplane(obj=s), os.path.join(PARTS, n + ".stl"), tolerance=0.08, angularTolerance=0.3)
    for n, w, _ in printed:
        cq.exporters.export(w, os.path.join(PARTS, n + ".stl"), tolerance=0.05, angularTolerance=0.2)
    print("PARTS_DONE", flush=True)

    if "--noassy" in sys.argv:
        return
    assy = cq.Assembly(name="FCL_monocular_case")
    assy.add(cq.Compound.makeCompound(sub), name="PCB_substrate", color=A.colour(0.18, 0.45, 0.22))
    assy.add(cq.Compound.makeCompound(comp), name="PCB_components", color=A.colour(0.55, 0.57, 0.60))
    if left_blocks is not None:
        assy.add(left_blocks, name="FCL_battery_blocks_left", color=A.colour(0.62, 0.64, 0.68))
    if spr is not None:
        assy.add(spr, name="spring_contacts_MY-18650-05-J", color=A.colour(0.75, 0.75, 0.78))
    if caps is not None:
        assy.add(caps, name="MS3181_cap_stacks", color=A.colour(0.35, 0.38, 0.30))
        assy.add(slugs, name="brass_slugs", color=A.colour(0.85, 0.70, 0.35))
    for n, s, c in cells + real + fpc:
        assy.add(s, name=n, color=c)
    for n, w, c in printed:
        assy.add(w.val(), name=n, color=A.colour(*c))
    out = os.path.join(A.BUILD, "FCL_case_assembly" + SUFFIX + ".step")
    assy.export(out)
    print("wrote", out, flush=True)


if __name__ == "__main__":
    main()
