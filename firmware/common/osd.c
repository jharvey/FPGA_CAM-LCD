#include "osd.h"
#include <stdio.h>
#include <string.h>

/* The LCD is round: a row only shows the characters inside the circle, so everything is centred.
 * Rows used: 1 heading, 2 REC, 3 pitch / roll, 10 distance, 11 height + pressure, 12 charge, 13 cell temperatures. */
static void centre(char grid[OSD_ROWS][OSD_COLS + 1], int row, const char *s)
{
    int n = (int)strlen(s);
    if (n > OSD_COLS) n = OSD_COLS;
    memcpy(grid[row] + (OSD_COLS - n) / 2, s, (size_t)n);
}

/* signed fixed point with one decimal, e.g. -4.5 from -45 */
static int fix1(char *o, int v10, int plus)
{
    int a = v10 < 0 ? -v10 : v10;
    return sprintf(o, "%s%d.%d", v10 < 0 ? "-" : (plus ? "+" : ""), a / 10, a % 10);
}

static int round10(int v) { return (v + (v < 0 ? -5 : 5)) / 10; }

void osd_compose(const telemetry_t *t, char grid[OSD_ROWS][OSD_COLS + 1])
{
    static const char *const card[8] = { "N", "NE", "E", "SE", "S", "SW", "W", "NW" };
    char s[64], *p;
    for (int r = 0; r < OSD_ROWS; r++) { memset(grid[r], ' ', OSD_COLS); grid[r][OSD_COLS] = 0; }

    if (t->overlay & OV_HEADING)
    {
        int h = (t->heading_cd + 36000) % 36000;             /* centi-degrees, 0..35999 */
        sprintf(s, "%03d %s", ((h + 50) / 100) % 360, card[((h + 2250) / 4500) % 8]);
        centre(grid, 1, s);
    }
    if (t->flags & TF_RECORDING)
        centre(grid, 2, "REC");
    if (t->overlay & OV_ATTITUDE)
    {
        p = s; p += sprintf(p, "P"); p += fix1(p, round10(t->pitch_cd), 1);
        p += sprintf(p, "  R"); fix1(p, round10(t->roll_cd), 1);
        centre(grid, 3, s);
    }
    if (t->overlay & OV_DIST)
    {
        if (t->flags & TF_TOF_VALID) sprintf(s, "D %d.%02dm", t->tof_mm / 1000, (t->tof_mm % 1000) / 10);
        else sprintf(s, "D ---");
        centre(grid, 10, s);
    }
    if (t->overlay & OV_BARO)
    {
        p = s; p += sprintf(p, "ALT "); p += fix1(p, round10((int)t->alt_cm), 1);
        sprintf(p, "m %uhPa", (unsigned)((t->press_pa + 50) / 100));
        centre(grid, 11, s);
    }
    if (t->overlay & OV_BATT)
    {
        p = s;
        for (int i = 0; i < 3; i++)
        {
            if (t->soc[i] == SOC_NO_CELL) p += sprintf(p, "%s--", i ? " " : "");
            else p += sprintf(p, "%s%d%%", i ? " " : "", t->soc[i]);
        }
        if (t->flags & TF_CUTOFF) sprintf(p, " OFF");
        else if (t->flags & TF_CELL_LOW) sprintf(p, " LOW");
        centre(grid, 12, s);
        p = s;
        for (int i = 0; i < 3; i++)
        {
            if (t->soc[i] == SOC_NO_CELL) p += sprintf(p, "%s--", i ? " " : "");
            else p += sprintf(p, "%s%d", i ? " " : "", round10(t->cell_temp_dc[i]));
        }
        sprintf(p, "C%s", (t->flags & TF_HOT) ? " HOT" : "");
        centre(grid, 13, s);
    }
}
