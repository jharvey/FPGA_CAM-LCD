# main.py: executed on every boot (upstream esp32ecp5 main.py plus the FCL sensor-hub link)
try:
  import wifiman
except:
  print('wifiman.py error')
import gc
gc.collect()
import uftpd
from ntptime import settime
try:
  settime()
  print('NTP time set')
except:
  print('NTP not available')
try:
  import fcl_hub
  fcl_hub.start()
  print('FCL hub link on UART1 (GPIO11/12)')
except Exception as e:
  print('fcl_hub not started:', e)
# USB serial stream (telemetry, commands, Wi-Fi setup, audio): see fcl_usb.py.  The command "repl" on the port
# returns to this prompt; create a file named "nostream" on the ESP32 to boot straight to the prompt.
try:
  open('nostream').close()
  print('nostream file found: USB stream not started (import fcl_usbdev; fcl_usbdev.run())')
except OSError:
  try:
    import fcl_usbdev
    fcl_usbdev.run()
  except Exception as e:
    print('fcl_usbdev stopped:', e)
