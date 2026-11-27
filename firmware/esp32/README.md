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
| `fcl_hub.py` | new | UART1 (TX 11 -> FPGA L1, RX 12 <- FPGA L2, 921600): decodes the sensor hub's telemetry and events, sends servo / mode commands, optional CSV log |
| `main.py` | upstream + | also starts `fcl_hub` |

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

- Not run on the board. The JTAG and SD pin numbers are from the pin map; the SDMMC call needs MicroPython 1.21 or
  later on the S3 (CHECK).
- The ROADMAP also wants USB mass storage for the SD card over the same USB-C port; MicroPython does not provide that.
  It needs either a native ESP-IDF / TinyUSB build later, or the card read through FTP meanwhile.
- `fcl_hub` needs the FPGA's soft CPU and its UART (`../hub/`), which do not exist yet. Until then it simply receives
  nothing.
