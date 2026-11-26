"""Search for a ribbon path that wraps cell 3 concentrically (centre = cell axis) with exact length."""
import math, sys
sys.path.insert(0, '.')
import build_assembly as b
CY, CZ, RC = 56.5, b.CELL_AXIS_Z, b.CELL_D / 2
EY, EZ = b.tft_lcm_bottom_y(), b.FPC_Z0
SLOT = b.J7_SLOT_Z
def plan(Rw, beta):
    dy = EY - CY
    r1 = (Rw**2 - (dy**2 + (EZ - CZ)**2)) / (2*Rw - 2*(CZ - EZ))   # internal tangency
    if r1 <= 0: return None
    uy, uz = dy, (EZ + r1) - CZ
    n = math.hypot(uy, uz); uy, uz = uy/n, uz/n
    phT = math.degrees(math.atan2(uz, uy))
    a1 = (phT + 90) % 360
    phP = phT + beta
    s = math.sin(math.radians(phP))
    if s >= 1: return None
    r3 = ((SLOT - CZ) - Rw*s) / (1 - s)
    g = 90 - phP
    if r3 <= 0 or g < 0: return None
    yfin = CY + (Rw - r3)*math.cos(math.radians(phP))
    arcs = math.radians(a1)*r1 + math.radians(beta)*Rw + math.radians(g)*r3
    return dict(Rw=Rw, beta=beta, r1=r1, a1=a1, r3=r3, g=g, yfin=yfin, arcs=arcs)
best=None
for i in range(0, 700):
    Rw = 15.65 + i*0.01
    for j in range(0, 900):
        p = plan(Rw, j*0.1)
        if not p: continue
        straight = b.FPC_LEN - p['arcs']
        if straight < b.J7_INSERT + 0.3: continue
        p['straight'] = straight
        p['opening'] = p['yfin'] - (straight - b.J7_INSERT)
        score = min(p['r1'], p['r3'])
        if best is None or score > best[0]: best = (score, p)
print({k: round(v, 2) for k, v in best[1].items()})
