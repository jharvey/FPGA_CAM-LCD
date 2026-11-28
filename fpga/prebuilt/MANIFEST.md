# Stored build outputs

Written by `python fpga/make_prebuilt.py` on 2026-11-28. Check your own build against these with `python fpga/make_prebuilt.py --check`.

Built from commit `d7ba9e2deb695feff936f8d042998960d0ce1333`.

| Design | Bitstream | What it is |
|---|---|---|
| full | `full/fcl_full.bit` | camera to TFT with the LCD overlay and the sensor bridge (`fpga/full/fcl_top.v`): the bitstream the unit runs. Timing and size: `full/build_summary.txt`. |
| full87 | `full87/fcl_full_87.bit` | the same with the memory clock at 87.5 MHz instead of 100 (`build_full.py --mem-mhz 87.5`): the fallback if the first board shows wrong pixels. |
| bridge | `bridge/fcl_bridge.bit` | the sensor bridge alone (`fpga/bridge/fcl_bridge_top.v`): sensors, ADC, buttons, servos from the ESP32. No camera or LCD. For first bring-up. |
| camera | `camera/main.bit` | camera to TFT with the Sobel view alone (`fpga/CameraToTFTSobel_FCL.ice`): no bridge, no overlay. |

None has been loaded into a real board. nextpnr runs with a fixed seed, so the same tool versions should give the same files.

## Timing

From nextpnr, after routing. A FAIL is the tool's estimate for the slowest path, not a measurement.

| Design | Clock | Result |
|---|---|---|
| full | `$glbnet$cam.m.w25` | 111.00 MHz possible, PASS at 100.00 MHz (SDRAM clock of the camera design) |
| full | `$glbnet$cmos_xclk$TRELLIS_IO_OUT` | 56.86 MHz possible, PASS at 25.00 MHz (25 MHz board clock: bridge, overlay text memory, camera set-up) |
| full | `$glbnet$pix_clk_out$TRELLIS_IO_OUT` | 69.81 MHz possible, PASS at 17.86 MHz (LCD pixel clock, 25 MHz x 5 / 7) |
| full87 | `$glbnet$cam.m.w25` | 118.71 MHz possible, PASS at 87.50 MHz (SDRAM clock of the camera design) |
| full87 | `$glbnet$cmos_xclk$TRELLIS_IO_OUT` | 58.31 MHz possible, PASS at 25.00 MHz (25 MHz board clock: bridge, overlay text memory, camera set-up) |
| full87 | `$glbnet$pix_clk_out$TRELLIS_IO_OUT` | 69.32 MHz possible, PASS at 17.86 MHz (LCD pixel clock, 25 MHz x 5 / 7) |
| camera | `$glbnet$v40f83b$TRELLIS_IO_IN` | 58.22 MHz possible, PASS at 25.00 MHz |
| camera | `$glbnet$v79e9a8$TRELLIS_IO_OUT` | 82.19 MHz possible, PASS at 17.86 MHz |
| camera | `$glbnet$w25` | 101.41 MHz possible, PASS at 100.00 MHz |

All clocks pass by this estimate; the memory clock (100 MHz) has the smallest margin. Builds before 2026-11-27 did not tell nextpnr the clock frequencies, so it checked every clock against 12 MHz; with the frequencies given, the camera design's memory clock failed at 142.9 MHz, and the project was changed (`fpga/IO_REMAP.md`, section Clocks).

## Whole-design simulation

`python fpga/full/test_full.py` takes about an hour and is run by hand, not by this script. Its last stored output is `test_full.txt`: first line `python fpga/full/test_full.py, run 2026-11-27 on the FPGA sources of commit 606e8d97 (the stored bitstreams were built from 2fa52355; no FPGA source changed in between)`, last line `ALL CHECKS PASSED`. Check that the commit named there is the one these bitstreams were built from, or that no FPGA source changed in between.

## Tools

| Tool | Version |
|---|---|
| yosys | Yosys 0.33+6 (git sha1 31ee566ec, x86_64-w64-mingw32-g++ 9.2.1 -Os) |
| nextpnr-ecp5 | nextpnr-ecp5" -- Next Generation Place and Route (Version nextpnr-0.6-118-g0eb9a9ad) |
| ecppack | Project Trellis ecppack Version 1.4-64-g36c615d |
| iverilog | Icarus Verilog version 13.0 (devel) (s20221226-321-gd22bb3d25) |
| python | 3.11.7 |

## Files

`intermediates.zip` holds the Yosys netlist (.json), the nextpnr result (.config) and the Yosys log; their checksums below are of the files inside the zip.

| File | Bytes | SHA-256 |
|---|---|---|
| `full87/fcl_full_87.bit` | 440721 | `a72060f9e645c48687ef581e041fe712e273a61f211b57c5f25def928c6b2064` |
| `full87/nextpnr.log` | 78878 | `d8c20506fb5bc4905d8f4df38dff26385c2eec2aec45e4abfd484a341b2310ee` |
| `full87/build_summary.txt` | 599 | `19bd6d15699d80b19d80b7f5b39ad6083d33f33c3eb5b9cd342bbeb8eb42a476` |
| `full87/fcl_full.json` | 13300905 | `69ac250915ed97dc420fc7548aef75bead43e006f575037dec0f928f536e495b` |
| `full87/fcl_full.config` | 3467612 | `67b54b1e590bc18bb8cd845beba256066dcaa20e19cac1a7af60c4649d0c8719` |
| `full/fcl_full.bit` | 439532 | `5b8c2650ea76b98be804526e509f17eead9db72a76b8f069c80b259200f5499c` |
| `full/fcl_top.lpf` | 11802 | `10992c4cc77cf57c9c054e6190b81e532e92ba2bd0e683c41a5422dfc3602094` |
| `full/main.v` | 125030 | `2463a1a933aa4f55d4225ba18411eb135e655ad6d678b360299a45f2ee98dfd3` |
| `full/fcl_cam.v` | 3080 | `4851a4d02128caad0086373edf6325697fc74d635439b5090018696dea04a8fe` |
| `full/nextpnr.log` | 73914 | `e6216de401d52385c123f4d44c9b20857d927d673e9dd2426dfbabe804d06f9e` |
| `full/build_summary.txt` | 598 | `ab2a733686ad205849dee7a41b96c3b03aba8a703c26810875f87e47d073e1d0` |
| `full/fcl_full.json` | 13158071 | `45947c643ed92fd95a766b0a4c5223f76a18d2491ae041ed706f3ff38fc2657d` |
| `full/fcl_full.config` | 3443254 | `37d85a6937e8d9be21a4b7f411c7bfff2fc9a4fdef6d34550ec744097d585145` |
| `full/yosys.log` | 1477995 | `dfd3305992d3fbde59f0ebf6084532caab8c017c5fbddd515ba8ce41ad43bd3f` |
| `bridge/fcl_bridge.bit` | 324119 | `0719793059990eb3f01721f05227f3e3d01819f1ec7d224d7353351a64b65d01` |
| `bridge/fcl_bridge_top.lpf` | 2745 | `583b6d25d4d0bb5cfabe8622aab4d0f0aaa113bb0e6557727431a5b55d83af64` |
| `bridge/nextpnr.log` | 25887 | `6283f2c3c13857160972673798ad43a6d48534a18a9ba6bf33231fd8e7f9cc31` |
| `bridge/fcl_bridge.json` | 5066730 | `61388b1775d2a0f1048c08f501ec9d359f68bd9e80b13b7c2761a09621d46547` |
| `bridge/fcl_bridge.config` | 1225696 | `1cdede4b11b904a340572a2cb41c21a7937c7c0244f30bac4d3967d99258b7bb` |
| `bridge/yosys.log` | 683531 | `1ffd0c6ebd535ec19fddd128d5db016d99763646302b0fb981cd24691dfe4fae` |
| `camera/main.bit` | 367922 | `670c02538b94f276755e1250a462e43830f50f0109c07a5dfe5c123ec3d4a7f7` |
| `camera/main.lpf` | 9806 | `5f13dfae7fc105284d2d3e25cb5d9586c5827c8dea76dd732956789483e166da` |
| `camera/main.v` | 125030 | `2463a1a933aa4f55d4225ba18411eb135e655ad6d678b360299a45f2ee98dfd3` |
| `camera/nextpnr.log` | 61839 | `05ab6bd6e6763baf09452ac10497626583402e5ea8694e03f8181b6445ac89af` |
| `camera/build_summary.txt` | 406 | `41c7485f4b333acae072125e2cd7549d95d8f0b1ce663d21a1370ffcfebb9935` |
| `camera/main.json` | 6235205 | `fde39e91d73e1752b79b34d00db89ca7a1146c849a8948616235596042ad3b40` |
| `camera/main.config` | 1628540 | `00b615d3b64ae1e71f15e03f225d78997f8ad718df74482a6272c3de8452be80` |
| `camera/yosys.log` | 530813 | `c8ebbfcf8b086e885c46eeca5e56bee29271209d8630481e117a54e7fbd726b4` |

## Tests at build time

Full output in `test_results.txt`.

| Test | Exit code | Last line |
|---|---|---|
| `firmware/sim/test_usb.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_filter.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_magcal.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_app.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_web.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_calibrate.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_tools.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_lessons.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_mpy.py` | 0 | SKIPPED: no micropython program (set MICROPYTHON=/path/to/micropython); nothing was tested |
| `fpga/bridge/test_bridge.py` | 0 | ALL CHECKS PASSED |
| `fpga/osd/test_osd.py` | 0 | ALL FRAMES IDENTICAL |
