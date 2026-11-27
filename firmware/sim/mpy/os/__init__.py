# MicroPython only (firmware/sim/test_mpy.py): the built-in os plus the few os.path calls the simulator uses
from uos import *       # noqa: F401,F403
from . import path      # noqa: F401
