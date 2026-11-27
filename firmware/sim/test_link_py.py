#!/usr/bin/env python3
"""Decode the hub's link bytes (from the C simulator) with the ESP32's MicroPython module fcl_hub.py.

    ./fcl_sim fcl_sim.csv link.bin && python3 test_link_py.py link.bin
"""
import sys
sys.path.insert(0, "../esp32")
import fcl_hub

data = open(sys.argv[1] if len(sys.argv) > 1 else "link.bin", "rb").read()
for i in range(0, len(data), 37):              # odd chunk size: frames split across reads, as on the UART
    fcl_hub.handle(data[i:i + 37])
t = fcl_hub.last
checks = [
    (fcl_hub.frames == 600, "telemetry frames decoded: %d" % fcl_hub.frames),
    (fcl_hub.crc_errors == 0, "CRC errors: %d" % fcl_hub.crc_errors),
    (t["mode"] == 2 and t["flags"] & fcl_hub.TF_RECORDING, "last frame: mode %d, recording %s" % (t["mode"], bool(t["flags"] & 1))),
    (abs(t["alt_m"]) < 0.15, "last height %.2f m (re-zeroed at 20 s by command)" % t["alt_m"]),
    (t["soc1"] in range(70, 78) and t["soc3"] <= 2 and t["overlay"] == 0x2F and t["sensors"] == 0x1F,
     "charge %d %% / %d %% / %d %%, overlay 0x%02X, sensors 0x%02X" % (t["soc1"], t["soc2"], t["soc3"], t["overlay"], t["sensors"])),
    (all(e in fcl_hub.events for e in ("B1", "B2", "CELL_LOW", "PWR_OFF")), "events: %s" % ", ".join(fcl_hub.events)),
]
fail = 0
for ok, txt in checks:
    print("PASS " if ok else "FAIL ", txt)
    fail += not ok
print("ALL CHECKS PASSED" if not fail else "SOME CHECKS FAILED")
sys.exit(1 if fail else 0)
