/* Live simulator back end: the real hub code and the sensor models of sim.c, stepped in lock-step over
 * stdin / stdout by fcl_sim.py (which owns the clock, the scenario and the USB side).
 *
 * One request line per step:
 *     S <ticks> <heading> <pitch> <roll> <alt_m> <dist_mm> <c1_v> <c2_v> <c3_v> <t1_c> <t2_c> <t3_c> <buttons> <hex|->
 *   ticks    hub ticks to run (200 per second); the truth moves linearly to the given values over the step
 *   buttons  bit 0 power, bit 1 B1, bit 2 B2
 *   hex      bytes for the hub from the ESP32 side of the link, "-" for none
 * Two reply lines:
 *     R <hex|-> <servo1..6 us> <led0> <led1> <power_hold> <dot_x> <dot_y> <dot_on>
 *     O <row 0>|<row 1>|...        overlay text, spaces as '_'
 */
#define SIM_LIVE
#include "sim.c"

static int hexval(int c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }

int main(void)
{
    static app_t a;
    static char line[8192];
    long k = 0;
    (void)wrap; (void)esp_send;
    live_b = (truth_t){ 0, 0, 0, 0, 1500, { 3.9f, 3.9f, 3.9f }, { 25, 25, 25 } };
    live_a = live_b;
    link_parser_init(&esp);
    app_init(&a);
    setvbuf(stdout, NULL, _IOLBF, 0);
    while (fgets(line, sizeof line, stdin))
    {
        int n, btn, pos = 0;
        truth_t t;
        if (line[0] != 'S')
            continue;
        if (sscanf(line + 1, "%d %f %f %f %f %f %f %f %f %f %f %f %d %n", &n, &t.hd, &t.pt, &t.rl, &t.alt, &t.tof_mm,
                   &t.cell[0], &t.cell[1], &t.cell[2], &t.temp[0], &t.temp[1], &t.temp[2], &btn, &pos) < 13)
            continue;
        const char *h = line + 1 + pos;
        for (; h[0] && h[1] && h[0] != '-' && h[0] != '\n' && h[0] != '\r'; h += 2)
            if (rxn < sizeof rxq)
                rxq[rxn++] = (uint8_t)(hexval(h[0]) << 4 | hexval(h[1]));
        live_a = live_b;
        live_b = t;
        live_btn = btn;
        live_t0 = now_s;
        live_t1 = now_s + n / (double)HUB_RATE_HZ;
        live_txn = 0;
        for (int i = 0; i < n; i++)
        {
            now_s = ++k / (double)HUB_RATE_HZ;
            app_tick(&a);
        }
        printf("R ");
        if (!live_txn) printf("-");
        for (size_t i = 0; i < live_txn; i++) printf("%02x", live_tx[i]);
        printf(" %u %u %u %u %u %u %d %d %d %d %d %d\nO ", servo[0], servo[1], servo[2], servo[3], servo[4], servo[5],
               led[0], led[1], power_hold, osd_x, osd_y, osd_on);
        for (int r = 0; r < OSD_ROWS; r++)
        {
            for (int c = 0; c < OSD_COLS; c++) putchar(osd[r][c] == ' ' || !osd[r][c] ? '_' : osd[r][c]);
            putchar(r + 1 < OSD_ROWS ? '|' : '\n');
        }
        fflush(stdout);
    }
    return 0;
}
