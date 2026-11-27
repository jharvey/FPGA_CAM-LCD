# Firmware draft (2026-11-27)

A first draft, not run on hardware. The board's sensors sit on two different chips, so the firmware has two halves
that talk over a UART.

| Part | Runs on | Handles | State |
|---|---|---|---|
| `common/` | both (portable C) | sensor drivers, attitude / heading fusion, battery monitor, buttons, power-off, link protocol | simulated: all checks pass |
| `hub/` | soft RISC-V CPU inside the ECP5 (LiteX) | glue from `common/` to the FPGA's I2C, SPI, GPIO, PWM, UART | draft, not built (needs a LiteX SoC) |
| `esp32/` | ESP32-S3 (U9) | **emard's esp32ecp5** (ECP5 JTAG programmer over Wi-Fi FTP, MicroPython) set to this board's pins, plus `fcl_hub.py` for the hub link | not run; see `esp32/README.md` |
| `sim/` | your PC / the VM | runs `common/` against modelled sensors with a scripted 32 s scenario; `test_link_py.py` decodes the hub's link bytes with `esp32/fcl_hub.py` | 12 + 5 checks, all pass |

Why two halves: the IMU (ICM-42688-P), compass (LIS2MDL), barometer (LPS22DF), distance sensor (VL53L1X), battery ADC
(AD7689), buttons, LEDs and servo outputs all wire to the FPGA (`fpga/IO_REMAP.md`,
`doc/constraints/camera_display_pinmap.md`). Wi-Fi, USB, the SD card and audio are on the ESP32
(`fpga/ESP32_PINS.md`). The two meet on the UART at FPGA L1/L2 <-> ESP32 GPIO11/12.

## What the draft does

- **Attitude and heading:** Madgwick filter on accel + gyro + compass at 200 Hz; gyro bias learned in the first second
  while still. Heading 0-360 from north, pitch and roll in degrees.
- **Altitude:** from the barometer, relative to power-up.
- **Distance:** VL53L1X, 20 Hz (simplified driver; production code should use ST's ULD API, see `TODO` in `sensors.c`).
- **Batteries:** three cell voltages, three cell NTC temperatures and VSYS from the AD7689 at 5 Hz; low (3.4 V),
  cut-off (3.2 V) and hot (55 C) flags and events.
- **Buttons:** B0 held 2 s switches off (releases the power hold), B1 cycles an overlay mode, B2 toggles SD recording.
- **Servo 1:** follows pitch to keep a camera level (demo), until the ESP32 sends a servo command.
- **Link** (`common/link.h`): framed, CRC-checked messages. Telemetry 20 Hz hub -> ESP32; events (buttons, low cell,
  power-off); commands (servo, mode) ESP32 -> hub.
- **ESP32:** keeps the ULX3S programmer role (esp32ecp5: load or flash the FPGA over Wi-Fi FTP); `fcl_hub.py` adds the telemetry, events and commands.

## Run the simulator

```
cd firmware/sim
make
./fcl_sim fcl_sim.csv          # prints PASS / FAIL per check, exit code 0 when all pass
python3 plot.py fcl_sim.csv    # fcl_sim.png
```

Needs gcc and Python with matplotlib. The scenario: 2 s still, then turning at 18 deg/s while pitching +-20 deg and
rolling +-10 deg, a 3 m climb, a moving target for the distance sensor, cell 3 running down past 3.4 V, B1 / B2
presses, a mode and a servo command from the ESP32, and B0 held 2 s.

## ESP32 firmware

MicroPython files; see `esp32/README.md` for install.

## Before it runs on the board (CHECK items)

- Done 2026-11-27: the ESP32 JTAG / SD / UART pins (`esp32/jtagpin.py`, `sdpin.py`, `fcl_hub.py`) and the hub's FPGA
  pins (`hub/fcl_hub_pins.lpf`) were checked against the routed board, pad by pad.

- Sensor axis orientation on the PCB (`AXES_IMU`, `AXES_MAG` in `common/board.h` are identity for now), and a compass
  hard-iron / soft-iron calibration once it is in the case.
- AD7689 channels for the NTCs of cells 2 and 3 (assumed IN6 / IN7), the NTC beta value, the reference setting.
- LPS22DF ODR code, VL53L1X data-ready polarity and its default configuration block.
- The FPGA side: a LiteX SoC with a VexRiscv CPU, I2C, SPI, GPIO, PWM and a second UART on the pins listed in
  `hub/hal_litex.c`, merged with the existing camera-to-TFT design (`fpga/CameraToTFTSobel_FCL.ice`).
- The power-hold signal name and polarity on the soft-shutdown path.
