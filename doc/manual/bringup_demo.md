# Bring-up stage 9, board 0 (a sample)

A sample of the report `firmware/tools/fcl_bringup.py` writes, made with `--sim --demo`: the simulator and a
simulated person, so every value here is simulated. A real board's report looks the same.

2026-11-28 02:05, simulator, FCL USB protocol 1. Written by `firmware/tools/fcl_bringup.py`.

| Check | Result | Measured | Expected |
|---|---|---|---|
| link: answers | pass | FCL USB protocol 1 | FCL USB protocol 1 |
| link: telemetry | pass | 30 lines in 3 s | about 30 (10 per second) |
| link: sensors | pass | 0x1F | 0x1F: all five |
| readings: pressure | pass | 1013.2 hPa | 870-1085 hPa (sea level to about 1300 m) |
| readings: cell 1 temperature | pass | 24.0 C | near the room's, 5-45 C |
| readings: cell 2 temperature | pass | 24.0 C | near the room's, 5-45 C |
| readings: cell 3 temperature | pass | 24.0 C | near the room's, 5-45 C |
| readings: cell 1 | pass | unit 4.044 V, meter 4.044 V (+0.0 %) | within 2 % (the calibration's `cells` step removes the rest) |
| readings: cell 2 | pass | unit 3.974 V, meter 3.974 V (+0.0 %) | within 2 % (the calibration's `cells` step removes the rest) |
| readings: cell 3 | pass | unit 3.670 V, meter 3.668 V (+0.0 %) | within 2 % (the calibration's `cells` step removes the rest) |
| attitude: on a table | pass | pitch -0.0, roll -0.0 | both within 10 degrees (before calibration) |
| attitude: lens down | pass | pitch -88.0 | near -90 (+90: a sign is reversed) |
| distance: hand at 30 cm | pass | 300 mm | 150-450 mm |
| distance: nothing in reach | pass | nothing seen | nothing seen (the ranger reaches about 4 m) |
| buttons: B1 | pass | reported | a $B line |
| buttons: B2 | pass | reported | a $B line |
| buttons: PWR | pass | reported | a $B line |
| screen: text | pass |  | picture and text |
| screen: graphics | pass |  | all three |
| screen: edge view | pass |  | white edges on black |
| pages: Level | pass | row 4: 'LEVEL' | 'LEVEL' |
| pages: back to the Overview | pass | row 4 given back |  |
| servo: 1 at 1500 us | pass |  | the servo holds its middle |
| audio: tone | pass |  | a short 880 Hz tone |
| log: written | pass | log off 35 lines | a file of some kilobytes after 3 s |
| wifi | skipped | state: off | skipped: set it up with `wifi <name> <password>` and run this check again |

26 checks: 25 passed, 0 failed, 1 skipped.
