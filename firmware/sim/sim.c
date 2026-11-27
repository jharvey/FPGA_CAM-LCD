/* Host simulator for the FCL sensor hub.
 *
 * Runs the real hub code (common/) against register-level models of the ICM-42688-P, LIS2MDL, LPS22DF,
 * VL53L1X and AD7689, driven by a scripted 32 s scenario: still, then turning and tilting, climbing 3 m,
 * a cell running down, button presses, a command from the ESP32, and a long press on the power button.
 * The ESP32 side of the link is played by a frame parser here.
 *
 *     make -C firmware/sim && ./firmware/sim/fcl_sim out.csv      (exit code 0 = all checks pass)
 */
#include "../common/app.h"
#include "../common/board.h"
#include "../common/hal.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PI 3.14159265358979f
#define D2R (PI / 180.0f)

/* ---------------------------------------------------------------- truth */
static double now_s;                                    /* simulation time */

typedef struct { float hd, pt, rl, alt, tof_mm, cell[3], temp[3]; } truth_t;

static truth_t truth(double t)
{
    truth_t s;
    double u = t < 2 ? 0 : (t > 22 ? 20 : t - 2);
    s.hd = (float)fmod(30.0 + 18.0 * u, 360.0);
    s.pt = (float)(20.0 * sin(2 * PI * u / 8.0));
    s.rl = (float)(10.0 * sin(2 * PI * u / 5.0));
    s.alt = (float)(t < 10 ? 0 : t > 14 ? 3.0 : 3.0 * (t - 10) / 4.0);
    s.tof_mm = (float)(1500 + 500 * sin(2 * PI * t / 10.0));
    s.cell[0] = 3.95f; s.cell[1] = 3.90f;
    s.cell[2] = (float)(3.62 - 0.01 * t);
    s.temp[0] = 25; s.temp[1] = 26; s.temp[2] = (float)(27 + 0.2 * t);
    return s;
}

/* body -> earth rotation; earth x north, y west, z up; body x forward, y left, z up */
static void rot(float hd, float pt, float rl, float R[3][3])
{
    float a = -hd * D2R, b = -pt * D2R, c = rl * D2R;
    float ca = cosf(a), sa = sinf(a), cb = cosf(b), sb = sinf(b), cc = cosf(c), sc = sinf(c);
    float Rz[3][3] = { {ca, -sa, 0}, {sa, ca, 0}, {0, 0, 1} };
    float Ry[3][3] = { {cb, 0, sb}, {0, 1, 0}, {-sb, 0, cb} };
    float Rx[3][3] = { {1, 0, 0}, {0, cc, -sc}, {0, sc, cc} };
    float T[3][3];
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++)
    { T[i][j] = 0; for (int k = 0; k < 3; k++) T[i][j] += Rz[i][k] * Ry[k][j]; }
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++)
    { R[i][j] = 0; for (int k = 0; k < 3; k++) R[i][j] += T[i][k] * Rx[k][j]; }
}

static vec3 to_body(float R[3][3], float x, float y, float z)
{
    vec3 o = { R[0][0] * x + R[1][0] * y + R[2][0] * z, R[0][1] * x + R[1][1] * y + R[2][1] * z,
               R[0][2] * x + R[1][2] * y + R[2][2] * z };
    return o;
}

static unsigned rng = 12345;
static float noise(float sd)
{
    float s = 0;
    for (int i = 0; i < 12; i++) { rng = rng * 1103515245u + 12345u; s += (rng >> 8 & 0xFFFF) / 65536.0f; }
    return (s - 6.0f) * sd;
}

static void imu_truth(vec3 *acc, vec3 *gyr, vec3 *mag)
{
    truth_t s = truth(now_s), s1 = truth(now_s + 0.001), s0 = truth(now_s - 0.001);
    float R[3][3], R1[3][3], R0[3][3];
    rot(s.hd, s.pt, s.rl, R); rot(s1.hd, s1.pt, s1.rl, R1); rot(s0.hd, s0.pt, s0.rl, R0);
    float W[3][3];                                    /* R^T dR/dt = skew(omega_body) */
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++)
    { W[i][j] = 0; for (int k = 0; k < 3; k++) W[i][j] += R[k][i] * (R1[k][j] - R0[k][j]) / 0.002f; }
    const float R2D = 180.0f / PI;
    *gyr = (vec3){ W[2][1] * R2D + 0.4f + noise(0.05f), W[0][2] * R2D - 0.3f + noise(0.05f), W[1][0] * R2D + 0.5f + noise(0.05f) };
    *acc = to_body(R, 0, 0, 1);
    acc->x += noise(0.003f); acc->y += noise(0.003f); acc->z += noise(0.003f);
    *mag = to_body(R, 0.20f, 0, -0.43f);              /* 0.2 G horizontal (north), 0.43 G down */
    mag->x += noise(0.002f); mag->y += noise(0.002f); mag->z += noise(0.002f);
}

/* ---------------------------------------------------------------- device models */
static int16_t clip16(float v) { return (int16_t)(v > 32767 ? 32767 : v < -32768 ? -32768 : lrintf(v)); }
static void put_be(uint8_t *p, int16_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }
static void put_le(uint8_t *p, int16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }

static int dev_read(uint8_t addr, uint16_t reg, uint8_t *d, size_t n)
{
    uint8_t b[16] = {0};
    vec3 a, g, m;
    truth_t s = truth(now_s);
    switch (addr)
    {
    case I2C_ADDR_ICM42688:
        if (reg == 0x75) b[0] = 0x47;
        else if (reg == 0x1D)
        {
            imu_truth(&a, &g, &m);
            put_be(b, clip16((30.0f - 25.0f) * 132.48f));
            put_be(b + 2, clip16(a.x * 8192)); put_be(b + 4, clip16(a.y * 8192)); put_be(b + 6, clip16(a.z * 8192));
            put_be(b + 8, clip16(g.x * 65.5f)); put_be(b + 10, clip16(g.y * 65.5f)); put_be(b + 12, clip16(g.z * 65.5f));
        }
        break;
    case I2C_ADDR_LIS2MDL:
        if (reg == 0x4F) b[0] = 0x40;
        else if (reg == 0x68)
        {
            imu_truth(&a, &g, &m);
            put_le(b, clip16(m.x / 0.0015f)); put_le(b + 2, clip16(m.y / 0.0015f)); put_le(b + 4, clip16(m.z / 0.0015f));
        }
        break;
    case I2C_ADDR_LPS22DF:
        if (reg == 0x0F) b[0] = 0xB4;
        else if (reg == 0x28)
        {
            float p = 1013.25f * powf(1.0f - s.alt / 44330.0f, 5.255f) + noise(0.01f);
            int32_t raw = (int32_t)lrintf(p * 4096);
            b[0] = (uint8_t)raw; b[1] = (uint8_t)(raw >> 8); b[2] = (uint8_t)(raw >> 16);
            put_le(b + 3, clip16(22.5f * 100));
        }
        break;
    case I2C_ADDR_VL53L1X:
    {
        static double last_clear;
        if (reg == 0x010F) b[0] = 0xEA;
        else if (reg == 0x0031) b[0] = (now_s - last_clear >= 0.05) ? 0 : 1;
        else if (reg == 0x0096) { uint16_t mm = (uint16_t)s.tof_mm; b[0] = (uint8_t)(mm >> 8); b[1] = (uint8_t)mm; }
        else if (reg == 0x0086) last_clear = now_s;  /* write path calls this with n = 0 */
        break;
    }
    default:
        return -1;                                    /* NACK */
    }
    memcpy(d, b, n);
    return 0;
}

int hal_i2c_read(uint8_t a, uint8_t r, uint8_t *d, size_t n) { return dev_read(a, r, d, n); }
int hal_i2c_read16(uint8_t a, uint16_t r, uint8_t *d, size_t n) { return dev_read(a, r, d, n); }
int hal_i2c_write(uint8_t a, uint8_t r, const uint8_t *d, size_t n) { (void)r; (void)d; (void)n; uint8_t x; return dev_read(a, 0xFFFF, &x, 0); }
int hal_i2c_write16(uint8_t a, uint16_t r, const uint8_t *d, size_t n) { (void)d; (void)n; uint8_t x; return dev_read(a, r, &x, 0); }

/* AD7689: result of frame k is the conversion configured two frames earlier */
static uint16_t adc_cfg_hist[2];
uint16_t hal_adc_xfer(uint16_t cfg)
{
    uint16_t old = adc_cfg_hist[0];
    adc_cfg_hist[0] = adc_cfg_hist[1];
    adc_cfg_hist[1] = cfg;
    int ch = (old >> 7) & 7;
    truth_t s = truth(now_s);
    float v = 0;
    if (ch <= 2) v = s.cell[ch] / DIV_CELL;
    else if (ch == ADC_CH_REF3025) v = 2.5f;
    else if (ch == ADC_CH_VSYS) v = (s.cell[0] - 0.05f) / DIV_VSYS;
    else
    {
        int i = ch == ADC_CH_NTC1 ? 0 : ch == ADC_CH_NTC2 ? 1 : 2;
        float r = NTC_R25 * expf(NTC_BETA * (1.0f / (s.temp[i] + 273.15f) - 1.0f / 298.15f));
        v = ADC_VREF_V * r / (r + NTC_PULLUP);
    }
    float code = v / ADC_VREF_V * 65536.0f + noise(2.0f);
    return (uint16_t)(code < 0 ? 0 : code > 65535 ? 65535 : code);
}

/* ---------------------------------------------------------------- the rest of the board */
static bool power_hold, led[2];
static uint16_t servo[6];
bool hal_button(btn_t b)
{
    if (b == BTN_1) return now_s >= 5.0 && now_s < 5.2;
    if (b == BTN_2) return now_s >= 6.0 && now_s < 6.3;
    return now_s >= 28.0 && now_s < 31.0;                 /* power: long press */
}
void hal_led(int i, bool on) { led[i & 1] = on; }
void hal_servo_us(int ch, uint16_t us) { if (ch >= 0 && ch < 6) servo[ch] = us; }
void hal_tof_xshut(bool on) { (void)on; }
void hal_power_hold(bool h) { power_hold = h; }
uint32_t hal_millis(void) { return (uint32_t)lrint(now_s * 1000); }
void hal_delay_ms(uint32_t ms) { (void)ms; }

/* the ESP32 end of the link */
static link_parser_t esp;
static telemetry_t esp_last;
static int n_telem, ev_seen[8];
static double ev_time[8];
void hal_link_tx(const uint8_t *d, size_t n)
{
    for (size_t i = 0; i < n; i++)
        if (link_parser_feed(&esp, d[i]))
        {
            if (esp.type == MSG_TELEMETRY && esp.len == TELEMETRY_LEN) { telemetry_unpack(esp.buf, &esp_last); n_telem++; }
            if (esp.type == MSG_EVENT && esp.len == 1 && esp.buf[0] < 8) { if (!ev_seen[esp.buf[0]]) ev_time[esp.buf[0]] = now_s; ev_seen[esp.buf[0]]++; }
        }
}
static uint8_t rxq[64];
static size_t rxn;
int hal_link_rx(uint8_t *d, size_t max)
{
    size_t n = rxn < max ? rxn : max;
    memcpy(d, rxq, n);
    memmove(rxq, rxq + n, rxn - n);
    rxn -= n;
    return (int)n;
}
static void esp_send(uint8_t type, const uint8_t *p, uint8_t len) { rxn += link_frame(type, p, len, rxq + rxn); }

/* ---------------------------------------------------------------- run */
static float wrap(float d) { while (d > 180) d -= 360; while (d < -180) d += 360; return d; }

int main(int argc, char **argv)
{
    FILE *csv = fopen(argc > 1 ? argv[1] : "fcl_sim.csv", "w");
    fprintf(csv, "t,hd_true,hd_est,pt_true,pt_est,rl_true,rl_est,alt_true,alt_est,tof_true,tof_mm,cell3_v,flags,mode,servo1_us,power_hold\n");
    static app_t a;
    link_parser_init(&esp);
    app_init(&a);
    float e_hd = 0, e_pt = 0, e_rl = 0;
    bool sent_mode = false, sent_servo = false;
    uint16_t servo_at_27 = 0;
    for (int k = 1; now_s < 32.0; k++)
    {
        now_s = k / (double)HUB_RATE_HZ;
        if (!sent_mode && now_s >= 15.0) { uint8_t m = 2; esp_send(MSG_CMD_MODE, &m, 1); sent_mode = true; }
        if (!sent_servo && now_s >= 26.0) { uint8_t p[3] = { 0, 1234 & 0xFF, 1234 >> 8 }; esp_send(MSG_CMD_SERVO, p, 3); sent_servo = true; }
        app_tick(&a);
        if (k == 27 * HUB_RATE_HZ) servo_at_27 = servo[0];
        truth_t s = truth(now_s);
        float hd, pt, rl;
        fusion_euler(&a.fus, &hd, &pt, &rl);
        if (now_s >= 4.0 && now_s < 28.0)
        {
            if (fabsf(wrap(hd - s.hd)) > e_hd) e_hd = fabsf(wrap(hd - s.hd));
            if (fabsf(pt - s.pt) > e_pt) e_pt = fabsf(pt - s.pt);
            if (fabsf(rl - s.rl) > e_rl) e_rl = fabsf(rl - s.rl);
        }
        if (k % 4 == 0)
            fprintf(csv, "%.3f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.3f,%.3f,%.0f,%u,%.3f,%u,%u,%u,%d\n", now_s, s.hd, hd, s.pt, pt, s.rl, rl,
                    s.alt, a.alt_m, s.tof_mm, a.tof_mm, a.cell_v[2], a.flags, a.mode, servo[0], power_hold);
    }
    fclose(csv);

    int fail = 0;
#define CHECK(cond, ...) do { int ok_ = (cond); printf("%s  ", ok_ ? "PASS" : "FAIL"); printf(__VA_ARGS__); printf("\n"); fail += !ok_; } while (0)
    CHECK(a.sensors_ok[0] && a.sensors_ok[1] && a.sensors_ok[2] && a.sensors_ok[3], "all sensors found (IMU, compass, barometer, ToF)");
    CHECK(e_hd < 5.0f, "heading error while turning 18 deg/s: max %.2f deg (limit 5)", e_hd);
    CHECK(e_pt < 3.0f && e_rl < 3.0f, "pitch / roll error while tilting: max %.2f / %.2f deg (limit 3)", e_pt, e_rl);
    CHECK(fabsf(esp_last.alt_cm / 100.0f - 3.0f) < 0.3f, "altitude after a 3 m climb: %.2f m", esp_last.alt_cm / 100.0f);
    CHECK(ev_seen[EV_CELL_LOW] == 1, "cell 3 low warning sent once, at %.1f s (cell crosses %.2f V at %.1f s)", ev_time[EV_CELL_LOW], CELL_LOW_MV / 1000.0, (3.62 - CELL_LOW_MV / 1000.0) / 0.01);
    CHECK(ev_seen[EV_B1] == 1 && ev_seen[EV_B2] == 1, "B1 and B2 presses reported");
    CHECK(esp_last.mode == 2 && (esp_last.flags & TF_RECORDING), "mode set to 2 by the ESP32, recording on from B2");
    CHECK(servo_at_27 == 1234, "servo command from the ESP32 applied: %u us", servo_at_27);
    CHECK(servo[0] == 0, "servo released at power-off");
    CHECK(ev_seen[EV_PWR_OFF] == 1 && fabs(ev_time[EV_PWR_OFF] - 30.0) < 0.1, "power-off after holding B0 2 s: event at %.2f s", ev_time[EV_PWR_OFF]);
    CHECK(!power_hold, "power hold released");
    CHECK(esp.bad == 0 && n_telem > 500, "link: %d telemetry frames, %u CRC errors", n_telem, esp.bad);
    printf("%s\n", fail ? "SOME CHECKS FAILED" : "ALL CHECKS PASSED");
    return fail != 0;
}
