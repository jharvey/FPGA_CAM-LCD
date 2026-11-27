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
