#include "sensors.h"
#include "board.h"
#include "hal.h"
#include <math.h>

/* ---------------------------------------------------------------- ICM-42688-P */
#define ICM_DEVICE_CONFIG   0x11
#define ICM_TEMP_DATA1      0x1D
#define ICM_PWR_MGMT0       0x4E
#define ICM_GYRO_CONFIG0    0x4F
#define ICM_ACCEL_CONFIG0   0x50
#define ICM_WHO_AM_I        0x75
#define ICM_REG_BANK_SEL    0x76
#define ICM_WHOAMI_VAL      0x47
#define ICM_ODR_200HZ       0x07
#define ICM_ACC_4G          (2u << 5)
#define ICM_GYR_500DPS      (2u << 5)
#define ICM_ACC_LSB_PER_G   8192.0f
#define ICM_GYR_LSB_PER_DPS 65.5f

static int wr8(uint8_t a, uint8_t r, uint8_t v) { return hal_i2c_write(a, r, &v, 1); }

static const int imu_axes[3][3] = AXES_IMU;
static const int mag_axes[3][3] = AXES_MAG;

static vec3 remap(const int m[3][3], float x, float y, float z)
{
    vec3 o = { m[0][0] * x + m[0][1] * y + m[0][2] * z,
               m[1][0] * x + m[1][1] * y + m[1][2] * z,
               m[2][0] * x + m[2][1] * y + m[2][2] * z };
    return o;
}

int icm42688_init(void)
{
    uint8_t id = 0;
    wr8(I2C_ADDR_ICM42688, ICM_REG_BANK_SEL, 0);
    if (hal_i2c_read(I2C_ADDR_ICM42688, ICM_WHO_AM_I, &id, 1) || id != ICM_WHOAMI_VAL)
        return -1;
    wr8(I2C_ADDR_ICM42688, ICM_DEVICE_CONFIG, 0x01);            /* soft reset */
    hal_delay_ms(2);
    wr8(I2C_ADDR_ICM42688, ICM_GYRO_CONFIG0, ICM_GYR_500DPS | ICM_ODR_200HZ);
    wr8(I2C_ADDR_ICM42688, ICM_ACCEL_CONFIG0, ICM_ACC_4G | ICM_ODR_200HZ);
    wr8(I2C_ADDR_ICM42688, ICM_PWR_MGMT0, 0x0F);                /* gyro + accel low-noise */
    hal_delay_ms(45);                                            /* gyro start-up */
    return 0;
}

static int16_t be16(const uint8_t *p) { return (int16_t)((p[0] << 8) | p[1]); }
static int16_t le16(const uint8_t *p) { return (int16_t)((p[1] << 8) | p[0]); }

int icm42688_read(vec3 *acc_g, vec3 *gyr_dps, float *temp_c)
{
    uint8_t b[14];                                               /* TEMP(2) ACCEL(6) GYRO(6), big-endian */
    if (hal_i2c_read(I2C_ADDR_ICM42688, ICM_TEMP_DATA1, b, sizeof b))
        return -1;
    if (temp_c)
        *temp_c = be16(b) / 132.48f + 25.0f;
    *acc_g = remap(imu_axes, be16(b + 2) / ICM_ACC_LSB_PER_G, be16(b + 4) / ICM_ACC_LSB_PER_G, be16(b + 6) / ICM_ACC_LSB_PER_G);
    *gyr_dps = remap(imu_axes, be16(b + 8) / ICM_GYR_LSB_PER_DPS, be16(b + 10) / ICM_GYR_LSB_PER_DPS, be16(b + 12) / ICM_GYR_LSB_PER_DPS);
    return 0;
}

/* ---------------------------------------------------------------- LIS2MDL */
#define MAG_WHO_AM_I        0x4F
#define MAG_CFG_A           0x60
#define MAG_CFG_B           0x61
#define MAG_CFG_C           0x62
#define MAG_OUTX_L          0x68
#define MAG_WHOAMI_VAL      0x40
#define MAG_GAUSS_PER_LSB   0.0015f

int lis2mdl_init(void)
{
    uint8_t id = 0;
    if (hal_i2c_read(I2C_ADDR_LIS2MDL, MAG_WHO_AM_I, &id, 1) || id != MAG_WHOAMI_VAL)
        return -1;
    wr8(I2C_ADDR_LIS2MDL, MAG_CFG_A, 0x80 | (3u << 2) | 0x00);   /* temp comp, 100 Hz, continuous */
    wr8(I2C_ADDR_LIS2MDL, MAG_CFG_B, 0x02);                      /* offset cancellation */
    wr8(I2C_ADDR_LIS2MDL, MAG_CFG_C, 0x10);                      /* BDU */
    return 0;
}

int lis2mdl_read(vec3 *mag)
{
    uint8_t b[6];                                                /* little-endian */
    if (hal_i2c_read(I2C_ADDR_LIS2MDL, MAG_OUTX_L, b, sizeof b))
        return -1;
    *mag = remap(mag_axes, le16(b) * MAG_GAUSS_PER_LSB, le16(b + 2) * MAG_GAUSS_PER_LSB, le16(b + 4) * MAG_GAUSS_PER_LSB);
    return 0;
}

/* ---------------------------------------------------------------- LPS22DF */
#define BARO_WHO_AM_I       0x0F
#define BARO_CTRL1          0x10
#define BARO_CTRL2          0x11
#define BARO_PRESS_XL       0x28
#define BARO_WHOAMI_VAL     0xB4

int lps22df_init(void)
{
    uint8_t id = 0;
    if (hal_i2c_read(I2C_ADDR_LPS22DF, BARO_WHO_AM_I, &id, 1) || id != BARO_WHOAMI_VAL)
        return -1;
    wr8(I2C_ADDR_LPS22DF, BARO_CTRL2, 0x08);                     /* BDU */
    wr8(I2C_ADDR_LPS22DF, BARO_CTRL1, 4u << 3);                  /* ODR 25 Hz  CHECK code */
    return 0;
}

int lps22df_read(float *p_hpa, float *t_c)
{
    uint8_t b[5];
    if (hal_i2c_read(I2C_ADDR_LPS22DF, BARO_PRESS_XL, b, sizeof b))
        return -1;
    int32_t p = (int32_t)((uint32_t)b[2] << 24 | (uint32_t)b[1] << 16 | (uint32_t)b[0] << 8) >> 8;
    *p_hpa = p / 4096.0f;
    if (t_c)
        *t_c = le16(b + 3) / 100.0f;
    return 0;
}

float baro_altitude_m(float p_hpa, float p0_hpa)
{
    return 44330.0f * (1.0f - powf(p_hpa / p0_hpa, 1.0f / 5.255f));
}

/* ---------------------------------------------------------------- VL53L1X (simplified) */
#define TOF_MODEL_ID        0x010F
#define TOF_GPIO_STATUS     0x0031
#define TOF_INT_CLEAR       0x0086
#define TOF_MODE_START      0x0087
#define TOF_RANGE_MM        0x0096
#define TOF_MODEL_VAL       0xEA

int vl53l1x_init(void)
{
    uint8_t id = 0, v;
    hal_tof_xshut(true);
    hal_delay_ms(2);
    if (hal_i2c_read16(I2C_ADDR_VL53L1X, TOF_MODEL_ID, &id, 1) || id != TOF_MODEL_VAL)
        return -1;
    /* TODO: write ST's default configuration block (registers 0x2D..0x87) here, as VL53L1X_SensorInit does */
    v = 0x40;
    return hal_i2c_write16(I2C_ADDR_VL53L1X, TOF_MODE_START, &v, 1);
}

int vl53l1x_read(uint16_t *mm, bool *fresh)
{
    uint8_t st = 0, b[2], one = 1;
    *fresh = false;
    if (hal_i2c_read16(I2C_ADDR_VL53L1X, TOF_GPIO_STATUS, &st, 1))
        return -1;
    if ((st & 1) == 0)                                           /* data ready (interrupt polarity active low) CHECK */
    {
        if (hal_i2c_read16(I2C_ADDR_VL53L1X, TOF_RANGE_MM, b, 2))
            return -1;
        *mm = (uint16_t)(b[0] << 8 | b[1]);
        *fresh = true;
        hal_i2c_write16(I2C_ADDR_VL53L1X, TOF_INT_CLEAR, &one, 1);
    }
    return 0;
}

/* ---------------------------------------------------------------- AD7689 */
/* CFG(13)=1 update, INCC(12:10)=111 unipolar to GND, INx(9:7), BW(6)=1 full, REF(5:3)=001 internal 2.5 V  CHECK,
   SEQ(2:1)=00, RB(0)=1 no readback */
static uint16_t ad7689_cfg(int ch)
{
    return (uint16_t)((1u << 13) | (7u << 10) | ((unsigned)ch << 7) | (1u << 6) | (1u << 3) | 1u);
}

int ad7689_read_all(uint16_t out[8])
{
    /* the result of a conversion comes out two frames after its configuration word went in */
    for (int k = 0; k < 10; k++)
    {
        uint16_t r = hal_adc_xfer(ad7689_cfg(k < 8 ? k : 0));
        if (k >= 2)
            out[k - 2] = r;
    }
    return 0;
}
