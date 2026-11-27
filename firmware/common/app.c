#include "app.h"
#include "board.h"
#include "hal.h"
#include <math.h>
#include <string.h>

#define DT (1.0f / HUB_RATE_HZ)

static void send(uint8_t type, const uint8_t *p, uint8_t n)
{
    uint8_t f[LINK_MAX_PAYLOAD + 6];
    hal_link_tx(f, link_frame(type, p, n, f));
}

static void event(uint8_t ev) { send(MSG_EVENT, &ev, 1); }

void app_init(app_t *a)
{
    memset(a, 0, sizeof *a);
    fusion_init(&a->fus);
    a->fus.beta = 2.0f;                         /* fast convergence first, then 0.1 */
    a->sensors_ok[0] = icm42688_init() == 0;
    a->sensors_ok[1] = lis2mdl_init() == 0;
    a->sensors_ok[2] = lps22df_init() == 0;
    a->sensors_ok[3] = vl53l1x_init() == 0;
    a->sensors_ok[4] = true;
    a->servo_follow = true;
    hal_power_hold(true);
    hal_led(0, true);
}

static float ntc_c(uint16_t code)
{
    float v = code * ADC_VREF_V / 65536.0f;
    if (v <= 0.001f || v >= ADC_VREF_V - 0.001f)
        return -99.0f;
    float r = NTC_PULLUP * v / (ADC_VREF_V - v);
    return 1.0f / (1.0f / 298.15f + logf(r / NTC_R25) / NTC_BETA) - 273.15f;
}

static void battery(app_t *a)
{
    if (ad7689_read_all(a->adc))
        return;
    const int ch[3] = { ADC_CH_CELL1, ADC_CH_CELL2, ADC_CH_CELL3 };
    const int nt[3] = { ADC_CH_NTC1, ADC_CH_NTC2, ADC_CH_NTC3 };
    uint8_t old = a->flags;
    a->flags &= (uint8_t)~(TF_CELL_LOW | TF_CUTOFF | TF_HOT);
    for (int i = 0; i < 3; i++)
    {
        a->cell_v[i] = a->adc[ch[i]] * ADC_VREF_V / 65536.0f * DIV_CELL;
        a->cell_temp_c[i] = ntc_c(a->adc[nt[i]]);
        int mv = (int)(a->cell_v[i] * 1000);
        if (mv > 2500 && mv < CELL_LOW_MV) a->flags |= TF_CELL_LOW;      /* < 2.5 V: slot empty */
        if (mv > 2500 && mv < CELL_CUTOFF_MV) a->flags |= TF_CUTOFF;
        if (a->cell_temp_c[i] * 10 > CELL_HOT_DC) a->flags |= TF_HOT;
    }
    a->vsys_v = a->adc[ADC_CH_VSYS] * ADC_VREF_V / 65536.0f * DIV_VSYS;
    if ((a->flags & TF_CELL_LOW) && !(old & TF_CELL_LOW)) event(EV_CELL_LOW);
    if ((a->flags & TF_CUTOFF) && !(old & TF_CUTOFF)) event(EV_CELL_CUTOFF);
}

/* 4-sample debounce at 200 Hz (20 ms) */
static void buttons(app_t *a)
{
    for (int b = 0; b < BTN_COUNT; b++)
    {
        bool raw = hal_button((btn_t)b);
        if (raw != a->btn_last[b]) { if (++a->btn_cnt[b] >= 4) { a->btn_last[b] = raw; a->btn_cnt[b] = 0;
            if (b == BTN_PWR) { if (raw) a->pwr_down_ms = hal_millis(); else if (!a->power_off) event(EV_PWR_SHORT); }
            if (b == BTN_1 && raw) { a->mode = (uint8_t)((a->mode + 1) % 4); event(EV_B1); }
            if (b == BTN_2 && raw) { a->recording = !a->recording; event(EV_B2); }
        } }
        else a->btn_cnt[b] = 0;
    }
    if (a->btn_last[BTN_PWR] && !a->power_off && hal_millis() - a->pwr_down_ms >= PWR_LONG_MS)
    {
        a->power_off = true;
        event(EV_PWR_OFF);
    }
}

static void commands(app_t *a)
{
    static link_parser_t lp;
    static int init;
    uint8_t buf[32];
    int n;
    if (!init) { link_parser_init(&lp); init = 1; }
    while ((n = hal_link_rx(buf, sizeof buf)) > 0)
        for (int i = 0; i < n; i++)
            if (link_parser_feed(&lp, buf[i]))
            {
                if (lp.type == MSG_CMD_SERVO && lp.len == 3)
                {
                    a->servo_follow = false;
                    hal_servo_us(lp.buf[0], (uint16_t)(lp.buf[1] | lp.buf[2] << 8));
                }
                else if (lp.type == MSG_CMD_MODE && lp.len == 1)
                    a->mode = lp.buf[0];
            }
}

void app_tick(app_t *a)
{
    a->tick++;
    if (a->power_off)
    {
        hal_servo_us(0, 0);
        hal_led(0, false);
        hal_power_hold(false);                  /* the soft-shutdown path removes power */
        return;
    }
    int have_mag = 0;
    if (a->sensors_ok[0] && icm42688_read(&a->acc, &a->gyr, &a->imu_temp_c) == 0)
    {
        if (a->sensors_ok[1] && a->tick % MAG_DIV == 0)
            have_mag = lis2mdl_read(&a->mag) == 0;
        /* still at power-up: learn the gyro bias for the first second */
        float gm = fabsf(a->gyr.x) + fabsf(a->gyr.y) + fabsf(a->gyr.z);
        if (a->tick <= HUB_RATE_HZ && gm < 5.0f)
            fusion_learn_bias(&a->fus, a->gyr);
        if (a->tick == 2 * HUB_RATE_HZ)
            a->fus.beta = 0.1f;
        fusion_update(&a->fus, a->acc, a->gyr, a->mag, have_mag || a->sensors_ok[1], DT);
    }
    if (a->sensors_ok[2] && a->tick % BARO_DIV == 0 && lps22df_read(&a->p_hpa, &a->baro_t_c) == 0)
    {
        static int n0;
        if (n0 < 16)                             /* reference = mean pressure over the first 16 readings (0.64 s) */
        {
            a->p0_hpa = (a->p0_hpa * n0 + a->p_hpa) / (n0 + 1);
            n0++;
        }
        float alt = baro_altitude_m(a->p_hpa, a->p0_hpa);
        a->alt_m += 0.2f * (alt - a->alt_m);    /* light low-pass */
    }
    if (a->sensors_ok[3] && a->tick % TOF_DIV == 0)
    {
        bool fresh;
        uint16_t mm;
        if (vl53l1x_read(&mm, &fresh) == 0 && fresh) { a->tof_mm = mm; a->tof_valid = mm > 0 && mm < 4000; }
    }
    if (a->tick % ADC_DIV == 0)
        battery(a);
    buttons(a);
    commands(a);

    float hd, pt, rl;
    fusion_euler(&a->fus, &hd, &pt, &rl);
    if (a->servo_follow)                         /* demo: servo 1 holds the camera level (1500 us +- 10 us / deg) */
    {
        float us = 1500.0f - 10.0f * pt;
        if (us < 1000) us = 1000;
        if (us > 2000) us = 2000;
        hal_servo_us(0, (uint16_t)us);
    }
    hal_led(1, (a->flags & TF_CELL_LOW) ? (a->tick / 50) % 2 : a->recording);

    if (a->tick % TELEM_DIV == 0)
    {
        telemetry_t t = {0};
        t.t_ms = hal_millis();
        t.heading_cd = (int16_t)lrintf(hd * 100 > 32767 ? hd * 100 - 36000 : hd * 100);
        t.pitch_cd = (int16_t)lrintf(pt * 100);
        t.roll_cd = (int16_t)lrintf(rl * 100);
        t.alt_cm = (int32_t)lrintf(a->alt_m * 100);
        t.press_pa = (uint32_t)lrintf(a->p_hpa * 100);
        t.tof_mm = a->tof_mm;
        for (int i = 0; i < 3; i++)
        {
            t.cell_mv[i] = (uint16_t)lrintf(a->cell_v[i] * 1000);
            t.cell_temp_dc[i] = (int16_t)lrintf(a->cell_temp_c[i] * 10);
        }
        t.vsys_mv = (uint16_t)lrintf(a->vsys_v * 1000);
        t.mode = a->mode;
        t.flags = (uint8_t)(a->flags | (a->recording ? TF_RECORDING : 0) | (a->tof_valid ? TF_TOF_VALID : 0));
        uint8_t p[TELEMETRY_LEN];
        send(MSG_TELEMETRY, p, (uint8_t)telemetry_pack(&t, p));
        a->last = t;
    }
}
