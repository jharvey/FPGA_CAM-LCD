"""BT12 / BT32 (battery block footprints) back into the BOM as machined parts; H1 (removed hole) out of the BOM."""
import re
VAL = {"BT12": "Battery block MS3181 A", "BT32": "Battery block MS3181 B"}
SRC = {"BT12": "case/battery_blocks/ms3181/FCL_BatteryBlock_MS3181_A_boardframe_for_machining.step",
       "BT32": "case/battery_blocks/ms3181/FCL_BatteryBlock_MS3181_B_boardframe_for_machining.step"}


def prop(name, val, at):
    return (f'\t\t(property "{name}" "{val}"\n\t\t\t(at {at} 0)\n\t\t\t(hide yes)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')


def blocks(text):
    """yield (start, end) of top-level (symbol ...) blocks in a schematic"""
    for m in re.finditer(r"\n\t\(symbol\n", text):
        s = m.start() + 1
        depth, i = 0, s
        while True:
            c = text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    yield s, i + 1
                    break
            i += 1


p = "power.kicad_sch"
t = open(p).read()
done = 0
for s, e in sorted(blocks(t), reverse=True):
    b = t[s:e]
    m = re.search(r'\(property "Reference" "(BT12|BT32)"', b)
    if not m:
        continue
    ref = m.group(1)
    at = re.search(r"\(symbol\n\t\t\(lib_id [^\n]+\n\t\t\(at ([\d.\-]+ [\d.\-]+)", b).group(1)
    b = b.replace("(in_bom no)", "(in_bom yes)", 1)
    b = b.replace('(property "Value" "BLOCK_MOUNT"', f'(property "Value" "{VAL[ref]}"', 1)
    extra = "".join(prop(k, v, at) for k, v in (("Category", "Machined"), ("Qty", "1"),
                                                  ("Material", "6061-T6, electroless nickel"), ("Source_File", SRC[ref])))
    i = b.index("\t\t(pin ")
    b = b[:i] + extra + b[i:]
    t = t[:s] + b + t[e:]
    done += 1
assert done == 2, done
open(p, "w").write(t)

r = open("FCL.kicad_sch").read()
i = r.index('(property "Reference" "H1"')
j = r.rindex("(in_bom yes)", 0, i)
assert i - j < 300
r = r[:j] + "(in_bom no)" + r[j + len("(in_bom yes)"):]
open("FCL.kicad_sch", "w").write(r)

pcb = open("FCL.kicad_pcb").read()
n = 0
for ref, val in VAL.items():
    k = pcb.index(f'(property "Reference" "{ref}"')
    s = pcb.rindex("\n\t(footprint ", 0, k)
    e = pcb.index("\n\t(footprint ", k)
    blk = pcb[s:e]
    blk2 = blk.replace("(attr through_hole exclude_from_pos_files exclude_from_bom)", "(attr through_hole exclude_from_pos_files)", 1)
    blk2 = blk2.replace('(property "Value" "BLOCK_MOUNT"', f'(property "Value" "{val}"', 1)
    assert blk2 != blk
    pcb = pcb[:s] + blk2 + pcb[e:]
    n += 1
open("FCL.kicad_pcb", "w").write(pcb)
for v in ("A", "B"):
    f = f"footprints/fcl_local.pretty/FCL_BatteryBlock_Mount_M2.5_Pin2_{v}.kicad_mod"
    x = open(f).read().replace("(attr through_hole exclude_from_pos_files exclude_from_bom)", "(attr through_hole exclude_from_pos_files)")
    open(f, "w").write(x)
print("BT12/BT32 in BOM, H1 out of BOM, pcb footprints", n)
