#include "link.h"
#include <string.h>

uint16_t crc16_ccitt(const uint8_t *d, size_t n, uint16_t crc)
{
    while (n--)
    {
        crc ^= (uint16_t)(*d++) << 8;
        for (int i = 0; i < 8; i++)
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

size_t link_frame(uint8_t type, const uint8_t *payload, uint8_t len, uint8_t *out)
{
    out[0] = 0xA5; out[1] = 0x5A; out[2] = type; out[3] = len;
    memcpy(out + 4, payload, len);
    uint16_t c = crc16_ccitt(out + 2, (size_t)len + 2, 0xFFFF);
    out[4 + len] = (uint8_t)c;
    out[5 + len] = (uint8_t)(c >> 8);
    return (size_t)len + 6;
}

static uint8_t *put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); return p + 2; }
static uint8_t *put32(uint8_t *p, uint32_t v) { p = put16(p, (uint16_t)v); return put16(p, (uint16_t)(v >> 16)); }
static uint16_t get16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }
static uint32_t get32(const uint8_t *p) { return get16(p) | (uint32_t)get16(p + 2) << 16; }

size_t telemetry_pack(const telemetry_t *t, uint8_t *p0)
{
    uint8_t *p = p0;
    p = put32(p, t->t_ms);
    p = put16(p, (uint16_t)t->heading_cd); p = put16(p, (uint16_t)t->pitch_cd); p = put16(p, (uint16_t)t->roll_cd);
    p = put32(p, (uint32_t)t->alt_cm); p = put32(p, t->press_pa);
    p = put16(p, t->tof_mm);
    for (int i = 0; i < 3; i++) p = put16(p, t->cell_mv[i]);
    p = put16(p, t->vsys_mv);
    for (int i = 0; i < 3; i++) p = put16(p, (uint16_t)t->cell_temp_dc[i]);
    *p++ = t->mode; *p++ = t->flags;
    return (size_t)(p - p0);
}

void telemetry_unpack(const uint8_t *p, telemetry_t *t)
{
    t->t_ms = get32(p); p += 4;
    t->heading_cd = (int16_t)get16(p); t->pitch_cd = (int16_t)get16(p + 2); t->roll_cd = (int16_t)get16(p + 4); p += 6;
    t->alt_cm = (int32_t)get32(p); t->press_pa = get32(p + 4); p += 8;
    t->tof_mm = get16(p); p += 2;
    for (int i = 0; i < 3; i++, p += 2) t->cell_mv[i] = get16(p);
    t->vsys_mv = get16(p); p += 2;
    for (int i = 0; i < 3; i++, p += 2) t->cell_temp_dc[i] = (int16_t)get16(p);
    t->mode = p[0]; t->flags = p[1];
}

void link_parser_init(link_parser_t *p) { memset(p, 0, sizeof *p); }

int link_parser_feed(link_parser_t *p, uint8_t c)
{
    switch (p->state)
    {
    case 0: p->state = (c == 0xA5) ? 1 : 0; break;
    case 1: p->state = (c == 0x5A) ? 2 : (c == 0xA5 ? 1 : 0); break;
    case 2: p->type = c; p->state = 3; break;
    case 3:
        p->len = c; p->n = 0;
        p->state = (c <= LINK_MAX_PAYLOAD) ? (c ? 4 : 5) : 0;
        break;
    case 4: p->buf[p->n++] = c; if (p->n == p->len) p->state = 5; break;
    case 5: p->crc = c; p->state = 6; break;
    case 6:
    {
        p->crc |= (uint16_t)c << 8;
        p->state = 0;
        uint8_t hdr[2] = { p->type, p->len };
        uint16_t calc = crc16_ccitt(p->buf, p->len, crc16_ccitt(hdr, 2, 0xFFFF));
        if (calc == p->crc) { p->good++; return 1; }
        p->bad++;
        break;
    }
    }
    return 0;
}
