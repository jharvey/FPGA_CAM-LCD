"""MicroPython (Unix port) only: run the unit's real main loop, firmware/esp32/fcl_usbdev.py, on a PC.

    micropython mpy_unit.py <work dir>        commands on stdin, the USB stream on stdout; "repl" ends it

machine.Pin / I2S / UART and network are stand-ins (firmware/sim/mpy); the UART leads to the Python model of the
FPGA bridge with the simulated sensors behind it, in real time.  Started by test_mpy.py.
"""
import sys

import uos

HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
if not HERE.startswith("/"):                 # absolute: the work directory changes below
    HERE = uos.getcwd() + "/" + HERE
sys.path.insert(0, HERE)
sys.path.insert(0, HERE + "/../esp32")
sys.path.insert(0, HERE + "/mpy")
import os           # noqa: E402
import machine      # noqa: E402
import fcl_usbdev   # noqa: E402

os.chdir(sys.argv[1])               # the ESP32's flash: cal.json, magcal.json, wifiman.conf, fcl001.log
try:
    import fcl_web
    # the page is served on port 80 on the unit: not as an ordinary user on a PC
    _init = fcl_web.Web.__init__    # so the test moves it to a high port

    def init(self, usb, hub, plat=None, port=80):
        _init(self, usb, hub, plat, 18474)
    fcl_web.Web.__init__ = init
except ImportError:
    pass
fcl_usbdev.run()
m = machine.UART.last.model
print("#unit servo %s" % list(m.servo))
print("#unit i2s %s written %d" % (machine.I2S.made, machine.I2S.written))
print("#unit row4 |%s|" % m.osd_rows()[4])
print("#unit files %s" % sorted(os.listdir(".")))
print("#unit end")
