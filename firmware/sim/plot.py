#!/usr/bin/env python3
"""Plot the simulator output.   python3 plot.py fcl_sim.csv  -> fcl_sim.png"""
import csv
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src = sys.argv[1] if len(sys.argv) > 1 else "fcl_sim.csv"
rows = list(csv.DictReader(open(src)))
col = lambda k: [float(r[k]) for r in rows]
t = col("t")
fig, ax = plt.subplots(5, 1, figsize=(11, 13), sharex=True)
for a, (k, lab) in zip(ax[:3], (("hd", "heading (deg)"), ("pt", "pitch (deg)"), ("rl", "roll (deg)"))):
    a.plot(t, col(k + "_true"), lw=2.5, color="#bbbbbb", label="true")
    a.plot(t, col(k + "_est"), lw=1.0, color="#1f5fbf", label="hub estimate")
    a.set_ylabel(lab)
    a.legend(loc="upper right", fontsize=8)
ax[3].plot(t, col("alt_true"), lw=2.5, color="#bbbbbb", label="true")
ax[3].plot(t, col("alt_est"), lw=1.0, color="#1f5fbf", label="barometer")
ax[3].set_ylabel("altitude (m)")
ax[3].legend(loc="upper left", fontsize=8)
ax[4].plot(t, col("cell3_v"), color="#c04020", label="cell 3 (V)")
ax[4].axhline(3.4, ls="--", color="#c04020", lw=0.8)
a2 = ax[4].twinx()
a2.plot(t, col("servo1_us"), color="#208040", lw=0.9, label="servo 1 (us)")
ax[4].set_ylabel("cell 3 (V)")
a2.set_ylabel("servo 1 (us)")
ax[4].set_xlabel("time (s)")
for a, x, txt in ((ax[0], 2, "start turning"), (ax[4], 26, "ESP32 servo cmd"), (ax[4], 30, "B0 held 2 s: off")):
    a.axvline(x, color="0.5", lw=0.6, ls=":")
    a.text(x, a.get_ylim()[1], " " + txt, fontsize=7, va="top")
fig.suptitle("FCL sensor hub - host simulation (real hub code, modelled sensors)")
fig.tight_layout()
out = src.rsplit(".", 1)[0] + ".png"
fig.savefig(out, dpi=90)
print("wrote", out)
