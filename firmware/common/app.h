/* Sensor-hub application: runs on the soft CPU in the FPGA (and unchanged in the simulator). */
#ifndef FCL_APP_H
#define FCL_APP_H
#include "fusion.h"
#include "link.h"
#include "hal.h"
#include <stdbool.h>

typedef struct {
    uint32_t tick;
    fusion_t fus;
    vec3 acc, gyr, mag;
    float imu_temp_c;
    float p_hpa, p0_hpa, baro_t_c, alt_m;
    uint16_t tof_mm;
    bool tof_valid;
    uint16_t adc[8];
    float cell_v[3], vsys_v, cell_temp_c[3];
    uint8_t mode, flags;
    bool recording, power_off;
    uint32_t pwr_down_ms;
    bool btn_last[BTN_COUNT];
    uint8_t btn_cnt[BTN_COUNT];
    uint32_t still_ticks;
    bool sensors_ok[5];          /* imu, mag, baro, tof, adc */
    bool servo_follow;           /* servo 1 follows pitch (stabiliser demo) */
    telemetry_t last;
} app_t;

void app_init(app_t *a);
/* call at HUB_RATE_HZ */
void app_tick(app_t *a);
#endif
