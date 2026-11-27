#!/usr/bin/env python3
"""The Survey page's points as a table, a CSV file and a plan drawing.

    python firmware/tools/fcl_survey.py trip.log                    points recorded in a log ($P lines)
    python firmware/tools/fcl_survey.py --from COM7                 ask the unit (also: sim, tcp:host:port)
    ... --csv points.csv --svg plan.svg                             write files as well

On the unit: page SURVEY, aim the reticle at a corner, press B2; go round the room in order.  x is east, y north,
z up, in metres from where you stood.  The plan is the shape the points make in the order taken, seen from above.
The ranger reaches about 4 m, and the compass is good to a few degrees: expect a few centimetres per metre.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
KEYS = ("n", "heading", "pitch", "dist", "x", "y", "z")


def parse(lines):
    """$P lines -> points in the order taken; a repeated number (points listed twice) counts once; "points clear" is
    not in a log, so a number that starts again at 1 begins a new survey and only the last one is returned"""
    pts = []
    for line in lines:
        line = line.strip()
        if not line.startswith("$P,"):
            continue
        v = line[3:].split(",")
        if len(v) != 7:
            continue
        p = dict(zip(KEYS, [int(v[0])] + [float(x) for x in v[1:]]))
        if p["n"] == 1 and pts and pts[0] != p:
            pts = []
        if not any(q["n"] == p["n"] for q in pts):
            pts.append(p)
    return pts


def sides(pts):
    """length on the ground of each side: point i to point i + 1, the last one back to the first"""
    n = len(pts)
    return [math.hypot(pts[(i + 1) % n]["x"] - pts[i]["x"], pts[(i + 1) % n]["y"] - pts[i]["y"]) for i in range(n if n > 2 else n - 1)]


def area(pts):
    return abs(sum(a["x"] * b["y"] - b["x"] * a["y"] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2.0 if len(pts) > 2 else 0.0


def table(pts):
    out = ["  n  heading  pitch   dist      x east  y north    z up   side to next", "     deg      deg     m         m       m          m      m"]
    sd = sides(pts) if len(pts) > 1 else []
    for i, p in enumerate(pts):
        out.append("%3d  %6.1f  %6.1f  %6.3f   %7.3f  %7.3f  %7.3f   %s" % (
            p["n"], p["heading"], p["pitch"], p["dist"], p["x"], p["y"], p["z"], "%.3f" % sd[i] if i < len(sd) else ""))
    if len(pts) > 2:
        zs = [p["z"] for p in pts]
        out.append("area on the ground %.2f m2, around %.2f m, heights %.2f to %.2f m from the unit" % (area(pts), sum(sd), min(zs), max(zs)))
    return "\n".join(out)


def csv_text(pts):
    return "\n".join([",".join(KEYS)] + [",".join(str(p[k]) for k in KEYS) for p in pts]) + "\n"


def svg(pts, size=640):
    """the plan from above, north up: the shape, its side lengths, the point numbers, where the unit stood"""
    xs, ys = [p["x"] for p in pts] + [0.0], [p["y"] for p in pts] + [0.0]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 0.5)
    m = 70
    k = (size - 2 * m) / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def P(x, y):
        return size / 2 + (x - cx) * k, size / 2 - (y - cy) * k
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="system-ui,sans-serif" font-size="14">' % (size, size),
         '<rect width="100%" height="100%" fill="#fff"/>']
    if len(pts) > 2:
        o.append('<polygon points="%s" fill="#e6f2ec" stroke="#0a7d5a" stroke-width="2.5" stroke-linejoin="round"/>' %
                 " ".join("%.1f,%.1f" % P(p["x"], p["y"]) for p in pts))
    elif len(pts) == 2:
        (x1, y1), (x2, y2) = P(pts[0]["x"], pts[0]["y"]), P(pts[1]["x"], pts[1]["y"])
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#0a7d5a" stroke-width="2.5"/>' % (x1, y1, x2, y2))
    sd = sides(pts) if len(pts) > 1 else []
    n = len(pts)
    for i, length in enumerate(sd):
        a, b = pts[i], pts[(i + 1) % n]
        mx, my = P((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2)
        ox, oy = mx - size / 2, my - size / 2                    # push the label away from the middle of the drawing
        d = math.hypot(ox, oy) or 1.0
        o.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#1c2321">%.2f m</text>' % (mx + 22 * ox / d, my + 22 * oy / d + 5, length))
    ux, uy = P(0, 0)
    o.append('<circle cx="%.1f" cy="%.1f" r="5" fill="none" stroke="#66706c" stroke-width="2"/>'
             '<text x="%.1f" y="%.1f" fill="#66706c">unit</text>' % (ux, uy, ux + 9, uy + 5))
    for p in pts:
        x, y = P(p["x"], p["y"])
        o.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="#0a7d5a"/><text x="%.1f" y="%.1f" font-weight="700" fill="#0a7d5a">%d</text>'
                 % (x, y, x + 8, y - 8, p["n"]))
    o.append('<path d="M34 64 L34 28 M27 38 L34 26 L41 38" fill="none" stroke="#1c2321" stroke-width="2"/><text x="29" y="20">N</text>')
    bar = 1.0 if span > 2 else 0.5 if span > 1 else 0.1
    o.append('<line x1="%d" y1="%d" x2="%.1f" y2="%d" stroke="#1c2321" stroke-width="3"/><text x="%d" y="%d">%g m</text>'
             % (m, size - 28, m + bar * k, size - 28, m, size - 36, bar))
    if len(pts) > 2:
        o.append('<text x="%d" y="%d" text-anchor="end">area %.2f m2, around %.2f m</text>' % (size - 20, size - 24, area(pts), sum(sd)))
    o.append("</svg>")
    return "\n".join(o) + "\n"


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("log", nargs="?", help="a recorded stream with $P lines")
    ap.add_argument("--from", dest="src", help="ask a unit: a serial port, sim, or tcp:host:port")
    ap.add_argument("--csv")
    ap.add_argument("--svg")
    a = ap.parse_args()
    if a.src:
        import fcl
        with fcl.connect(a.src) as u:
            u.wait(1.0)
            pts = u.points()
    elif a.log:
        pts = parse(open(a.log, encoding="utf-8", errors="replace"))
    else:
        ap.error("give a log file or --from")
    if not pts:
        print("no points: on the unit, page SURVEY, aim and press B2")
        return 1
    print(table(pts))
    if a.csv:
        open(a.csv, "w", newline="\n").write(csv_text(pts))
        print("wrote", a.csv)
    if a.svg:
        open(a.svg, "w", newline="\n", encoding="utf-8").write(svg(pts))
        print("wrote", a.svg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
