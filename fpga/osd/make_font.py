#!/usr/bin/env python3
"""Font ROM for the LCD overlay: ASCII 32..127 as 16 x 32 pixel glyphs, one 16-bit hex word per row
(MSB = left pixel), 96 x 32 = 3072 words -> font16x32.hex ($readmemh in fcl_osd.v, read by sim/fcl_osd.py).

Rendered from DejaVu Sans Mono Bold (free licence, shipped with matplotlib).   python fpga/osd/make_font.py
"""
import os
import matplotlib
from PIL import Image, ImageDraw, ImageFont

W, H, SIZE = 16, 32, 25
ttf = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSansMono-Bold.ttf")
font = ImageFont.truetype(ttf, SIZE)
asc, desc = font.getmetrics()
y0 = (H - (asc + desc)) // 2
out = []
for code in range(32, 128):
    img = Image.new("L", (W, H), 0)
    if code < 127:
        d = ImageDraw.Draw(img)
        adv = font.getlength(chr(code))
        d.text(((W - adv) / 2, y0), chr(code), font=font, fill=255)
    for y in range(H):
        word = 0
        for x in range(W):
            word = word << 1 | (1 if img.getpixel((x, y)) >= 110 else 0)
        out.append("%04x" % word)
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font16x32.hex")
with open(path, "w", newline="\n") as f:
    for i in range(0, len(out), H):
        f.write(" ".join(out[i:i + H]) + "\n")
print("wrote", path, len(out), "words; ascent/descent", asc, desc)
