#!/usr/bin/env python3
"""Check the pins the designs and the firmware use against the routed board, FCL.kicad_pcb.

    python fpga/check_pins.py [path/to/fcl_top.lpf]          exit code 0 = everything on its net

FPGA (U1): every pin of the full design's pin file (fpga/prebuilt/full/fcl_top.lpf, or the file given) must sit on
a ball whose net is the one that signal is meant for:
  * camera and display signals: the net must reach the right pin of J1 (camera module, the usual 18-pin OV7670
    pinout) or J7 (the NHD-2.1-480480AF-ASXP's 40-pin FPC, pinout in doc/constraints/camera_display_pinmap.md);
  * everything else: a named net (SDRAM_A3, IMU_SCL, SRV_PWM2, ...);
  * the camera design's debug LEDs led[7:2] and the pixel-clock output may go to free balls (nothing is driven);
    the pixel clock's ball must have a probe via (doc/PROBE_POINTS.md).
  No ball may be used twice.
ESP32 (U9): every GPIO number in the firmware (fcl_usbdev.py, sdpin.py, jtagpin.py) must be on the pad of the
module that carries the net it is used for, and the JTAG nets must reach the FPGA's JTAG pins.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ESP = os.path.join(ROOT, "firmware", "esp32")

# connector pin -> the fcl_top port that must arrive there
J1 = {3: "cmos_scl", 4: "cmos_sda", 5: "cmos_vsync", 6: "cmos_href", 7: "cmos_pclk", 9: "cmos_db[7]", 10: "cmos_db[6]",
      11: "cmos_db[5]", 12: "cmos_db[4]", 13: "cmos_db[3]", 14: "cmos_db[2]", 15: "cmos_db[1]", 16: "cmos_db[0]",
      17: "cmos_rst_n", 18: "cmos_pwdn"}
J7 = {11: "LCD_VS", 12: "LCD_HS", 13: "LCD_PCLK", 14: "LCD_DE", 33: "LCD_RESET_N", 34: "LCD_SPI_CS_N", 35: "LCD_SPI_CLK",
      36: "LCD_SPI_DC", 37: "LCD_SPI_MOSI"}
for i in range(6):
    J7[15 + i], J7[21 + i], J7[27 + i] = "LCD_B[%d]" % i, "LCD_G[%d]" % i, "LCD_R[%d]" % i
NAMED = {
    "clk_25mhz": "CLK_25MHz", "cmos_xclk": "CAM_XCLK", "LCD_BL_EN": "GP13",
    "sdram_clk": "SDRAM_CLK", "sdram_cke": "SDRAM_CKE", "sdram_cs_n": "SDRAM_nCS", "sdram_ras_n": "SDRAM_nRAS",
    "sdram_cas_n": "SDRAM_nCAS", "sdram_we_n": "SDRAM_nWE",
    "i2c_scl": "IMU_SCL", "i2c_sda": "IMU_SDA", "imu_int1": "IMU_INT1", "imu_int2": "IMU_INT2", "mag_drdy": "MAG_DRDY",
    "baro_int": "BARO_INT", "tof_int": "TOF_INT", "tof_xshut": "TOF_XSHUT", "adc_cnv": "ADC_CNV", "adc_din": "ADC_DIN",
    "adc_sck": "ADC_SCK", "adc_sdo": "ADC_SDO", "btn_pwr_n": "BTN_PWRn", "btn1_n": "BTN1n", "btn2_n": "BTN2n",
    "led0": "LED0", "led1": "LED1", "esp_rx": "WIFI_TXD", "esp_tx": "WIFI_RXD", "shutdown": "SHUTDOWN"}
FREE_OK = re.compile(r"cam_led\[\d\]$|pix_clk_out$")       # outputs that may go to free balls


def named(port):
    if port in NAMED:
        return NAMED[port]
    m = re.match(r"(\w+)\[(\d+)\]$", port)
    if m:
        base, bit = m.group(1), int(m.group(2))
        return {"sdram_addr": "SDRAM_A%d", "sdram_dq": "SDRAM_D%d", "sdram_ba": "SDRAM_BA%d", "sdram_dqm": "SDRAM_DQM%d"}.get(base, "?%d") % bit
    m = re.match(r"srv_pwm(\d)$", port)
    return "SRV_PWM" + m.group(1) if m else None


def footprint_pads(pcb, ref):
    """-> {pad: (net, pin function)} of the footprint with this reference"""
    i = pcb.find('(property "Reference" "%s"' % ref)
    if i < 0:
        raise SystemExit("%s not found in the board" % ref)
    start = pcb.rfind("(footprint ", 0, i)
    end = pcb.find("\n\t(footprint ", start + 10)
    fp = pcb[start:end if end > 0 else len(pcb)]
    pads = {}
    for part in fp.split('(pad "')[1:]:
        name = part.split('"', 1)[0]
        net = re.search(r'\(net (?:\d+ )?"([^"]*)"\)', part)
        fn = re.search(r'\(pinfunction "([^"]*)"\)', part)
        if name and net:
            pads[name] = (net.group(1).lstrip("/").split("/")[-1], fn.group(1) if fn else "")
    return pads


def probe_balls():
    text = open(os.path.join(ROOT, "doc", "PROBE_POINTS.md"), encoding="utf-8").read()
    sec = text.split("## Spare FPGA balls", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\| ([A-Z]\d+) \|", sec, re.M))


def check_fpga(pcb, lpf, out):
    u1 = footprint_pads(pcb, "U1")
    want = {}                                   # port -> expected net
    for ref, table in (("J1", J1), ("J7", J7)):
        pads = footprint_pads(pcb, ref)
        for pin, port in table.items():
            want[port] = pads[str(pin)][0]
    probes = probe_balls()
    locs = re.findall(r'LOCATE COMP "([^"]+)" SITE "(\w+)";', open(lpf).read())
    seen, bad = {}, 0
    for port, ball in locs:
        net = u1.get(ball, ("<no such ball>", ""))[0]
        exp = want.get(port) or named(port)
        if ball in seen:
            out.append("BAD  %s and %s on the same ball %s" % (seen[ball], port, ball))
            bad += 1
        seen[ball] = port
        if FREE_OK.match(port):
            ok = net.startswith("unconnected") and (port != "pix_clk_out" or ball in probes)
            note = "free ball" + (", probe via" if ball in probes else "")
        else:
            ok = exp is not None and net == exp
            note = "via %s" % ("J1" if port in J1.values() else "J7") if port in want else ""
        if not ok:
            bad += 1
        out.append("%s %-14s %-4s %-24s %s" % ("ok  " if ok else "BAD ", port, ball, net, note if ok else "expected %s" % exp))
    # the JTAG nets of the ESP32 must reach the FPGA's JTAG pins
    jt = dict((fn.split("_")[0], net) for pad, (net, fn) in u1.items() if fn.split("_")[0] in ("TCK", "TDI", "TDO", "TMS"))
    for sig in ("TCK", "TDI", "TDO", "TMS"):
        ok = jt.get(sig) == "JTAG_" + sig
        bad += not ok
        out.append("%s FPGA %-9s %-4s %s" % ("ok  " if ok else "BAD ", sig, "", jt.get(sig)))
    return len(locs), bad


def firmware_gpios():
    """-> [(where, gpio, net it must be on)]"""
    src = open(os.path.join(ESP, "fcl_usbdev.py"), encoding="utf-8").read()
    m = re.search(r"I2S_BCLK, I2S_WS, I2S_SPK, I2S_MIC, AMP_SD = (\d+), (\d+), (\d+), (\d+), (\d+)", src)
    g = [("fcl_usbdev I2S_BCLK", int(m.group(1)), "I2S_BCLK"), ("fcl_usbdev I2S_WS", int(m.group(2)), "I2S_WS"),
         ("fcl_usbdev I2S_SPK", int(m.group(3)), "I2S_SPK"), ("fcl_usbdev I2S_MIC", int(m.group(4)), "I2S_MIC"),
         ("fcl_usbdev AMP_SD", int(m.group(5)), "AMP_SD")]
    m = re.search(r"UART\(1, baudrate=\d+, tx=(\d+), rx=(\d+)", src)
    g += [("fcl_usbdev UART tx", int(m.group(1)), "WIFI_TXD"), ("fcl_usbdev UART rx", int(m.group(2)), "WIFI_RXD")]
    for fname, names in (("sdpin.py", {"d0": "SD_D0", "d1": "SD_D1", "d2": "SD_D2", "d3": "SD_D3", "clk": "SD_CLK", "cmd": "SD_CMD", "cd": "SD_CD"}),
                         ("jtagpin.py", {"tms": "JTAG_TMS", "tck": "JTAG_TCK", "tdi": "JTAG_TDI", "tdo": "JTAG_TDO"})):
        text = open(os.path.join(ESP, fname), encoding="utf-8").read()
        for var, net in names.items():
            g.append(("%s %s" % (fname[:-3], var), int(re.search(r"^%s = const\((\d+)\)" % var, text, re.M).group(1)), net))
    return g


def check_esp32(pcb, out):
    u9 = footprint_pads(pcb, "U9")
    by_gpio = {}
    for pad, (net, fn) in u9.items():
        m = re.match(r"IO(\d+)_", fn)
        if m:
            by_gpio[int(m.group(1))] = net
    bad = 0
    gpios = firmware_gpios()
    for where, gpio, net in gpios:
        got = by_gpio.get(gpio, "<not on the module>")
        ok = got == net
        bad += not ok
        out.append("%s %-22s GPIO%-3d %s" % ("ok  " if ok else "BAD ", where, gpio, got if ok else "%s, expected %s" % (got, net)))
    return len(gpios), bad


def main():
    lpf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "prebuilt", "full", "fcl_top.lpf")
    pcb = open(os.path.join(ROOT, "FCL.kicad_pcb"), encoding="utf-8").read()
    out = []
    n1, b1 = check_fpga(pcb, lpf, out)
    n2, b2 = check_esp32(pcb, out)
    print("\n".join(out))
    print("\nFPGA: %d pins and the 4 JTAG pins, %d wrong.  ESP32: %d GPIOs in the firmware, %d wrong." % (n1, b1, n2, b2))
    print("ALL PINS ON THEIR NETS" if not (b1 or b2) else "%d PIN(S) WRONG" % (b1 + b2))
    return 1 if b1 or b2 else 0


if __name__ == "__main__":
    sys.exit(main())
