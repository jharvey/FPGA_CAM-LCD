/* Framed messages between the FPGA sensor hub and the ESP32-S3 (UART, 921600 8N1 suggested).
 * Frame: 0xA5 0x5A | type | len | payload[len] | crc16 (CCITT-FALSE, little-endian, over type, len, payload). */
#ifndef FCL_LINK_H
#define FCL_LINK_H
#include <stdint.h>
#include <stddef.h>

enum {
    MSG_TELEMETRY = 0x01,   /* hub -> ESP32, 20 Hz */
    MSG_EVENT     = 0x02,   /* hub -> ESP32: button / power events */
    MSG_CMD_SERVO = 0x10,   /* ESP32 -> hub: ch, pulse_us */
    MSG_CMD_MODE  = 0x11,   /* ESP32 -> hub: display mode */
    MSG_CMD_OVERLAY = 0x12, /* ESP32 -> hub: overlay mask (OV_*) */
    MSG_CMD_ZERO_ALT = 0x13,/* ESP32 -> hub: make the present height 0 */
    MSG_CMD_FOLLOW = 0x14,  /* ESP32 -> hub: 1 = servo 1 follows pitch, 0 = off */
};

enum { EV_B1 = 1, EV_B2 = 2, EV_PWR_SHORT = 3, EV_PWR_OFF = 4, EV_CELL_LOW = 5, EV_CELL_CUTOFF = 6 };

/* flags in telemetry */
#define TF_RECORDING   0x01
#define TF_CELL_LOW    0x02
#define TF_CUTOFF      0x04
#define TF_TOF_VALID   0x08
#define TF_HOT         0x10
#define TF_DOT_INSIDE  0x20    /* the down dot is inside the picture (else it sits on the rim, toward down) */

/* overlay items on the LCD */
#define OV_DOT      0x01
#define OV_HEADING  0x02
#define OV_ATTITUDE 0x04
#define OV_BARO     0x08
#define OV_DIST     0x10
#define OV_BATT     0x20
#define OV_ALL      0x3F

#define SOC_NO_CELL 255     /* soc[] value for an empty slot */

typedef struct {
    uint32_t t_ms;
    int16_t heading_cd, pitch_cd, roll_cd;      /* centi-degrees */
    int32_t alt_cm;                             /* relative to power-up */
    uint32_t press_pa;
    uint16_t tof_mm;
    uint16_t cell_mv[3];
    uint16_t vsys_mv;
    int16_t cell_temp_dc[3];                    /* 0.1 C */
    uint8_t mode, flags;
    uint8_t soc[3];                             /* percent, from the rest voltage; SOC_NO_CELL = empty slot */
    uint8_t buttons;                            /* bit 0 power, bit 1 B1, bit 2 B2 (1 = held) */
    int16_t dot_x, dot_y;                       /* down dot, LCD pixels from the screen centre (+x right, +y down) */
    uint8_t overlay;                            /* OV_* mask */
    uint8_t sensors;                            /* bit 0 IMU, 1 compass, 2 barometer, 3 distance, 4 ADC answered */
} telemetry_t;

#define TELEMETRY_LEN 46
#define LINK_MAX_PAYLOAD 64

size_t link_frame(uint8_t type, const uint8_t *payload, uint8_t len, uint8_t *out);
size_t telemetry_pack(const telemetry_t *t, uint8_t *p);
void telemetry_unpack(const uint8_t *p, telemetry_t *t);

typedef struct {
    int state;
    uint8_t type, len, n;
    uint8_t buf[LINK_MAX_PAYLOAD];
    uint16_t crc;
    uint32_t good, bad;
} link_parser_t;

void link_parser_init(link_parser_t *p);
/* feed one byte; returns 1 when a complete, CRC-checked frame is in p->type / p->len / p->buf */
int link_parser_feed(link_parser_t *p, uint8_t c);
uint16_t crc16_ccitt(const uint8_t *d, size_t n, uint16_t crc);
#endif
