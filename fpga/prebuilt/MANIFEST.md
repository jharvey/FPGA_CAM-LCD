# Stored build outputs

Written by `python fpga/make_prebuilt.py` on 2026-11-27. Check your own build against these with `python fpga/make_prebuilt.py --check`.

Built from commit `c8ac71c995ac6a8ef37bd2f2042c59b666f54a9e`.

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
| full | `$glbnet$cam.m.w25` | 69.53 MHz possible, FAIL at 142.86 MHz (SDRAM clock of the camera design) |
| full | `$glbnet$cmos_xclk$TRELLIS_IO_OUT` | 47.62 MHz possible, PASS at 25.00 MHz (25 MHz board clock: bridge, overlay text memory, camera set-up) |
| full | `$glbnet$pix_clk_out$TRELLIS_IO_OUT` | 60.46 MHz possible, PASS at 18.00 MHz (LCD pixel clock) |
| camera | `$glbnet$v40f83b$TRELLIS_IO_IN` | 50.56 MHz possible, PASS at 25.00 MHz |
| camera | `$glbnet$v79e9a8$TRELLIS_IO_OUT` | 96.41 MHz possible, PASS at 12.00 MHz |
| camera | `$glbnet$w25` | 73.93 MHz possible, FAIL at 142.86 MHz |

The SDRAM clock of the camera design (142.9 MHz) does not meet timing by this estimate, in both designs that contain it. Builds before 2026-11-27 did not tell nextpnr the clock frequencies, so it checked every clock against 12 MHz and reported a pass.

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
| `full/fcl_full.bit` | 636668 | `39ab6479e5122697c75d64974642775e24532d94b498a212a37795d37864a966` |
| `full/fcl_top.lpf` | 11802 | `10992c4cc77cf57c9c054e6190b81e532e92ba2bd0e683c41a5422dfc3602094` |
| `full/main.v` | 119325 | `ef06d07dca38be0d72e572ea2295dbbe4e5dd3010e67015121ddb825e8fcb1ea` |
| `full/fcl_cam.v` | 3080 | `4851a4d02128caad0086373edf6325697fc74d635439b5090018696dea04a8fe` |
| `full/nextpnr.log` | 90724 | `91b10183ef4b16e1917a97b633adaddb650cfa7b102f10d2391e6a1771c99997` |
| `full/build_summary.txt` | 583 | `b7a42595c04f7fc9772e66a57679840fb6cd7f575345b91981f5ccd77fefb353` |
| `full/fcl_full.json` | 23978168 | `2562d0551de9305305c29202ae9e9735be5bb38e3fa055449f0884d7c63a8bfc` |
| `full/fcl_full.config` | 8144440 | `9ce029a559a27430529405b58bca002e2feeda66e77c9cec2bfe23c4fdef9ed0` |
| `full/yosys.log` | 1966004 | `ab159ae6ba3d9678a0be7b47524db995d48e30e3b032907b3948cd6f4cfef541` |
| `bridge/fcl_bridge.bit` | 324485 | `8027f0eeff3073a2caf9cc32b9e0c48ae70cf0dad6f1a8fce0c8a9677e8f9789` |
| `bridge/fcl_bridge_top.lpf` | 2745 | `583b6d25d4d0bb5cfabe8622aab4d0f0aaa113bb0e6557727431a5b55d83af64` |
| `bridge/nextpnr.log` | 27893 | `8df3e0d548eb8b048133aff4605e48ba0c9fe035cd285660c96cee93c7a8f723` |
| `bridge/fcl_bridge.json` | 5108412 | `8c9eab633fccd5e0addaef7c5d59b55e92f0378f2d263a5709517fc580f62da0` |
| `bridge/fcl_bridge.config` | 1219080 | `07ecdc235331460c582ca3517c7c5cc78f7e358085c6841621292343bd9694b3` |
| `bridge/yosys.log` | 683722 | `b9ea0382bcfe5e2bbeb46b3309673481b85b9c3b1d8bacb0bf963a4572ede151` |
| `camera/main.bit` | 575250 | `a0aad79018d92f4f216a66e2e71e1e93229a5fc29534fcb2fea0a79c383361b1` |
| `camera/main.lpf` | 9806 | `5f13dfae7fc105284d2d3e25cb5d9586c5827c8dea76dd732956789483e166da` |
| `camera/main.v` | 119325 | `ef06d07dca38be0d72e572ea2295dbbe4e5dd3010e67015121ddb825e8fcb1ea` |
| `camera/nextpnr.log` | 75339 | `d6a4c6e9bdd98f64f737d1138a24487202a794fcf0e52d33ea9a705b1f992a30` |
| `camera/build_summary.txt` | 406 | `6643dd9fdfc13c09675e4b007b3b54d28984152690d059fdf93a90f86a025c7a` |
| `camera/main.json` | 20929656 | `e9612bb300663cbcc5181b17d1e0a0dd057f92e86ea0aab7a422e7df7dcc0f80` |
| `camera/main.config` | 6788962 | `b845adce415c43de32102492520345bf5d5ba8613444c5ea31fb396106042ccb` |
| `camera/yosys.log` | 1283429 | `850d031f9062690e74277391bffb109f6c27878e5d36b8f37a1075b7619270f6` |

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
| `fpga/bridge/test_bridge.py` | 0 | ALL CHECKS PASSED |
| `fpga/osd/test_osd.py` | 0 | ALL FRAMES IDENTICAL |
