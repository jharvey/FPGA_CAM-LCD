# FPGA_CAM-LCD (FCL) board, ESP32-S3-WROOM-1-N8R2 (U9) -> ECP5 JTAG (fpga/ESP32_PINS.md)
tms = const(9)     # JTAG_TMS, pad 17
tck = const(18)    # JTAG_TCK, pad 11
tdi = const(10)    # JTAG_TDI, pad 18
tdo = const(8)     # JTAG_TDO, pad 12
tcknc = const(2)   # GPIO2, unconnected: free pin for the SPI workaround
led = const(1)     # GPIO1, unconnected: the board has no ESP32 LED
