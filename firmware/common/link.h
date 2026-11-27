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
    MSG_CMD_MODE  = 0x11,   /* ESP32 -> hub: overlay mode */
};

enum { EV_B1 = 1, EV_B2 = 2, EV_PWR_SHORT = 3, EV_PWR_OFF = 4, EV_CELL_LOW = 5, EV_CELL_CUTOFF = 6 };

/* flags in telemetry */
#define TF_RECORDING   0x01
#define TF_CELL_LOW    0x02
#define TF_CUTOFF      0x04
#define TF_TOF_VALID   0x08
#define TF_HOT         0x10

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
} telemetry_t;

#define TELEMETRY_LEN 36
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
