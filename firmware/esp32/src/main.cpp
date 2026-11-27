/* FCL ESP32-S3 firmware draft.
 *
 *  - UART link to the FPGA sensor hub: TX GPIO11 -> FPGA L1, RX GPIO12 <- FPGA L2 (fpga/ESP32_PINS.md), framed
 *    messages from common/link.h
 *  - Wi-Fi access point "FCL-xxxx" with a live status page (heading, tilt, altitude, distance, cells) and
 *    controls for the servo and the overlay mode
 *  - microSD (SDMMC 4-bit) CSV log of the telemetry while recording (toggled with B2)
 *  - I2S speaker beeps (MAX98357A) for button presses, low cell and power-off
 *
 * Pins from fpga/ESP32_PINS.md. Untested on hardware.
 */
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <SD_MMC.h>
#include <driver/i2s.h>
extern "C" {
#include "link.h"
}

/* ---- pins */
static const int PIN_LINK_TX = 11, PIN_LINK_RX = 12;
static const int PIN_SD_CLK = 15, PIN_SD_CMD = 7, PIN_SD_D0 = 16, PIN_SD_D1 = 17, PIN_SD_D2 = 5, PIN_SD_D3 = 6;
static const int PIN_I2S_BCLK = 35, PIN_I2S_WS = 36, PIN_I2S_DOUT = 37, PIN_I2S_DIN = 38, PIN_AMP_SD = 47;
static const uint32_t LINK_BAUD = 921600;

static HardwareSerial Link(1);
static WebServer web(80);
static link_parser_t parser;
static telemetry_t tel;
static uint32_t tel_count, tel_ms;
static bool sd_ok;
static File logfile;

/* ---------------------------------------------------------------- link */
static void link_send(uint8_t type, const uint8_t *p, uint8_t n)
{
    uint8_t f[LINK_MAX_PAYLOAD + 6];
    Link.write(f, link_frame(type, p, n, f));
}

/* ---------------------------------------------------------------- audio */
static void audio_init()
{
    pinMode(PIN_AMP_SD, OUTPUT);
    digitalWrite(PIN_AMP_SD, LOW);
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
    cfg.sample_rate = 16000;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
    cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.dma_buf_count = 4;
    cfg.dma_buf_len = 256;
    i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr);
    i2s_pin_config_t pins = {};
    pins.mck_io_num = I2S_PIN_NO_CHANGE;
    pins.bck_io_num = PIN_I2S_BCLK;
    pins.ws_io_num = PIN_I2S_WS;
    pins.data_out_num = PIN_I2S_DOUT;
    pins.data_in_num = PIN_I2S_DIN;          /* ICS-43434 microphone, not used yet */
    i2s_set_pin(I2S_NUM_0, &pins);
}

static void beep(int hz, int ms, int count = 1)
{
    digitalWrite(PIN_AMP_SD, HIGH);
    static int16_t buf[2 * 256];
    for (int c = 0; c < count; c++)
    {
        int n = 16000 * ms / 1000;
        for (int i = 0; i < n; i += 256)
        {
            for (int k = 0; k < 256; k++)
            {
                int16_t v = (int16_t)(4000 * sinf(2 * PI * hz * (i + k) / 16000.0f));
                buf[2 * k] = buf[2 * k + 1] = v;
            }
            size_t w;
            i2s_write(I2S_NUM_0, buf, sizeof buf, &w, portMAX_DELAY);
        }
        i2s_zero_dma_buffer(I2S_NUM_0);
        delay(80);
    }
    digitalWrite(PIN_AMP_SD, LOW);
}

/* ---------------------------------------------------------------- SD log */
static void sd_init()
{
    SD_MMC.setPins(PIN_SD_CLK, PIN_SD_CMD, PIN_SD_D0, PIN_SD_D1, PIN_SD_D2, PIN_SD_D3);
    sd_ok = SD_MMC.begin("/sdcard", false);
    Serial.printf("SD: %s\n", sd_ok ? "mounted" : "not found");
}

static void sd_log(const telemetry_t &t)
{
    bool rec = t.flags & TF_RECORDING;
    if (!sd_ok)
        return;
    if (rec && !logfile)
    {
        char name[32];
        snprintf(name, sizeof name, "/fcl_%lu.csv", (unsigned long)t.t_ms);
        logfile = SD_MMC.open(name, FILE_WRITE);
        if (logfile)
            logfile.println("t_ms,heading,pitch,roll,alt_m,press_pa,tof_mm,cell1,cell2,cell3,vsys,temp1,temp2,temp3,flags");
    }
    if (!rec && logfile)
        logfile.close();
    if (logfile)
        logfile.printf("%lu,%.2f,%.2f,%.2f,%.2f,%lu,%u,%u,%u,%u,%u,%.1f,%.1f,%.1f,%u\n", (unsigned long)t.t_ms, t.heading_cd / 100.0,
                    t.pitch_cd / 100.0, t.roll_cd / 100.0, t.alt_cm / 100.0, (unsigned long)t.press_pa, t.tof_mm, t.cell_mv[0],
                    t.cell_mv[1], t.cell_mv[2], t.vsys_mv, t.cell_temp_dc[0] / 10.0, t.cell_temp_dc[1] / 10.0,
                    t.cell_temp_dc[2] / 10.0, t.flags);
}

/* ---------------------------------------------------------------- web */
static const char PAGE[] PROGMEM = R"HTML(<!doctype html><html><head><meta name=viewport content="width=device-width">
<title>FCL</title><style>body{font-family:sans-serif;margin:16px}td{padding:2px 10px}</style></head><body>
<h3>FCL monocular</h3><table id=t></table>
<p>Servo 1 <input type=range min=1000 max=2000 value=1500 oninput="fetch('/servo?ch=0&us='+this.value)">
 Mode <select onchange="fetch('/mode?m='+this.value)"><option>0<option>1<option>2<option>3</select></p>
<script>
async function up(){let s=await (await fetch('/status.json')).json();let h='';
for(const k in s)h+='<tr><td>'+k+'<td>'+s[k];document.getElementById('t').innerHTML=h}
setInterval(up,250);up();</script></body></html>)HTML";

static void web_status()
{
    char j[512];
    snprintf(j, sizeof j,
             "{\"age_ms\":%lu,\"heading\":%.1f,\"pitch\":%.1f,\"roll\":%.1f,\"alt_m\":%.2f,\"tof_mm\":%u,"
             "\"cell_mV\":[%u,%u,%u],\"vsys_mV\":%u,\"temp_C\":[%.1f,%.1f,%.1f],\"mode\":%u,\"flags\":%u,\"frames\":%lu,\"crc_err\":%lu}",
             (unsigned long)(millis() - tel_ms), tel.heading_cd / 100.0, tel.pitch_cd / 100.0, tel.roll_cd / 100.0, tel.alt_cm / 100.0,
             tel.tof_mm, tel.cell_mv[0], tel.cell_mv[1], tel.cell_mv[2], tel.vsys_mv, tel.cell_temp_dc[0] / 10.0,
             tel.cell_temp_dc[1] / 10.0, tel.cell_temp_dc[2] / 10.0, tel.mode, tel.flags, (unsigned long)tel_count,
             (unsigned long)parser.bad);
    web.send(200, "application/json", j);
}

static void web_init()
{
    char ssid[16];
    snprintf(ssid, sizeof ssid, "FCL-%04X", (unsigned)(ESP.getEfuseMac() & 0xFFFF));
    WiFi.softAP(ssid, "monocular");                      /* change before use */
    web.on("/", [] { web.send_P(200, "text/html", PAGE); });
    web.on("/status.json", web_status);
    web.on("/servo", [] {
        int ch = web.arg("ch").toInt(), us = web.arg("us").toInt();
        uint8_t p[3] = { (uint8_t)ch, (uint8_t)us, (uint8_t)(us >> 8) };
        link_send(MSG_CMD_SERVO, p, 3);
        web.send(200, "text/plain", "ok");
    });
    web.on("/mode", [] {
        uint8_t m = (uint8_t)web.arg("m").toInt();
        link_send(MSG_CMD_MODE, &m, 1);
        web.send(200, "text/plain", "ok");
    });
    web.begin();
    Serial.printf("Wi-Fi AP %s, http://%s/\n", ssid, WiFi.softAPIP().toString().c_str());
}

/* ---------------------------------------------------------------- main */
static void on_frame()
{
    if (parser.type == MSG_TELEMETRY && parser.len == TELEMETRY_LEN)
    {
        telemetry_unpack(parser.buf, &tel);
        tel_count++;
        tel_ms = millis();
        sd_log(tel);
    }
    else if (parser.type == MSG_EVENT && parser.len == 1)
    {
        switch (parser.buf[0])
        {
        case EV_B1: case EV_B2: case EV_PWR_SHORT: beep(2000, 40); break;
        case EV_CELL_LOW: beep(800, 150, 2); break;
        case EV_CELL_CUTOFF: beep(500, 300, 3); break;
        case EV_PWR_OFF:
            if (logfile) logfile.close();
            beep(1200, 80); beep(600, 160);
            break;
        }
    }
}

void setup()
{
    Serial.begin(115200);
    Link.setRxBufferSize(1024);
    Link.begin(LINK_BAUD, SERIAL_8N1, PIN_LINK_RX, PIN_LINK_TX);
    link_parser_init(&parser);
    audio_init();
    sd_init();
    web_init();
    beep(1500, 60);
}

void loop()
{
    while (Link.available())
        if (link_parser_feed(&parser, (uint8_t)Link.read()))
            on_frame();
    web.handleClient();
}
