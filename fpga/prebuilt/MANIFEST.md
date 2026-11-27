# Stored build outputs

Written by `python fpga/make_prebuilt.py` on 2026-11-27. Check your own build against these with `python fpga/make_prebuilt.py --check`.

Built from commit `139c68501550ccee54fe1673d7fce766fc620484`.

| Design | Bitstream | What it is |
|---|---|---|
| bridge | `bridge/fcl_bridge.bit` | the sensor bridge alone (`fpga/bridge/fcl_bridge_top.v`): sensors, ADC, buttons, servos from the ESP32. No camera or LCD. For first bring-up. |
| camera | `camera/main.bit` | camera to TFT with the Sobel view (`fpga/CameraToTFTSobel_FCL.ice`). No bridge and no overlay yet. |

Neither has been loaded into a real board. nextpnr runs with a fixed seed, so the same tool versions should give the same files.

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
| `bridge/fcl_bridge.bit` | 323613 | `f412b2fe19d67889bb47e0fb49075767ca1abd90cdc8addae2997e5d92e77cb7` |
| `bridge/fcl_bridge_top.lpf` | 2745 | `583b6d25d4d0bb5cfabe8622aab4d0f0aaa113bb0e6557727431a5b55d83af64` |
| `bridge/nextpnr.log` | 29187 | `063c4a7033a56238f28aaa64bb7bc3628c4cd3c66225b88fdd7a8b3a9494e701` |
| `bridge/fcl_bridge.json` | 5047236 | `e7cd2fb540541a14bb6af060f5bef5ac36a2177e0fb908e02c1e107d2235075b` |
| `bridge/fcl_bridge.config` | 1217300 | `8856dc58301b68ee2c8b42e139587095cee75f3db4e137463669b9a6f8bd3211` |
| `bridge/yosys.log` | 680337 | `c09effe776a3a39e55acb8fd54b4f9c7a37f6dc5aa509df299d7a856153d05fd` |
| `camera/main.bit` | 575250 | `a0aad79018d92f4f216a66e2e71e1e93229a5fc29534fcb2fea0a79c383361b1` |
| `camera/main.lpf` | 9683 | `00f45fc6f26bd25f2bae1d07b953cf16935db2c21ea2e09be438775f0698eb04` |
| `camera/main.v` | 119325 | `ef06d07dca38be0d72e572ea2295dbbe4e5dd3010e67015121ddb825e8fcb1ea` |
| `camera/nextpnr.log` | 75357 | `f1c8f343295e26cf60fb4d69b4523fe896dc9fcf5fe417927fda0add5bb8040a` |
| `camera/main.json` | 20929656 | `e9612bb300663cbcc5181b17d1e0a0dd057f92e86ea0aab7a422e7df7dcc0f80` |
| `camera/main.config` | 6788962 | `b845adce415c43de32102492520345bf5d5ba8613444c5ea31fb396106042ccb` |
| `camera/yosys.log` | 1283429 | `ba398534653b57da75860ac143d91e63e34a50e38fc1190a9530e5e5c356e02b` |

## Tests at build time

Full output in `test_results.txt`.

| Test | Exit code | Last line |
|---|---|---|
| `firmware/sim/test_usb.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_filter.py` | 0 | ALL CHECKS PASSED |
| `firmware/sim/test_magcal.py` | 0 | ALL CHECKS PASSED |
| `fpga/bridge/test_bridge.py` | 0 | ALL CHECKS PASSED |
| `fpga/osd/test_osd.py` | 0 | ALL FRAMES IDENTICAL |
