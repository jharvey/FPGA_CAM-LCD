# FPGA_CAM-LCD (FCL) board: microSD SD1 on the ESP32-S3 SDMMC 4-bit bus (fpga/ESP32_PINS.md).
# The same lines also reach the FPGA, so they are released (hi-Z) when the FPGA takes the card.
d0 = const(16)    # SD_D0
d1 = const(17)    # SD_D1
d2 = const(5)     # SD_D2
d3 = const(6)     # SD_D3
clk = const(15)   # SD_CLK
cmd = const(7)    # SD_CMD
cd = const(4)     # SD_CD, card detect (R86 pull-up)
hiz = bytearray([d0, d1, d2, d3, clk, cmd])  # to release SD
