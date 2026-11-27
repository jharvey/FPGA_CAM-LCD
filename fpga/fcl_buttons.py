#!/usr/bin/env python3
"""Fit the camera-to-TFT design to the FCL buttons (one-shot; run from the repo root).

The design came from a ULX3S project: three active-high buttons on BTN_F1 / BTN_F2 / BTN_U. On this board those balls
have no switch; the user buttons are B1 (BTN1n, N5) and B2 (BTN2n, M5), active low with 10k pull-ups.
  * switch (raw camera <-> Sobel view)  -> B1, BTN1n, N5
  * inc_threshold                       -> B2, BTN2n, M5   (wraps to 0 after 252: there is no second threshold button)
  * dec_threshold                       stays on R1 (no switch), pulled up = idle
  * the key edge detector reacts to a press of an active-low button (falling edge of the debounced input)
  * the output that drives GP13 is labelled LCD_BL_EN: on this board GP13 is the backlight boost enable (U8),
    and the design holds it at 1 (backlight on)
The board definition's BTN_F1 / BTN_F2 / BTN_U pins get pull-ups, so unused inputs read as released.
"""
import json

ICE = "fpga/CameraToTFTSobel_FCL.ice"
PIN = "fpga/icestudio/FCL/pinout.json"
SOBEL = "215c2916a835b74d09e6348d0d037d2c0f1fc7ef"

s = open(ICE, encoding="utf-8").read()
nl = "\r\n" if "\r\n" in s else "\n"
ice = json.loads(s)
G = ice["design"]["graph"]


def port(name):
    hits = [b for b in G["blocks"] if (b.get("data") or {}).get("name") == name]
    assert len(hits) == 1, (name, len(hits))
    return hits[0]


def set_pin(name, pin_name, ball):
    b = port(name)
    assert len(b["data"]["pins"]) == 1
    b["data"]["pins"][0]["name"] = pin_name
    b["data"]["pins"][0]["value"] = ball


set_pin("switch", "btn1n", "N5")
set_pin("inc_threshold", "btn2n", "M5")
port("LCD_IM0")["data"]["name"] = "LCD_BL_EN"

dep = ice["dependencies"][SOBEL]["design"]["graph"]
code = [b for b in dep["blocks"] if b["type"] == "basic.code" and "key1_rise" in b["data"]["code"]]
assert len(code) == 1
c = code[0]["data"]["code"]
for old, new in (
        ("assign key1_rise = key1 && !key1_prev;", "assign key1_rise = !key1 && key1_prev;   // FCL: active-low buttons, act on press"),
        ("assign key2_rise = key2 && !key2_prev;", "assign key2_rise = !key2 && key2_prev;"),
        ("assign key3_rise = key3 && !key3_prev;", "assign key3_rise = !key3 && key3_prev;"),
        ("            else\n                threshold <= 8'd255;",
         "            else\n                threshold <= 8'd0;   // FCL: wrap (one threshold button)")):
    nlc = "\r\n" if "\r\n" in c else "\n"
    old, new = old.replace("\n", nlc), new.replace("\n", nlc)
    assert c.count(old) == 1, old
    c = c.replace(old, new)
code[0]["data"]["code"] = c

out = json.dumps(ice, indent=2, ensure_ascii=True).replace("\n", nl)
if s.endswith(nl):
    out += nl
open(ICE, "w", encoding="utf-8", newline="").write(out)

pins = json.load(open(PIN))
for p in pins:
    if p["value"] in ("R1", "T1", "R18"):
        p["pullmode"] = "UP"
open(PIN, "w").write(json.dumps(pins, separators=(",", ":")))
print("ok")
