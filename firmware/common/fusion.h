/* Madgwick MARG filter (accel + gyro + magnetometer) -> attitude and heading.
 * Earth frame: x north, y west, z up.  Device frame: see board.h. */
#ifndef FCL_FUSION_H
#define FCL_FUSION_H
#include "sensors.h"

typedef struct {
    float q0, q1, q2, q3;
    float beta;
    vec3 gyro_bias_dps;
    int bias_n;
    vec3 bias_sum;
} fusion_t;

void fusion_init(fusion_t *f);
/* call while the device is still: averages the gyro to estimate its bias */
void fusion_learn_bias(fusion_t *f, vec3 gyr_dps);
void fusion_update(fusion_t *f, vec3 acc_g, vec3 gyr_dps, vec3 mag, int have_mag, float dt);
/* degrees: heading 0..360 (from north, toward east), pitch + nose up, roll + right side down */
void fusion_euler(const fusion_t *f, float *heading, float *pitch, float *roll);
#endif
