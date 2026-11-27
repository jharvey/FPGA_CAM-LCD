#!/usr/bin/env python3
"""Read a recorded FCL stream (.log: from the unit's `log on`, or the dashboard's `!log file.log`).

    python firmware/tools/fcl_log.py trip.log                 summary: duration, ranges, events, battery use
    python firmware/tools/fcl_log.py trip.log --csv trip.csv  the telemetry as a table (one row per $T line)
    python firmware/tools/fcl_log.py trip.log --plot trip.png heading, pitch / roll, height, distance, cells over time
                                                              (needs matplotlib)
Play it back on the dashboard with:  python firmware/tools/fcl_dash.py --replay trip.log
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "esp32"))
import fcl_usb      # noqa: E402


def load(path):
    """-> (telemetry dicts, [(t_s, kind, fields)] for everything else)"""
    tele, other = [], []
    t = 0.0
    for line in open(path, encoding="utf-8", errors="replace"):
        r = fcl_usb.parse_line(line)
        if not r:
            continue
        if r[0] == "T":
            tele.append(r[1])
            t = r[1]["t_ms"] / 1000.0
        else:
            other.append((t, r[0], r[1]))
    return tele, other


def summary(tele, other):
    if not tele:
        return ["no telemetry lines in this file"]
    t0, t1 = tele[0]["t_ms"] / 1000.0, tele[-1]["t_ms"] / 1000.0
    out = ["%d telemetry lines over %.1f s (%.1f per second)" % (len(tele), t1 - t0, len(tele) / max(0.001, t1 - t0))]
    for key, unit, name in (("pitch", "deg", "pitch"), ("roll", "deg", "roll"), ("alt_m", "m", "height"),
                            ("press_hpa", "hPa", "pressure")):
        v = [t[key] for t in tele]
        out.append("%-9s %8.2f .. %8.2f %s" % (name, min(v), max(v), unit))
    d = [t["dist_mm"] / 1000.0 for t in tele if t["flags"] & 8]
    out.append("distance  %8.2f .. %8.2f m   (in range on %d of %d lines)" % (min(d), max(d), len(d), len(tele)) if d
               else "distance  never in range")
    for i in (1, 2, 3):
        have = [t for t in tele if t["soc%d" % i] != 255]            # 255: no cell, or no reading yet
        if not have:
            out.append("cell %d    no cell" % i)
        else:
            tc = [t["temp%d_c" % i] for t in have]
            out.append("cell %d    %3d %% -> %3d %%   %d -> %d mV   %.0f .. %.0f C" % (
                i, have[0]["soc%d" % i], have[-1]["soc%d" % i], have[0]["cell%d_mv" % i], have[-1]["cell%d_mv" % i], min(tc), max(tc)))
    turn = 0.0
    for a, b in zip(tele, tele[1:]):
        turn += abs((b["heading"] - a["heading"] + 180.0) % 360.0 - 180.0)
    out.append("turned    %.0f deg in all" % turn)
    ev = [(t, f[0]) for t, k, f in other if k == "E"]
    out.append("events    " + (", ".join("%s at %.1f s" % (n, t - t0) for t, n in ev[:12]) + (" ..." if len(ev) > 12 else "") if ev else "none"))
    said = [(t, f[0]) for t, k, f in other if k == "I"]
    for t, text in said[:12]:
        out.append("  %.1f s  %s" % (t - t0, text))
    return out


def write_csv(tele, path):
    with open(path, "w") as f:
        f.write(",".join(fcl_usb.T_FIELDS) + "\n")
        for t in tele:
            f.write(",".join(("%g" % t[k]) for k in fcl_usb.T_FIELDS) + "\n")


def plot(tele, other, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t0 = tele[0]["t_ms"] / 1000.0
    x = [t["t_ms"] / 1000.0 - t0 for t in tele]
    fig, ax = plt.subplots(5, 1, figsize=(10, 11), sharex=True)
    ax[0].plot(x, [t["heading"] for t in tele], ".", ms=2, color="#1f6f8b")
    ax[0].set_ylabel("heading, deg")
    ax[0].set_ylim(0, 360)
    ax[1].plot(x, [t["pitch"] for t in tele], label="pitch", color="#1f6f8b")
    ax[1].plot(x, [t["roll"] for t in tele], label="roll", color="#c05621")
    ax[1].set_ylabel("deg")
    ax[1].legend(loc="upper right", frameon=False)
    ax[2].plot(x, [t["alt_m"] for t in tele], color="#1f6f8b")
    ax[2].set_ylabel("height, m")
    ax[3].plot(x, [t["dist_mm"] / 1000.0 if t["flags"] & 8 else float("nan") for t in tele], color="#1f6f8b")
    ax[3].set_ylabel("distance, m")
    for i, c in zip((1, 2, 3), ("#1f6f8b", "#c05621", "#2f855a")):
        ax[4].plot(x, [t["cell%d_mv" % i] / 1000.0 if t["soc%d" % i] != 255 else float("nan") for t in tele], label="cell %d" % i, color=c)
    ax[4].set_ylabel("cell voltage, V")
    ax[4].legend(loc="lower left", frameon=False, ncol=3)
    ax[4].set_xlabel("time, s")
    for t, k, f in other:
        if k == "E":
            for a in ax:
                a.axvline(t - t0, color="#999999", lw=0.6)
            ax[0].text(t - t0, 362, f[0], fontsize=7, rotation=90, va="bottom", ha="center")
    for a in ax:
        a.grid(alpha=0.25)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.suptitle(os.path.basename(path).rsplit(".", 1)[0] + ": recorded stream (grey lines: events)", y=0.995, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--csv")
    ap.add_argument("--plot")
    a = ap.parse_args()
    tele, other = load(a.log)
    print("\n".join(summary(tele, other)))
    if a.csv and tele:
        write_csv(tele, a.csv)
        print("wrote", a.csv)
    if a.plot and tele:
        plot(tele, other, a.plot)
        print("wrote", a.plot)
