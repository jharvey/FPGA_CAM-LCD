# Stored build outputs

Written by `python fpga/make_prebuilt.py` on 2026-11-27. Check your own build against these with `python fpga/make_prebuilt.py --check`.

Built from commit `2fa5235527c29d387670f3fe8069dee0e3b01312`.

| Design | Bitstream | What it is |
|---|---|---|
| full | `full/fcl_full.bit` | camera to TFT with the LCD overlay and the sensor bridge (`fpga/full/fcl_top.v`): the bitstream the unit runs. Timing and size: `full/build_summary.txt`. |
| bridge | `bridge/fcl_bridge.bit` | the sensor bridge alone (`fpga/bridge/fcl_bridge_top.v`): sensors, ADC, buttons, servos from the ESP32. No camera or LCD. For first bring-up. |
| camera | `camera/main.bit` | camera to TFT with the Sobel view alone (`fpga/CameraToTFTSobel_FCL.ice`): no bridge, no overlay. |

None has been loaded into a real board. nextpnr runs with a fixed seed, so the same tool versions should give the same files.

## Timing

From nextpnr, after routing. A FAIL is the tool's estimate for the slowest path, not a measurement.

| Design | Clock | Result |
|---|---|---|
| full | `$glbnet$cam.m.w25` | 103.44 MHz possible, PASS at 100.00 MHz (SDRAM clock of the camera design) |
| full | `$glbnet$cmos_xclk$TRELLIS_IO_OUT` | 57.27 MHz possible, PASS at 25.00 MHz (25 MHz board clock: bridge, overlay text memory, camera set-up) |
| full | `$glbnet$pix_clk_out$TRELLIS_IO_OUT` | 73.41 MHz possible, PASS at 17.86 MHz (LCD pixel clock, 25 MHz x 5 / 7) |
| camera | `$glbnet$v40f83b$TRELLIS_IO_IN` | 58.16 MHz possible, PASS at 25.00 MHz |
| camera | `$glbnet$v79e9a8$TRELLIS_IO_OUT` | 77.10 MHz possible, PASS at 17.86 MHz |
| camera | `$glbnet$w25` | 97.13 MHz possible, FAIL at 100.00 MHz |

**A clock does not meet timing in: camera.** Builds before 2026-11-27 did not tell nextpnr the clock frequencies, so it checked every clock against 12 MHz; with the frequencies given, the camera design's memory clock failed at 142.9 MHz, and the project was changed (`fpga/IO_REMAP.md`, section Clocks).

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
| `full/fcl_full.bit` | 443582 | `ff0b27bcb73d6781988eaa03fd7b46f60d14c7db76dc09f13bd4a5351c30d118` |
| `full/fcl_top.lpf` | 11802 | `10992c4cc77cf57c9c054e6190b81e532e92ba2bd0e683c41a5422dfc3602094` |
| `full/main.v` | 124081 | `0d9911166a8bbe6d9728416d01aac0af42b27b381e841a735c3908f1172e53e3` |
| `full/fcl_cam.v` | 3080 | `4851a4d02128caad0086373edf6325697fc74d635439b5090018696dea04a8fe` |
| `full/nextpnr.log` | 77501 | `f8b557f15038d994868b9b4092af58e563d9857a99722144f5516072345def06` |
| `full/build_summary.txt` | 599 | `bf09daf8cf110d9cdb2408ef8594c22c68119da12e0578db5d130f0bd5b8a00f` |
| `full/fcl_full.json` | 13718618 | `f966f2db97a4580992bb7fbbae73afc44e257b336d5dfa85e108984769de47c7` |
| `full/fcl_full.config` | 3523359 | `6856bf833e50c595566385e081cc255036a7718c7f8df7fb98cbfe57c418b5e4` |
| `full/yosys.log` | 1507023 | `8288d8135d8ef41b4600b271e1c753ecbd03996afa2badc34704039bb5f60daf` |
| `bridge/fcl_bridge.bit` | 324119 | `0719793059990eb3f01721f05227f3e3d01819f1ec7d224d7353351a64b65d01` |
| `bridge/fcl_bridge_top.lpf` | 2745 | `583b6d25d4d0bb5cfabe8622aab4d0f0aaa113bb0e6557727431a5b55d83af64` |
| `bridge/nextpnr.log` | 25887 | `02a036bd66f1798f2843c59e5cb709a2e4e23346abb6b9b01b63fe2749cb8667` |
| `bridge/fcl_bridge.json` | 5066730 | `61388b1775d2a0f1048c08f501ec9d359f68bd9e80b13b7c2761a09621d46547` |
| `bridge/fcl_bridge.config` | 1225696 | `1cdede4b11b904a340572a2cb41c21a7937c7c0244f30bac4d3967d99258b7bb` |
| `bridge/yosys.log` | 683531 | `ed049942c267a4ab7627fce5cae3a843e6196273f76a55c800e2af1ab0d20918` |
| `camera/main.bit` | 367164 | `43274a8a2ad52fa3a943639827d9343fa41a3665f298a024b457b472e632f5c2` |
| `camera/main.lpf` | 9806 | `5f13dfae7fc105284d2d3e25cb5d9586c5827c8dea76dd732956789483e166da` |
| `camera/main.v` | 124081 | `0d9911166a8bbe6d9728416d01aac0af42b27b381e841a735c3908f1172e53e3` |
| `camera/nextpnr.log` | 62453 | `4b5cc1c23be899903c987de101e78c1c789902dce30afd8b90d1e9d3bf265da0` |
| `camera/build_summary.txt` | 406 | `0cef4229a0c4d6ffcf157ed2b729b4eb0385d35a3e6eaf606c9fb8b6a8a23035` |
| `camera/main.json` | 6174680 | `fa634bc99b5f6da9b47673042adfcb51d3a5f5b81128013414f6b16a814451b1` |
| `camera/main.config` | 1615191 | `e37764d4d5258fe986ae58896c6cd094f650add7c99733383494ba6a4013cea1` |
| `camera/yosys.log` | 530608 | `069ae0dd398c9a986c388b0153a1b959e357293b10ebe42dfc4799f2d391c5b6` |

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
