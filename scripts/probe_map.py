import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
W = 85
fpga = {"C13": (43.1, 43.1), "D5": (50.3, 43.1), "D7": (48.7, 43.1), "E13": (43.9, 42.3), "J3": (51.1, 38.3),
        "J4": (50.3, 38.3), "J5": (49.5, 38.3), "K4": (50.3, 37.5), "P3": (51.1, 34.3), "R3": (51.9, 33.5)}
esp = {"IO46": (60.28, 26.95), "IO39": (76.64, 18.45), "IO40": (76.3, 16.38), "IO41": (76.3, 15.11), "IO42": (76.3, 13.84),
       "RXD0": (77.25, 12.57), "TXD0": (77.25, 11.3), "IO2": (76.55, 10.03), "IO1": (76.8, 8.35)}
nets = {"CLK_25MHz": (52.65, 40.65), "PWREN": (60.5, 62.3), "SHUTDOWN": (53.5, 62.15), "VBAT_OR": (67.65, 60.95), "WIFIEN (ESP EN)": (54.6, 14.75), "PWRBTn": (29.2, 47.5), "WAKEUPn": (40.1, 61.95), "VBUS_C": (72.3, 69.45), "VBAT1": (65.6, 39.75), "VBAT3": (73.75, 52.25), "CHG1_CHRGn": (67.05, 27.15), "CHG2_CHRGn": (71.2, 41.1), "CHG3_CHRGn": (72.2, 59.7), "PROG3": (77.55, 59.14), "SD3V3": (34.74, 5.26), "LCD_BL_K": (40.55, 71.5), "GP13": (41.25, 53.15), "FPGA_DONE": (45.6, 27.7), "FPGA_INITN": (51.6, 29.2), "FPGA_PROGRAMN": (27.05, 17.6), "FLASH_SCK": (51.85, 31.95), "FLASH_nCS": (60.35, 28.6), "FLASH_MOSI": (52.65, 30.35), "FLASH_MISO": (56.15, 28.15), "ADC_SDO": (69.83, 48.71), "ADC_DIN": (54.25, 41.6), "SD_CLK": (36.3, 3.25), "SD_CMD": (39.9, 33.5), "SD_D0": (38.5, 3.25), "I2S_BCLK": (52.0, 23.7), "I2S_WS": (49.25, 22.15), "I2S_SPK": (58.5, 22.25), "I2S_MIC": (19.7, 27.6), "AMP_SD": (21.8, 26.6), "IMU_INT1": (14.95, 17.2), "TOF_INT": (30.7, 30.65), "MAG_DRDY": (39.9, 36.7), "BARO_INT": (18.0, 14.8)}
tps = {"TP1 GND": (38.3, 31.1), "TP2 GND": (40.7, 5.7), "TP3 3V3": (33.2, 7.1), "TP4 1V1": (50.1, 50.1), "TP5 2V5": (56.2, 47.8), "TP7 5V": (62.6, 36.9)}
X = lambda x: W - x   # seen from the back
fig, axs = plt.subplots(1, 3, figsize=(19, 7.2), gridspec_kw={"width_ratios": [1.5, 1, 1]})
for ax, (x0, y0, x1, y1, title) in zip(axs, ((0, 0, 85, 79, "Whole board, seen from the BACK"),
                                             (41.5, 32.5, 53.5, 44.5, "Under the FPGA (U1), back"),
                                             (73.5, 6.5, 80, 20, "Beside the ESP32 (U9), back"))):
    ax.add_patch(Rectangle((X(85), 0), 85, 79, fill=False, lw=2))
    ax.add_patch(Rectangle((X(54.9), 28.1), 18.8, 18.8, fill=False, ls="--"))
    ax.add_patch(Rectangle((X(75.5), 0), 18.5, 25.6, fill=False, ls="--", ec="b"))
    for d, c, fs in ((fpga, "darkorange", 9), (esp, "royalblue", 9), (nets, "crimson", 9)):
        for k, (x, y) in d.items():
            ax.plot(X(x), y, "o", ms=7 if ax is not axs[0] else 4, mfc="gold", mec=c, mew=2)
            if ax is not axs[0] or d is nets:
                ax.annotate(k, (X(x), y), xytext=(6, -3), textcoords="offset points", fontsize=fs if ax is not axs[0] else 7, color=c)
    for k, (x, y) in tps.items():
        ax.plot(X(x), y, "s", ms=5 if ax is axs[0] else 8, mfc="none", mec="gray")
        ax.annotate(k, (X(x), y), xytext=(5, 4), textcoords="offset points", fontsize=7, color="gray")
    ax.set_xlim(X(x1), X(x0)) if False else ax.set_xlim(X(x1), X(x0))
    ax.set_ylim(y1, y0); ax.set_aspect("equal"); ax.set_title(title, fontsize=10); ax.grid(alpha=.2)
    ax.set_xlabel("mm from the left edge, seen from the back (= 85 - board x)")
axs[0].text(X(45.5), 30, "U1", ha="center"); axs[0].text(X(66), 22, "U9", ha="center", color="b")
axs[0].plot([], [], "o", mfc="gold", mec="darkorange", label="spare FPGA ball (dog-bone via)")
axs[0].plot([], [], "o", mfc="gold", mec="royalblue", label="spare ESP32 pin")
axs[0].plot([], [], "o", mfc="gold", mec="crimson", label="existing net")
axs[0].plot([], [], "s", mfc="none", mec="gray", label="existing TP")
axs[0].legend(loc="lower right", fontsize=8)
plt.tight_layout(); plt.savefig(r"M:\FPGA_CAM-LCD-merged\doc\probe_points.png", dpi=105)
