#include "fusion.h"
#include <math.h>

#define DEG2RAD 0.017453292519943295f
#define RAD2DEG 57.29577951308232f

void fusion_init(fusion_t *f)
{
    f->q0 = 1.0f; f->q1 = f->q2 = f->q3 = 0.0f;
    f->beta = 0.1f;
    f->gyro_bias_dps = (vec3){0, 0, 0};
    f->bias_sum = (vec3){0, 0, 0};
    f->bias_n = 0;
}

void fusion_learn_bias(fusion_t *f, vec3 g)
{
    f->bias_sum.x += g.x; f->bias_sum.y += g.y; f->bias_sum.z += g.z;
    f->bias_n++;
    f->gyro_bias_dps = (vec3){ f->bias_sum.x / f->bias_n, f->bias_sum.y / f->bias_n, f->bias_sum.z / f->bias_n };
}

static float inv_sqrt(float x) { return 1.0f / sqrtf(x); }

/* Madgwick, "An efficient orientation filter for inertial and inertial/magnetic sensor arrays" (2010) */
void fusion_update(fusion_t *f, vec3 a, vec3 g, vec3 m, int have_mag, float dt)
{
    float q0 = f->q0, q1 = f->q1, q2 = f->q2, q3 = f->q3;
    float gx = (g.x - f->gyro_bias_dps.x) * DEG2RAD;
    float gy = (g.y - f->gyro_bias_dps.y) * DEG2RAD;
    float gz = (g.z - f->gyro_bias_dps.z) * DEG2RAD;
    float qd0 = 0.5f * (-q1 * gx - q2 * gy - q3 * gz);
    float qd1 = 0.5f * (q0 * gx + q2 * gz - q3 * gy);
    float qd2 = 0.5f * (q0 * gy - q1 * gz + q3 * gx);
    float qd3 = 0.5f * (q0 * gz + q1 * gy - q2 * gx);

    float an = a.x * a.x + a.y * a.y + a.z * a.z;
    if (an > 0.0f)
    {
        float r = inv_sqrt(an);
        float ax = a.x * r, ay = a.y * r, az = a.z * r;
        float s0, s1, s2, s3;
        float mn = m.x * m.x + m.y * m.y + m.z * m.z;
        if (have_mag && mn > 0.0f)
        {
            r = inv_sqrt(mn);
            float mx = m.x * r, my = m.y * r, mz = m.z * r;
            float _2q0mx = 2 * q0 * mx, _2q0my = 2 * q0 * my, _2q0mz = 2 * q0 * mz, _2q1mx = 2 * q1 * mx;
            float _2q0 = 2 * q0, _2q1 = 2 * q1, _2q2 = 2 * q2, _2q3 = 2 * q3;
            float _2q0q2 = 2 * q0 * q2, _2q2q3 = 2 * q2 * q3;
            float q0q0 = q0 * q0, q0q1 = q0 * q1, q0q2 = q0 * q2, q0q3 = q0 * q3, q1q1 = q1 * q1, q1q2 = q1 * q2;
            float q1q3 = q1 * q3, q2q2 = q2 * q2, q2q3 = q2 * q3, q3q3 = q3 * q3;
            float hx = mx * q0q0 - _2q0my * q3 + _2q0mz * q2 + mx * q1q1 + _2q1 * my * q2 + _2q1 * mz * q3 - mx * q2q2 - mx * q3q3;
            float hy = _2q0mx * q3 + my * q0q0 - _2q0mz * q1 + _2q1mx * q2 - my * q1q1 + my * q2q2 + _2q2 * mz * q3 - my * q3q3;
            float _2bx = sqrtf(hx * hx + hy * hy);
            float _2bz = -_2q0mx * q2 + _2q0my * q1 + mz * q0q0 + _2q1mx * q3 - mz * q1q1 + _2q2 * my * q3 - mz * q2q2 + mz * q3q3;
            float _4bx = 2 * _2bx, _4bz = 2 * _2bz;
            s0 = -_2q2 * (2 * q1q3 - _2q0q2 - ax) + _2q1 * (2 * q0q1 + _2q2q3 - ay)
                 - _2bz * q2 * (_2bx * (0.5f - q2q2 - q3q3) + _2bz * (q1q3 - q0q2) - mx)
                 + (-_2bx * q3 + _2bz * q1) * (_2bx * (q1q2 - q0q3) + _2bz * (q0q1 + q2q3) - my)
                 + _2bx * q2 * (_2bx * (q0q2 + q1q3) + _2bz * (0.5f - q1q1 - q2q2) - mz);
            s1 = _2q3 * (2 * q1q3 - _2q0q2 - ax) + _2q0 * (2 * q0q1 + _2q2q3 - ay) - 4 * q1 * (1 - 2 * q1q1 - 2 * q2q2 - az)
                 + _2bz * q3 * (_2bx * (0.5f - q2q2 - q3q3) + _2bz * (q1q3 - q0q2) - mx)
                 + (_2bx * q2 + _2bz * q0) * (_2bx * (q1q2 - q0q3) + _2bz * (q0q1 + q2q3) - my)
                 + (_2bx * q3 - _4bz * q1) * (_2bx * (q0q2 + q1q3) + _2bz * (0.5f - q1q1 - q2q2) - mz);
            s2 = -_2q0 * (2 * q1q3 - _2q0q2 - ax) + _2q3 * (2 * q0q1 + _2q2q3 - ay) - 4 * q2 * (1 - 2 * q1q1 - 2 * q2q2 - az)
                 + (-_4bx * q2 - _2bz * q0) * (_2bx * (0.5f - q2q2 - q3q3) + _2bz * (q1q3 - q0q2) - mx)
                 + (_2bx * q1 + _2bz * q3) * (_2bx * (q1q2 - q0q3) + _2bz * (q0q1 + q2q3) - my)
                 + (_2bx * q0 - _4bz * q2) * (_2bx * (q0q2 + q1q3) + _2bz * (0.5f - q1q1 - q2q2) - mz);
            s3 = _2q1 * (2 * q1q3 - _2q0q2 - ax) + _2q2 * (2 * q0q1 + _2q2q3 - ay)
                 + (-_4bx * q3 + _2bz * q1) * (_2bx * (0.5f - q2q2 - q3q3) + _2bz * (q1q3 - q0q2) - mx)
                 + (-_2bx * q0 + _2bz * q2) * (_2bx * (q1q2 - q0q3) + _2bz * (q0q1 + q2q3) - my)
                 + _2bx * q1 * (_2bx * (q0q2 + q1q3) + _2bz * (0.5f - q1q1 - q2q2) - mz);
        }
        else
        {
            float _2q0 = 2 * q0, _2q1 = 2 * q1, _2q2 = 2 * q2, _2q3 = 2 * q3, _4q0 = 4 * q0, _4q1 = 4 * q1, _4q2 = 4 * q2;
            float _8q1 = 8 * q1, _8q2 = 8 * q2, q0q0 = q0 * q0, q1q1 = q1 * q1, q2q2 = q2 * q2, q3q3 = q3 * q3;
            s0 = _4q0 * q2q2 + _2q2 * ax + _4q0 * q1q1 - _2q1 * ay;
            s1 = _4q1 * q3q3 - _2q3 * ax + 4 * q0q0 * q1 - _2q0 * ay - _4q1 + _8q1 * q1q1 + _8q1 * q2q2 + _4q1 * az;
            s2 = 4 * q0q0 * q2 + _2q0 * ax + _4q2 * q3q3 - _2q3 * ay - _4q2 + _8q2 * q1q1 + _8q2 * q2q2 + _4q2 * az;
            s3 = 4 * q1q1 * q3 - _2q1 * ax + 4 * q2q2 * q3 - _2q2 * ay;
        }
        float sn = s0 * s0 + s1 * s1 + s2 * s2 + s3 * s3;
        if (sn > 0.0f)
        {
            r = inv_sqrt(sn);
            qd0 -= f->beta * s0 * r; qd1 -= f->beta * s1 * r; qd2 -= f->beta * s2 * r; qd3 -= f->beta * s3 * r;
        }
    }
    q0 += qd0 * dt; q1 += qd1 * dt; q2 += qd2 * dt; q3 += qd3 * dt;
    float r = inv_sqrt(q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3);
    f->q0 = q0 * r; f->q1 = q1 * r; f->q2 = q2 * r; f->q3 = q3 * r;
}

void fusion_euler(const fusion_t *f, float *heading, float *pitch, float *roll)
{
    float q0 = f->q0, q1 = f->q1, q2 = f->q2, q3 = f->q3;
    float yaw = atan2f(2 * (q1 * q2 + q0 * q3), q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3) * RAD2DEG;  /* + toward west */
    float sp = -2 * (q1 * q3 - q0 * q2);
    if (sp > 1) sp = 1;
    if (sp < -1) sp = -1;
    float hd = -yaw;                                         /* compass heading: + toward east */
    while (hd < 0) hd += 360;
    while (hd >= 360) hd -= 360;
    *heading = hd;
    *pitch = -asinf(sp) * RAD2DEG;                           /* nose up = + */
    *roll = atan2f(2 * (q0 * q1 + q2 * q3), q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3) * RAD2DEG;
}
