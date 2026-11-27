/* Drivers for the parts on the IMU I2C bus and the AD7689 battery ADC.
 * Register values follow the datasheets as far as known; marked CHECK where they must be confirmed on hardware. */
#ifndef FCL_SENSORS_H
#define FCL_SENSORS_H
#include <stdint.h>
#include <stdbool.h>

typedef struct { float x, y, z; } vec3;

/* ICM-42688-P: +-4 g, +-500 dps, 200 Hz, low-noise mode */
int  icm42688_init(void);
int  icm42688_read(vec3 *acc_g, vec3 *gyr_dps, float *temp_c);

/* LIS2MDL: 100 Hz continuous, temperature compensation, offset cancellation */
int  lis2mdl_init(void);
int  lis2mdl_read(vec3 *mag_gauss);

/* LPS22DF: 25 Hz, BDU */
int  lps22df_init(void);
int  lps22df_read(float *p_hpa, float *t_c);
float baro_altitude_m(float p_hpa, float p0_hpa);

/* VL53L1X: long mode, continuous. Simplified: production code should use ST's ULD API (VL53L1X_SensorInit) */
int  vl53l1x_init(void);
int  vl53l1x_read(uint16_t *mm, bool *fresh);

/* AD7689: 8 channels, unipolar to GND, internal 2.5 V reference */
int  ad7689_read_all(uint16_t out[8]);
#endif
