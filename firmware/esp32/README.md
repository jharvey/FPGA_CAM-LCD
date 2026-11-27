# ESP32-S3 firmware: esp32ecp5 + FCL hub link

Starting point: **emard/esp32ecp5** (MIT, `LICENSE_esp32ecp5.txt`), the MicroPython ECP5 programmer used on the
ULX3S, copied at upstream commit `f6cea24` (2025-09-14). It programs the ECP5 over JTAG (SRAM or config flash) from
files on the ESP32 or the SD card, through Wi-Fi FTP (`uftpd`) or the REPL. Upstream docs: `upstream_docs/`.

## Files

| File | From | Change for this board |
|---|---|---|
| `ecp5.py`, `ecp5wp.py`, `sdraw.py`, `gzip4k.py`, `wifiman.py`, `ecp5setup.py`, `boot.py` | upstream | none |
| `uftpd.py` | upstream | `mount()` first tries the S3's SDMMC 4-bit bus on the pins in `sdpin.py`, then falls back to upstream |
| `jtagpin.py` | new | JTAG pins of U9: TCK 18, TMS 9, TDI 10, TDO 8 (`fpga/ESP32_PINS.md`); GPIO2 / GPIO1 (unconnected) for the SPI workaround and the LED |
| `sdpin.py` | new | microSD on SDMMC: CLK 15, CMD 7, D0 16, D1 17, D2 5, D3 6, card detect 4 |
| `fcl_hub.py` | earlier design | link to a C hub on a soft CPU in the FPGA (not built). Kept for the simulator's `--hub c` path; the unit does not load it |
| `fcl_bridge.py` | new | driver for the FPGA bridge (`fpga/bridge/fcl_bridge.v`) on UART1 (TX 11 -> FPGA L1, RX 12 <- FPGA L2, 921600): I2C, ADC, servos, buttons, LCD overlay |
| `fcl_fix.py` | new | attitude filter in 32-bit integer arithmetic, written for the viper compiler (native code, no heap use at 200 Hz) |
| `fcl_hubpy.py` | new | the sensor hub: sensor set-up, battery, buttons, down dot, overlay, telemetry |
| `fcl_magcal.py` | new | compass calibration (hard iron): automatic sphere fit in use, manual mode, stored in `magcal.json` |
| `fcl_app.py` | new | the layer above the hub: pages (Level, Height, Bearing, your own), the menu on B1 held, the `Unit` calls a page uses. `doc/DEVELOPER_GUIDE.md` |
| `fcl_cfg.py` | new | calibration values of one unit (`cal.json`): lens angle, mounting error, cell gains, temperature / distance / heading offsets, servo travel |
| `fcl_web.py` | new | the phone page over Wi-Fi (port 80): LCD text, readings, buttons. No password, so everyday commands only. Not run on hardware |
| `fcl_user_example.py` | new | an example page (a climb meter). Copy as `fcl_user.py` to load your own pages at start |
| `fcl_calc.py` | new | charge table, down dot, overlay text (also used by the PC tools) |
| `fcl_usb.py` | new | the USB text protocol (telemetry lines, commands); also runs on a PC, tested in the simulator |
| `fcl_usbdev.py` | new | the ESP32 side of it: USB serial port, Wi-Fi setup into `wifiman.conf`, I2S microphone / speaker as base64 lines. Not run on hardware |
| `main.py` | upstream + | starts the hub and the USB stream (`fcl_usbdev.run()`). The command `repl` on the port, or a file named `nostream`, gives the Python prompt back |

## Install

1. Flash MicroPython for the ESP32-S3 (the `ESP32_GENERIC_S3` build with SPIRAM) over the USB-C port.
2. Copy the files to the board, for example with `mpremote`:

   ```
   mpremote cp *.py :
   mpremote cp wifiman.conf :      # your Wi-Fi: one "ssid:password" per line (not in git)
   ```

3. Reset. FTP to the board's address; `put file.bit` / `put file.bit.gz` loads the FPGA, the `flash@` forms write the
   config flash (see `upstream_docs/README_esp32ecp5.md`).

In the REPL, `fcl_hub.last` shows the latest telemetry (heading, tilt, altitude, distance, cells), `fcl_hub.servo(0, 1500)`
and `fcl_hub.mode(2)` send commands, `fcl_hub.log("/sd/fcl.csv")` logs while recording (B2).

## Not yet

- Not run on the board. The JTAG, SD and UART pins were checked pad by pad against U9 in the routed board (2026-11-27); the SDMMC call needs MicroPython 1.21 or
  later on the S3 (CHECK).
- The ROADMAP also wants USB mass storage for the SD card over the same USB-C port; MicroPython does not provide that.
  It needs either a native ESP-IDF / TinyUSB build later, or the card read through FTP meanwhile.
- `fcl_hub` needs the FPGA's soft CPU and its UART (`../hub/`), which do not exist yet. Until then it simply receives
  nothing.

## USB stream

See `doc/FIRMWARE_GUIDE.md` for the line format and commands. While the stream runs the USB port is not a Python
prompt: `mpremote` and Thonny need it stopped first (send `repl`, or create `nostream` and reset). Loading the FPGA
over Wi-Fi (FTP) is not affected.
