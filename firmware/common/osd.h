/* Text of the LCD overlay, built from one telemetry record. Pure function: the simulator, the PC preview
 * (tools/fcl_osd.py has the same layout in Python) and the FPGA all show the same grid. */
#ifndef FCL_OSD_H
#define FCL_OSD_H
#include "hal.h"
#include "link.h"

void osd_compose(const telemetry_t *t, char grid[OSD_ROWS][OSD_COLS + 1]);
#endif
