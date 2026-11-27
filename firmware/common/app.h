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
    uint8_t overlay;             /* OV_* mask */
    float soc_f[3];              /* filtered state of charge, percent; < 0 = no cell */
    bool zero_alt;               /* request: make the present height 0 */
    float alt_zero;              /* height (from power-up) that reads as 0 */
    telemetry_t last;
} app_t;

void app_init(app_t *a);
/* state of charge of one Li-ion cell from its rest voltage, percent (SOC_NO_CELL below 2.5 V) */
uint8_t soc_from_mv(int mv);
/* where 'straight down' appears on the LCD for a pitch / roll in degrees. Returns true when it is inside the picture;
 * otherwise (x, y) is on the rim in the direction of down. Pixels from the screen centre, +x right, +y down. */
bool down_dot(float pitch_deg, float roll_deg, int *x, int *y);
/* call at HUB_RATE_HZ */
void app_tick(app_t *a);
#endif
