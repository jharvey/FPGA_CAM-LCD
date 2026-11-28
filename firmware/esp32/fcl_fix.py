# Attitude filter in 32-bit integer arithmetic, written for MicroPython's viper compiler (native code, no heap
# use, no floats in the 200 Hz path).  The same file runs unchanged under CPython for the simulator and tests:
# there `viper` does nothing and the state lives in array('i'), which raises OverflowError if a value ever
# leaves the 32-bit range, so the tests also prove the arithmetic never overflows.
#
# Method: a complementary filter on two vectors kept in the device frame:
#     up    (unit vector, Q28)   turned by the gyro, pulled toward the accelerometer when it reads about 1 g
#     north (magnetometer counts, Q16)   turned by the gyro, pulled toward the magnetometer
# Turning a world-fixed vector v seen from a body rotating at w:  v += (v x w) dt.
# Heading, pitch and roll are worked out from the two vectors at the telemetry rate (fcl_hubpy.py), in floats.
#
# State layout (array('i'), 29 words):
#   0..2 up (Q28)   3..5 north (Q16)   6..8 gyro bias (raw counts)   9..11 bias sum   12 bias samples
#   13 gain shift for the accelerometer pull   14 samples seen   15 magnetometer started
#   16..18 compass offset in counts (hard iron, from fcl_magcal.py), subtracted from every reading
#   19 spare   20..28 compass matrix, Q14, row by row (soft iron, from fcl_magcal.py), applied after the offset
from array import array
try:
    import micropython                   # the decorator must be spelled @micropython.viper for the compiler to see it
except ImportError:                      # CPython: plain functions, arrays instead of pointers
    class micropython:
        @staticmethod
        def viper(f):
            return f

    def ptr32(x):
        return x

    def ptr8(x):
        return x

ST_WORDS = 29
ACC_1G = 8192                            # ICM-42688-P at +-4 g: counts per g
BIAS_SAMPLES = 200                       # gyro bias: mean of the first second, if the unit is still


def new_state():
    st = array("i", [0] * ST_WORDS)
    st[2] = 1 << 28                      # up = +z until the accelerometer says otherwise
    st[13] = 2                           # fast pull for the first second, then slow
    st[20] = st[24] = st[28] = 1 << 14   # compass matrix: identity until a calibration gives another
    return st


@micropython.viper
def imu_step(st_o, buf_o, dt_us: int) -> int:
    """one ICM-42688-P sample: buf = 14 bytes from register 0x1D (temperature, accel xyz, gyro xyz, big-endian)"""
    st = ptr32(st_o)
    b = ptr8(buf_o)
    one = 1
    s = 0                                # ptr32 reads are signed on the 32-bit ESP32 but unsigned on a 64-bit PC
    if (one << 31) > 0:                  # (MicroPython Unix port): there, sign-extend every word that is read
        s = 32
    # ---- unpack
    ax = (b[2] << 8) | b[3]
    ay = (b[4] << 8) | b[5]
    az = (b[6] << 8) | b[7]
    gx = (b[8] << 8) | b[9]
    gy = (b[10] << 8) | b[11]
    gz = (b[12] << 8) | b[13]
    if ax >= 32768:
        ax -= 65536
    if ay >= 32768:
        ay -= 65536
    if az >= 32768:
        az -= 65536
    if gx >= 32768:
        gx -= 65536
    if gy >= 32768:
        gy -= 65536
    if gz >= 32768:
        gz -= 65536
    n = ((st[14] << s) >> s)
    st[14] = n + 1
    # ---- gyro bias from the first second, while the rates are small (under about 6 deg/s)
    if n < 200:                          # BIAS_SAMPLES (viper wants the literal)
        if gx > -400 and gx < 400 and gy > -400 and gy < 400 and gz > -400 and gz < 400:
            st[9] = ((st[9] << s) >> s) + gx
            st[10] = ((st[10] << s) >> s) + gy
            st[11] = ((st[11] << s) >> s) + gz
            st[12] = ((st[12] << s) >> s) + 1
    elif n == 200:
        k = ((st[12] << s) >> s)
        if k > 20:
            # rounded division by a positive count, written with shifts and a loop-free reciprocal
            r = 65536 // k
            st[6] = (((st[9] << s) >> s) * r + 32768) >> 16
            st[7] = (((st[10] << s) >> s) * r + 32768) >> 16
            st[8] = (((st[11] << s) >> s) * r + 32768) >> 16
        st[13] = 7                       # accelerometer pull: 1/128 per sample from now on
    gx -= ((st[6] << s) >> s)
    gy -= ((st[7] << s) >> s)
    gz -= ((st[8] << s) >> s)
    # ---- rotation this step, Q21 radians:  counts / 65.5 deg/s * pi/180 * dt
    #      = counts * dt_us * 5.588e-4   ->  ((counts * dt_us) >> 9) * 586 >> 11        (586 / 2^20 = 5.588e-4)
    if dt_us > 20000:
        dt_us = 20000
    wx = (((gx * dt_us) >> 9) * 586) >> 11
    wy = (((gy * dt_us) >> 9) * 586) >> 11
    wz = (((gz * dt_us) >> 9) * 586) >> 11
    # ---- turn both vectors:  v += v x w      (products Q(v) * Q21 >> 21, in three 10-bit limbs of v)
    i = 0
    while i < 6:
        v0 = ((st[i] << s) >> s)
        v1 = ((st[i + 1] << s) >> s)
        v2 = ((st[i + 2] << s) >> s)
        c0 = ((((v1 >> 20) * wz) >> 1) + ((((v1 >> 10) & 1023) * wz) >> 11) + (((v1 & 1023) * wz) >> 21)
              - (((v2 >> 20) * wy) >> 1) - ((((v2 >> 10) & 1023) * wy) >> 11) - (((v2 & 1023) * wy) >> 21))
        c1 = ((((v2 >> 20) * wx) >> 1) + ((((v2 >> 10) & 1023) * wx) >> 11) + (((v2 & 1023) * wx) >> 21)
              - (((v0 >> 20) * wz) >> 1) - ((((v0 >> 10) & 1023) * wz) >> 11) - (((v0 & 1023) * wz) >> 21))
        c2 = ((((v0 >> 20) * wy) >> 1) + ((((v0 >> 10) & 1023) * wy) >> 11) + (((v0 & 1023) * wy) >> 21)
              - (((v1 >> 20) * wx) >> 1) - ((((v1 >> 10) & 1023) * wx) >> 11) - (((v1 & 1023) * wx) >> 21))
        st[i] = v0 + c0
        st[i + 1] = v1 + c1
        st[i + 2] = v2 + c2
        i += 3
    # ---- pull "up" toward the accelerometer when it reads 0.85 .. 1.15 g
    a2 = ax * ax + ay * ay + az * az                      # up to 3 * 2^30: keep it in range
    if a2 < 0:
        a2 = 1000000000                                   # (a literal above 2^30 is not a viper int on a 32-bit MicroPython)
    if a2 > 48486605 and a2 < 88752129:                   # (0.85 g)^2 .. (1.15 g)^2 in counts^2
        sh = ((st[13] << s) >> s)
        st[0] = ((st[0] << s) >> s) + ((((ax << 15) - ((st[0] << s) >> s))) >> sh)
        st[1] = ((st[1] << s) >> s) + ((((ay << 15) - ((st[1] << s) >> s))) >> sh)
        st[2] = ((st[2] << s) >> s) + ((((az << 15) - ((st[2] << s) >> s))) >> sh)
    # ---- keep "up" at unit length:  v += v * (1 - |v|^2) / 2, a small step each sample
    x = ((st[0] << s) >> s) >> 14
    y = ((st[1] << s) >> s) >> 14
    z = ((st[2] << s) >> s) >> 14
    e = (1 << 28) - (x * x + y * y + z * z)
    if e > 65535:
        e = 65535
    if e < -65535:
        e = -65535
    st[0] = ((st[0] << s) >> s) + ((x * e) >> 15)
    st[1] = ((st[1] << s) >> s) + ((y * e) >> 15)
    st[2] = ((st[2] << s) >> s) + ((z * e) >> 15)
    return n


@micropython.viper
def mag_step(st_o, buf_o) -> int:
    """one LIS2MDL sample: buf = 6 bytes from register 0x68 (x, y, z little-endian), 1.5 mG per count"""
    st = ptr32(st_o)
    b = ptr8(buf_o)
    one = 1
    s = 0                                # ptr32 reads are signed on the 32-bit ESP32 but unsigned on a 64-bit PC
    if (one << 31) > 0:                  # (MicroPython Unix port): there, sign-extend every word that is read
        s = 32
    mx = b[0] | (b[1] << 8)
    my = b[2] | (b[3] << 8)
    mz = b[4] | (b[5] << 8)
    if mx >= 32768:
        mx -= 65536
    if my >= 32768:
        my -= 65536
    if mz >= 32768:
        mz -= 65536
    if mx > 8000 or mx < -8000 or my > 8000 or my < -8000 or mz > 8000 or mz < -8000:
        return 0                                          # over 12 gauss: not the earth's field
    mx -= ((st[16] << s) >> s)
    my -= ((st[17] << s) >> s)
    mz -= ((st[18] << s) >> s)
    # soft iron: the matrix (Q14, entries under 2) turns the squashed sphere of readings round again.  With
    # readings within +-16000 after the offset the sums stay under 2^31.
    m0 = ((st[20] << s) >> s) * mx + ((st[21] << s) >> s) * my + ((st[22] << s) >> s) * mz
    m1 = ((st[23] << s) >> s) * mx + ((st[24] << s) >> s) * my + ((st[25] << s) >> s) * mz
    m2 = ((st[26] << s) >> s) * mx + ((st[27] << s) >> s) * my + ((st[28] << s) >> s) * mz
    mx = m0 >> 14
    my = m1 >> 14
    mz = m2 >> 14
    if ((st[15] << s) >> s) == 0:
        st[3] = mx << 16
        st[4] = my << 16
        st[5] = mz << 16
        st[15] = 1
        return 1
    sh = 2
    if ((st[14] << s) >> s) > 200:
        sh = 5                                            # 1/32 per sample at 100 Hz
    st[3] = ((st[3] << s) >> s) + (((mx << 16) - ((st[3] << s) >> s)) >> sh)
    st[4] = ((st[4] << s) >> s) + (((my << 16) - ((st[4] << s) >> s)) >> sh)
    st[5] = ((st[5] << s) >> s) + (((mz << 16) - ((st[5] << s) >> s)) >> sh)
    return 1
