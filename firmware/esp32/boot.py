# boot.py: executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
# WebREPL only when it has been set up (import webrepl_setup).  Without webrepl_cfg.py, webrepl.start() raises an
# error, and an error in boot.py stops MicroPython from running main.py, so the unit's software would not start
# (found 2026-11-28 on the emulated ESP32 with MicroPython 1.24.1).
try:
  import webrepl
  webrepl.start()
except Exception as e:
  print('webrepl not started:', e)
