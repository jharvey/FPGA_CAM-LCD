// The full FCL design: camera to TFT (the Icestudio project, as generated: module main, reached through the
// generated name wrapper fcl_cam) + the LCD overlay on its way to the panel + the sensor bridge to the ESP32.
// Build: python fpga/full/build_full.py     Pins: build/fcl_top.lpf (generated from the .ice file and the hub pins)
//
// What changes against the camera-only design:
//   * the LCD data, DE, HS and VS pass through fcl_osd_stream (3 pixel clocks later; the pixel clock is untouched)
//   * B1 / B2 still switch the view and step the threshold, until the ESP32 takes them over (OUT bit 7); it then
//     presses the video keys itself (OUT bits 4, 5, 6: view, threshold up, threshold down)
//   * the power button no longer resets the video pipeline; a power-on reset does
//   * LED0 / LED1 belong to the bridge (the camera design's led[1:0] are not shown)
module fcl_top #(
    parameter POR_BITS = 20              // power-on reset: 2^POR_BITS clocks of 25 MHz (42 ms); the test bench shortens it
) (
    input  wire        clk_25mhz,
    // camera
    input  wire        cmos_pclk,
    input  wire        cmos_href,
    input  wire        cmos_vsync,
    input  wire [7:0]  cmos_db,
    output wire        cmos_rst_n,
    output wire        cmos_pwdn,
    output wire        cmos_xclk,
    output wire        cmos_scl,
    output wire        cmos_sda,
    // frame memory
    output wire        sdram_clk,
    output wire        sdram_cke,
    output wire        sdram_cs_n,
    output wire        sdram_ras_n,
    output wire        sdram_cas_n,
    output wire        sdram_we_n,
    output wire [12:0] sdram_addr,
    output wire [15:0] sdram_dq,         // bidirectional inside the camera design (TRELLIS_IO)
    output wire [1:0]  sdram_ba,
    output wire [1:0]  sdram_dqm,
    // TFT
    output wire        LCD_PCLK,
    output wire        LCD_DE,
    output wire        LCD_HS,
    output wire        LCD_VS,
    output wire [5:0]  LCD_R,
    output wire [5:0]  LCD_G,
    output wire [5:0]  LCD_B,
    output wire        LCD_RESET_N,
    output wire        LCD_SPI_CS_N,
    output wire        LCD_SPI_CLK,
    output wire        LCD_SPI_DC,
    output wire        LCD_SPI_MOSI,
    output wire        LCD_BL_EN,
    output wire [5:0]  cam_led,          // the camera design's led[7:2]
    output wire        pix_clk_out,      // 18 MHz pixel clock on C13 (probe via)
    // bridge
    input  wire        esp_rx,
    output wire        esp_tx,
    inout  wire        i2c_scl,
    inout  wire        i2c_sda,
    output wire        adc_cnv,
    output wire        adc_sck,
    output wire        adc_din,
    input  wire        adc_sdo,
    input  wire        btn_pwr_n,
    input  wire        btn1_n,
    input  wire        btn2_n,
    input  wire        imu_int1,
    input  wire        imu_int2,
    input  wire        mag_drdy,
    input  wire        baro_int,
    input  wire        tof_int,
    output wire        led0,
    output wire        led1,
    output wire        tof_xshut,
    output wire        shutdown,
    output wire        srv_pwm1,
    output wire        srv_pwm2,
    output wire        srv_pwm3,
    output wire        srv_pwm4,
    output wire        srv_pwm5,
    output wire        srv_pwm6
);
    reg [POR_BITS:0] por = 0;                          // reset for 42 ms after configuration (the PLLs lock meanwhile)
    wire rst = !por[POR_BITS];
    always @(posedge clk_25mhz) if (rst) por <= por + 1'b1;

    // ---- bridge
    wire scl_oe, sda_oe;
    assign i2c_scl = scl_oe ? 1'b0 : 1'bz;
    assign i2c_sda = sda_oe ? 1'b0 : 1'bz;
    wire [5:0] servo;
    wire [1:0] led;
    wire [3:0] aux;
    wire       osd_we, dot_on, dot_inside;
    wire [8:0] osd_addr;
    wire [6:0] osd_data;
    wire [9:0] dot_x, dot_y;
    wire [40:0] hud;
    assign {srv_pwm6, srv_pwm5, srv_pwm4, srv_pwm3, srv_pwm2, srv_pwm1} = servo;
    assign {led1, led0} = led;

    fcl_bridge #(.CLK_HZ(25000000), .BAUD(921600)) bridge (
        .clk(clk_25mhz), .rst(rst), .uart_rx(esp_rx), .uart_tx(esp_tx),
        .scl_i(i2c_scl), .scl_oe(scl_oe), .sda_i(i2c_sda), .sda_oe(sda_oe),
        .adc_cnv(adc_cnv), .adc_sck(adc_sck), .adc_din(adc_din), .adc_sdo(adc_sdo),
        .btn_n({btn2_n, btn1_n, btn_pwr_n}), .int_in({tof_int, baro_int, mag_drdy, imu_int2, imu_int1}),
        .led(led), .tof_xshut(tof_xshut), .shutdown(shutdown), .servo(servo), .aux(aux),
        .osd_we(osd_we), .osd_addr(osd_addr), .osd_data(osd_data),
        .dot_x(dot_x), .dot_y(dot_y), .dot_on(dot_on), .dot_inside(dot_inside), .hud(hud));

    // ---- camera design; its key inputs are active low
    wire own = aux[3];
    wire key_view_n = (own | btn1_n) & ~aux[0];
    wire key_inc_n  = (own | btn2_n) & ~aux[1];
    wire key_dec_n  = ~aux[2];
    wire        c_pclk, c_de, c_hs, c_vs, pix_clk;
    wire [5:0]  c_r, c_g, c_b;
    wire [7:0]  c_led;
    assign cam_led = c_led[7:2];
    assign pix_clk_out = pix_clk;

    fcl_cam cam (
        .clk(clk_25mhz), .rst_n(!rst), .switch(key_view_n), .inc_threshold(key_inc_n), .dec_threshold(key_dec_n),
        .cmos_pclk(cmos_pclk), .cmos_href(cmos_href), .cmos_vsync(cmos_vsync), .cmos_db(cmos_db),
        .cmos_rst_n(cmos_rst_n), .cmos_pwdn(cmos_pwdn), .cmos_xclk(cmos_xclk), .cmos_scl(cmos_scl), .cmos_sda(cmos_sda),
        .sdram_clk(sdram_clk), .sdram_cke(sdram_cke), .sdram_cs_n(sdram_cs_n), .sdram_ras_n(sdram_ras_n),
        .sdram_cas_n(sdram_cas_n), .sdram_we_n(sdram_we_n), .sdram_addr(sdram_addr), .sdram_dq(sdram_dq),
        .sdram_ba(sdram_ba), .sdram_dqm(sdram_dqm),
        .LCD_PCLK(c_pclk), .LCD_DE(c_de), .LCD_HS(c_hs), .LCD_VS(c_vs),
        .LCD_R5(c_r[5]), .LCD_R4(c_r[4]), .LCD_R3(c_r[3]), .LCD_R2(c_r[2]), .LCD_R1(c_r[1]), .LCD_R0(c_r[0]),
        .LCD_G5(c_g[5]), .LCD_G4(c_g[4]), .LCD_G3(c_g[3]), .LCD_G2(c_g[2]), .LCD_G1(c_g[1]), .LCD_G0(c_g[0]),
        .LCD_B5(c_b[5]), .LCD_B4(c_b[4]), .LCD_B3(c_b[3]), .LCD_B2(c_b[2]), .LCD_B1(c_b[1]), .LCD_B0(c_b[0]),
        .LCD_RESET_N(LCD_RESET_N), .LCD_SPI_CS_N(LCD_SPI_CS_N), .LCD_SPI_CLK(LCD_SPI_CLK), .LCD_SPI_DC(LCD_SPI_DC),
        .LCD_SPI_MOSI(LCD_SPI_MOSI), .LCD_BL_EN(LCD_BL_EN), .led(c_led), .debug_OUT(pix_clk));

    // ---- overlay between the camera design and the panel
    assign LCD_PCLK = c_pclk;
    fcl_osd_stream #(.BITS(6), .FONT_FILE("font16x32.hex")) osd (
        .pix_clk(pix_clk), .de(c_de), .hs(c_hs), .vs(c_vs), .rgb({c_r, c_g, c_b}),
        .de_o(LCD_DE), .hs_o(LCD_HS), .vs_o(LCD_VS), .rgb_o({LCD_R, LCD_G, LCD_B}),
        .wclk(clk_25mhz), .char_we(osd_we), .char_addr(osd_addr), .char_data(osd_data),
        .dot_x(dot_x), .dot_y(dot_y), .dot_on(dot_on), .dot_inside(dot_inside), .hud(hud));
endmodule
