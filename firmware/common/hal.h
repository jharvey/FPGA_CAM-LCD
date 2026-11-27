/* Hardware abstraction used by the portable sensor-hub code.
 * Implemented by hub/hal_litex.c (soft CPU in the ECP5) and sim/hal_sim.c (host simulator). */
#ifndef FCL_HAL_H
#define FCL_HAL_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* I2C on the IMU bus (IMU_SCL / IMU_SDA). Return 0 on ACK, <0 on NACK / error. */
int hal_i2c_write(uint8_t addr7, uint8_t reg, const uint8_t *data, size_t len);
int hal_i2c_read(uint8_t addr7, uint8_t reg, uint8_t *data, size_t len);
/* same, 16-bit register address (VL53L1X) */
int hal_i2c_write16(uint8_t addr7, uint16_t reg, const uint8_t *data, size_t len);
int hal_i2c_read16(uint8_t addr7, uint16_t reg, uint8_t *data, size_t len);

/* AD7689: one 16-bit SPI frame (CNV pulse, then DIN out / SDO in) */
uint16_t hal_adc_xfer(uint16_t cfg14);

/* inputs: true = pressed (the hardware lines are active low) */
typedef enum { BTN_PWR = 0, BTN_1 = 1, BTN_2 = 2, BTN_COUNT } btn_t;
bool hal_button(btn_t b);

void hal_led(int idx, bool on);                 /* LED0 / LED1 */
void hal_servo_us(int ch, uint16_t pulse_us);   /* ch 0..5, 0 = off */
void hal_tof_xshut(bool on);                    /* TOF_XSHUT */
void hal_power_hold(bool hold);                 /* false = let the soft-shutdown path cut power */

/* LCD overlay in the FPGA: OSD_ROWS x OSD_COLS characters of 16 x 32 px (text is 0-terminated per row, ' ' = clear)
 * and the down dot at (x, y) px from the screen centre; dot_on false hides it. Called at the telemetry rate. */
#define OSD_COLS 30
#define OSD_ROWS 15
void hal_osd(const char grid[OSD_ROWS][OSD_COLS + 1], int dot_x, int dot_y, bool dot_on);

/* link to the ESP32-S3 (FPGA L1/L2 <-> ESP32 GPIO11/12) */
void hal_link_tx(const uint8_t *data, size_t len);
int  hal_link_rx(uint8_t *data, size_t max);   /* bytes read, 0 if none */

uint32_t hal_millis(void);
void hal_delay_ms(uint32_t ms);
#endif
