#!/usr/bin/env python3
"""Tests of the USB stream through the simulator: telemetry lines, commands, buttons, Wi-Fi, audio, overlay.

    python firmware/sim/test_usb.py            Python stand-in hub, and the C hub too when fcl_sim_live is built
Exit code 0 = all checks pass.
"""
import base64
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcl_sim      # noqa: E402
import fcl_usb      # noqa: E402
import fcl_osd      # noqa: E402
import fcl_hub      # noqa: E402

fail = 0


def check(ok, text):
    global fail
    print("PASS " if ok else "FAIL ", text)
    fail += not ok


def run(backend):
    sim = fcl_sim.Sim(backend)
    print("---- hub:", sim.hub.name)
    seen = {"T": [], "E": [], "B": [], "R": [], "S": [], "W": [], "A": [], "I": []}
    osd_same = dot_same = True
    n_osd = 0

    def go(seconds):
        nonlocal osd_same, dot_same, n_osd
        for _ in range(int(round(seconds / fcl_sim.STEP_S))):
            for line in sim.step():
                r = fcl_usb.parse_line(line)
                if r:
                    seen[r[0]].append(r[1])
            if fcl_hub.last and sim.state["power_hold"]:
                n_osd += 1
                osd_same &= sim.state["osd"] == fcl_osd.osd_compose(fcl_hub.last)
                dot_same &= sim.state["dot"][:2] == (fcl_hub.last["dot_x"], fcl_hub.last["dot_y"])

    go(4.0)
    t = seen["T"][-1]
    check(38 <= len(seen["T"]) <= 41, "telemetry at 10 lines per second: %d lines in 4 s" % len(seen["T"]))
    check(abs(((t["heading"] - (30 + 12 * 4.0)) + 180) % 360 - 180) < 3 and abs(t["pitch"]) < 8,
          "heading follows the scene: %.1f deg at 4 s (truth 78.0)" % t["heading"])
    check(t["soc1"] > 80 and t["soc3"] < 30 and 20 < t["temp1_c"] < 30,
          "charge and temperature: %d %% / %d %% / %d %%, %.1f C" % (t["soc1"], t["soc2"], t["soc3"], t["temp1_c"]))
    go(2.0)                                           # demo presses B1 at 5.0-5.3 s
    check(["B1", "1"] in seen["B"] and ["B1", "0"] in seen["B"] and ["B1"] in seen["E"],
          "button B1 press and release reported: %s, event %s" % (seen["B"], seen["E"]))
    sim.command("sim press B2 400")
    go(1.0)
    check(["B2", "1"] in seen["B"] and seen["T"][-1]["flags"] & 1, "sim press B2: reported, recording flag set")

    sim.command("servo 3 1700")
    sim.command("servo 9 1700")
    go(0.3)
    check(sim.state["servo"][2] == 1700 and ["1700" == x for x in seen["S"][-1]][2] and seen["R"][-1][0] == "err",
          "servo 3 -> 1700 us on the hub; servo 9 refused: %s" % seen["R"][-1][1])
    sim.command("follow on")
    sim.command("sim set pitch 20")
    go(1.5)
    check(abs(sim.state["servo"][0] - 1300) <= 6, "follow on: servo 1 at %d us for 20 deg pitch (1300)" % sim.state["servo"][0])

    sim.command("sim set pitch -90")
    sim.command("sim set roll 0")
    go(4.0)
    t = seen["T"][-1]
    check(abs(t["dot_x"]) <= 6 and abs(t["dot_y"]) <= 6 and t["flags"] & 32,
          "pointing straight down: dot at (%d, %d), inside" % (t["dot_x"], t["dot_y"]))
    sim.command("sim set pitch 0")
    go(4.0)
    t = seen["T"][-1]
    check(abs(t["dot_x"]) <= 6 and t["dot_y"] > 220 and not t["flags"] & 32,
          "level: dot on the rim at the bottom (%d, %d)" % (t["dot_x"], t["dot_y"]))

    sim.command("overlay dot batt")
    go(0.5)
    t = seen["T"][-1]
    check(t["overlay"] == 0x21 and sim.state["osd"][1].strip() == "" and "%" in sim.state["osd"][12],
          "overlay dot batt: mask 0x%02X, heading row empty, charge row '%s'" % (t["overlay"], sim.state["osd"][12].strip()))
    sim.command("overlay all")
    sim.command("sim set alt 2.0")
    go(4.0)
    a0 = seen["T"][-1]["alt_m"]
    sim.command("zero")
    go(2.0)
    check(abs(a0 - 2.0) < 0.3 and abs(seen["T"][-1]["alt_m"]) < 0.2, "zero: height %.2f m -> %.2f m" % (a0, seen["T"][-1]["alt_m"]))

    sim.command("stream 2")
    n0 = len(seen["T"])
    go(3.0)
    n2 = len(seen["T"]) - n0
    sim.command("stream off")
    go(0.2)
    n0 = len(seen["T"])
    go(1.0)
    check(5 <= n2 <= 7 and len(seen["T"]) == n0, "stream 2: %d lines in 3 s; stream off: none" % n2)
    sim.command("stream 10")

    sim.command("wifi HomeNet correct horse battery")
    go(0.2)
    w0 = seen["W"][-1]
    go(6.0)
    w1 = seen["W"][-1]
    check(w0[0] == "connecting" and w1[0] == "connected" and w1[1] == "HomeNet" and w1[2].count(".") == 3,
          "wifi <ssid> <password>: %s -> %s %s %s" % (w0[0], w1[0], w1[1], w1[2]))
    sim.command("wifi scan")
    go(0.1)
    check(any("HomeNet" in i[0] for i in seen["I"]), "wifi scan lists networks")

    sim.command("mic on 16000")
    go(1.0)
    pcm = b"".join(base64.b64decode(a[2]) for a in seen["A"])
    v = struct.unpack("<%dh" % (len(pcm) // 2), pcm)
    seqs = [int(a[0]) for a in seen["A"]]
    check(len(v) == 16000 and max(v) > 2000 and seqs == list(range(seqs[0], seqs[0] + len(seqs))),
          "mic on: %d samples in 1 s, peak %d, sequence unbroken" % (len(v), max(v)))
    sim.command("mic off")
    tone = struct.pack("<320h", *[int(8000 * ((i % 32) / 16.0 - 1)) for i in range(320)])
    for _ in range(5):
        sim.command("spk 16000 " + base64.b64encode(tone).decode())
    sim.command("tone 880 200")
    go(0.2)
    check(sim.plat.spk_bytes == 5 * 640 and sim.plat.spk_level >= 7000 and sim.plat.tone_log == [(880, 200)],
          "spk: %d bytes reached the speaker, level %d; tone 880 Hz 200 ms" % (sim.plat.spk_bytes, sim.plat.spk_level))

    sim.command("bogus")
    sim.command("help")
    go(0.1)
    check(any(r[0] == "err" and "unknown" in r[1] for r in seen["R"]) and sum("servo" in i[0] for i in seen["I"]) >= 1,
          "unknown command refused; help lists the commands")
    check(fcl_hub.crc_errors == 0 and n_osd > 300, "link: %d frames, %d CRC errors" % (fcl_hub.frames, fcl_hub.crc_errors))
    check(osd_same and dot_same, "overlay text and dot from the hub equal the Python layout (fcl_osd.py) on %d frames" % n_osd)

    sim.command("sim press PWR 2500")
    go(3.0)
    check(["PWR_OFF"] in seen["E"] and sim.state["power_hold"] == 0, "holding the power button 2 s: PWR_OFF event, power released")
    sim.close()


run("python")
if fcl_sim.find_live():
    run("c")
else:
    print("---- C hub not built here (make -C firmware/sim all): only the Python stand-in was tested")
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
