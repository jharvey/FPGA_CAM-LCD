/* HAL for the sensor hub running on a soft RISC-V CPU (VexRiscv) in the ECP5, built with LiteX.  DRAFT, not built.
 *
 * Pins: fcl_hub_pins.lpf (generated from the routed board, 2026-11-27).  Assumed LiteX SoC cores (names as they
 * appear in the generated csr.h):
 *   i2c0     LiteX I2C bit-bang core on i2c_scl P16 / i2c_sda K17 (IMU_SCL / IMU_SDA)
 *   adc      LiteX SPIMaster, 16 bits: adc_sck D1, adc_din E1, adc_sdo C1; adc_cnv B1 as its chip select
 *   gpio_in  bit 0 btn_pwr_n D6, bit 1 btn1_n N5, bit 2 btn2_n M5      active low
 *   gpio_out bit 0 led0 B2, bit 1 led1 C2, bit 2 tof_xshut N16, bit 3 shutdown D11 (high = switch off)
 *   pwm0..5  LiteX PWM on srv_pwm1..6 (C18, D17, D16, D15, D14, D13), period 20 ms
 *   uart_esp second UART: rx esp_rx L1 (WIFI_TXD), tx esp_tx L2 (WIFI_RXD)
 *   timer0   1 kHz tick for hal_millis
 * The camera-to-TFT design also uses D6 (as its reset), B2 and C2: give them to one design or the other when merging.
 */
#include "../common/hal.h"
#include <generated/csr.h>
#include <system.h>

/* ---------------------------------------------------------------- I2C bit-bang */
#define SCL 0x01
#define OE  0x02
#define SDA 0x04
static void w(int scl, int sda) { i2c0_w_write((scl ? SCL : 0) | (sda ? 0 : OE)); busy_wait_us(2); }  /* open drain */
static int  r(void) { return i2c0_r_read() & 1; }
static void start(void) { w(1, 1); w(1, 0); w(0, 0); }
static void stop(void)  { w(0, 0); w(1, 0); w(1, 1); }
static int tx(uint8_t b)
{
    for (int i = 7; i >= 0; i--) { int d = (b >> i) & 1; w(0, d); w(1, d); w(0, d); }
    w(0, 1); w(1, 1);
    int nack = r();
    w(0, 1);
    return nack;
}
static uint8_t rx(int ack)
{
    uint8_t b = 0;
    for (int i = 0; i < 8; i++) { w(0, 1); w(1, 1); b = (uint8_t)(b << 1 | r()); }
    w(0, !ack); w(1, !ack); w(0, 1);
    return b;
}
static int xfer(uint8_t a, const uint8_t *reg, int rn, const uint8_t *wd, size_t wn, uint8_t *rd, size_t n)
{
    start();
    if (tx((uint8_t)(a << 1))) { stop(); return -1; }
    for (int i = 0; i < rn; i++) tx(reg[i]);
    for (size_t i = 0; i < wn; i++) tx(wd[i]);
    if (rd)
    {
        start();
        if (tx((uint8_t)(a << 1 | 1))) { stop(); return -1; }
        for (size_t i = 0; i < n; i++) rd[i] = rx(i + 1 < n);
    }
    stop();
    return 0;
}
int hal_i2c_write(uint8_t a, uint8_t reg, const uint8_t *d, size_t n) { return xfer(a, &reg, 1, d, n, 0, 0); }
int hal_i2c_read(uint8_t a, uint8_t reg, uint8_t *d, size_t n) { return xfer(a, &reg, 1, 0, 0, d, n); }
int hal_i2c_write16(uint8_t a, uint16_t reg, const uint8_t *d, size_t n) { uint8_t r2[2] = { (uint8_t)(reg >> 8), (uint8_t)reg }; return xfer(a, r2, 2, d, n, 0, 0); }
int hal_i2c_read16(uint8_t a, uint16_t reg, uint8_t *d, size_t n) { uint8_t r2[2] = { (uint8_t)(reg >> 8), (uint8_t)reg }; return xfer(a, r2, 2, 0, 0, d, n); }

/* ---------------------------------------------------------------- ADC: CNV high >= 4 us (conversion), then 16 clocks */
uint16_t hal_adc_xfer(uint16_t cfg14)
{
    adc_cs_write(0);                         /* CNV high while idle (inverted chip select) -> conversion */
    busy_wait_us(4);
    adc_mosi_write((uint32_t)cfg14 << 2);    /* 14 config bits, MSB first, in a 16-bit frame */
    adc_cs_write(1);
    adc_control_write(16 << 8 | 1);          /* length 16, start */
    while (!(adc_status_read() & 1)) {}
    adc_cs_write(0);
    return (uint16_t)adc_miso_read();
}

/* ---------------------------------------------------------------- simple I/O */
bool hal_button(btn_t b) { return !((gpio_in_in_read() >> b) & 1); }
static uint32_t outs;
static void out(int bit, bool on) { outs = on ? (outs | 1u << bit) : (outs & ~(1u << bit)); gpio_out_out_write(outs); }
void hal_led(int i, bool on) { out(i & 1, on); }
void hal_tof_xshut(bool on) { out(2, on); }
void hal_power_hold(bool h) { out(3, !h); }     /* SHUTDOWN: high = the soft-shutdown path cuts power */
void hal_servo_us(int ch, uint16_t us)       /* pwm width in system clocks; 0 = off */
{
    uint32_t w = (uint32_t)us * (CONFIG_CLOCK_FREQUENCY / 1000000);
    switch (ch)
    {
    case 0: pwm0_width_write(w); break;
    case 1: pwm1_width_write(w); break;
    case 2: pwm2_width_write(w); break;
    case 3: pwm3_width_write(w); break;
    case 4: pwm4_width_write(w); break;
    case 5: pwm5_width_write(w); break;
    }
}

/* ---------------------------------------------------------------- link UART */
void hal_link_tx(const uint8_t *d, size_t n)
{
    while (n--) { while (uart_esp_txfull_read()) {} uart_esp_rxtx_write(*d++); }
}
int hal_link_rx(uint8_t *d, size_t max)
{
    size_t n = 0;
    while (n < max && !uart_esp_rxempty_read()) { d[n++] = (uint8_t)uart_esp_rxtx_read(); uart_esp_ev_pending_write(2); }
    return (int)n;
}

/* ---------------------------------------------------------------- time */
static volatile uint32_t ms;
void hub_timer_isr(void) { ms++; timer0_ev_pending_write(1); }
uint32_t hal_millis(void) { return ms; }
void hal_delay_ms(uint32_t d) { uint32_t t = ms; while (ms - t < d) {} }
