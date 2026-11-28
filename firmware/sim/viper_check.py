"""The ESP32's integer code alone, on made-up sensor data: the attitude filter (fcl_fix.py, viper) and the CRC of
the FPGA link (fcl_bridge.py).  No floats anywhere, so every interpreter and every processor must print exactly
the same lines.  Run by test_esp32_qemu.py on the emulated ESP32 and by ordinary Python, and compared.
"""
import sys

if sys.platform != "esp32":
    HERE = __file__.replace("\\", "/").rsplit("/", 1)[0] if "/" in __file__.replace("\\", "/") else "."
    sys.path.insert(0, HERE + "/../esp32")
import fcl_fix      # noqa: E402
import fcl_bridge   # noqa: E402

seed = 12345


def rnd(n):
    """a number 0 .. n-1 from a fixed sequence (a linear congruential generator in 31 bits)"""
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed % n


def s16(v):
    v &= 0xFFFF
    return bytes((v >> 8, v & 255))


st = fcl_fix.new_state()
st[16], st[17], st[18] = 40, -25, 12                       # a compass offset
for i, w in enumerate((17000, 900, -300, 900, 15000, 500, -300, 500, 16200)):
    st[20 + i] = w                                          # and a soft-iron matrix, Q14
imu = bytearray(14)
mag = bytearray(6)
gx = gy = gz = 0
for n in range(1200):
    # an IMU sample: the unit turning slowly and shaking a little, the accelerometer near 1 g
    gx = max(-3000, min(3000, gx + rnd(201) - 100))
    gy = max(-3000, min(3000, gy + rnd(201) - 100))
    gz = max(-3000, min(3000, gz + rnd(201) - 100))
    ax, ay, az = rnd(1601) - 800, rnd(1601) - 800, 8192 + rnd(801) - 400
    imu[0:2] = s16(1300)
    imu[2:4], imu[4:6], imu[6:8] = s16(ax), s16(ay), s16(az)
    imu[8:10], imu[10:12], imu[12:14] = s16(gx), s16(gy), s16(gz)
    fcl_fix.imu_step(st, imu, 4900 + rnd(201))
    if n % 2 == 0:
        mx, my, mz = 250 + rnd(121) - 60, -120 + rnd(121) - 60, 180 + rnd(121) - 60
        mag[0], mag[1] = mx & 255, (mx >> 8) & 255
        mag[2], mag[3] = my & 255, (my >> 8) & 255
        mag[4], mag[5] = mz & 255, (mz >> 8) & 255
        fcl_fix.mag_step(st, mag)
    if n % 100 == 99:
        print("step %d: %s" % (n + 1, " ".join(str(st[i]) for i in range(16))))
data = bytearray(rnd(256) for _ in range(1000))
print("crc16 %04x %04x %04x" % (fcl_bridge.crc16(data, 0xFFFF), fcl_bridge.crc16(data[:37], 0xFFFF), fcl_bridge.crc16(b"", 0xFFFF)))
print("END")
