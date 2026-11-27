/* FCL board constants for the sensor hub. Sources: imu / peripherals / power sheets, ROADMAP.md (Phases 3, 3d, 3e).
 * Values marked CHECK need confirming against the schematic before first power-up. */
#ifndef FCL_BOARD_H
#define FCL_BOARD_H

/* IMU I2C bus devices */
#define I2C_ADDR_ICM42688   0x68    /* AP_AD0 = GND */
#define I2C_ADDR_LIS2MDL    0x1E
#define I2C_ADDR_LPS22DF    0x5C    /* SA0 = GND */
#define I2C_ADDR_VL53L1X    0x29

/* AD7689 channels (ROADMAP Phase 2): IN0-2 cell dividers 47k/56k, IN3 NTC cell 1, IN4 REF3025, IN5 VSYS 100k/68k.
 * IN6 / IN7: NTCs of cells 2 / 3 (TEMP_BAT_CELL2/3)  -- CHECK */
#define ADC_CH_CELL1        0
#define ADC_CH_CELL2        1
#define ADC_CH_CELL3        2
#define ADC_CH_NTC1         3
#define ADC_CH_REF3025      4
#define ADC_CH_VSYS         5
#define ADC_CH_NTC2         6
#define ADC_CH_NTC3         7
#define ADC_VREF_V          2.5f
#define DIV_CELL            ((47.0f + 56.0f) / 56.0f)     /* 4.2 V -> 2.28 V */
#define DIV_VSYS            ((100.0f + 68.0f) / 68.0f)
#define NTC_R25             10000.0f                      /* 10k NTC, 10k pull-up from VREF_SENSE (2.5 V) */
#define NTC_BETA            3435.0f                       /* CHECK against TH1-3 part */
#define NTC_PULLUP          10000.0f

/* battery policy (ROADMAP: 3.3 V rail needs about 3.4 V on VSYS -> cutoff 3.5-3.6 V on the highest cell) */
#define CELL_LOW_MV         3400
#define CELL_CUTOFF_MV      3200
#define CELL_HOT_DC         550     /* 55.0 C */

/* sensor axes -> device axes (device: x along the lens toward the scene, y left, z up when held level).
 * Identity until checked against the part orientations on the PCB.  CHECK */
#define AXES_IMU            { {1,0,0}, {0,1,0}, {0,0,1} }
#define AXES_MAG            { {1,0,0}, {0,1,0}, {0,0,1} }

/* down dot: the camera picture fills the round LCD; CAM_HFOV_DEG is the angle across the 480 px width.  CHECK with the lens */
#define CAM_HFOV_DEG        40.0f
#define LCD_HALF_PX         240
#define DOT_RIM_PX          226     /* radius of the rim position */

#define HUB_RATE_HZ         200     /* IMU + fusion */
#define MAG_DIV             2       /* magnetometer every 2nd tick (100 Hz) */
#define BARO_DIV            8       /* 25 Hz */
#define TOF_DIV             10      /* 20 Hz */
#define ADC_DIV             40      /* 5 Hz */
#define TELEM_DIV           10      /* 20 Hz to the ESP32 */
#define PWR_LONG_MS         2000    /* hold B0 this long to switch off */
#endif
