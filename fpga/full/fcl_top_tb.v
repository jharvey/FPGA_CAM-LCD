// Test bench for the whole design, fcl_top.v: a camera model in, an SDRAM model beside it, the ESP32's UART
// driven from a script, and every picture that leaves for the TFT written to a file.  Run by test_full.py.
//   tb_stim.txt    D <microseconds> wait | B <hex byte> UART byte to the bridge | P <mask> buttons | E end
//   tb_out.txt     every byte the bridge sent
//   tb_lcd_<n>.txt one line per pixel the panel would latch (LCD_DE high at a rising LCD_PCLK), 18 bits hex
//   tb_spi.txt     the panel's set-up bytes: <dc> <byte>
//   tb_sccb.txt    the camera's register writes (from the camera model)
//   stdout         CLOCKS ..., FRAME n pixels lines, SDRAM ..., for the Python side
`timescale 1ns/1ps
module fcl_top_tb;
    localparam real BIT_NS = 1.0e9 / 921600.0;
    reg clk = 0;
    always #20 clk = ~clk;                                // 25 MHz

    reg        host_tx = 1;
    wire       esp_tx;
    reg  [2:0] btn = 0;                                   // bit 0 PWR, 1 B1, 2 B2 (pressed = 1)
    wire       cmos_pclk, cmos_href, cmos_vsync, cmos_xclk, cmos_scl, cmos_sda, cmos_rst_n, cmos_pwdn;
    wire [7:0] cmos_db;
    wire       sdram_clk, sdram_cke, sdram_cs_n, sdram_ras_n, sdram_cas_n, sdram_we_n;
    wire [12:0] sdram_addr;
    wire [15:0] sdram_dq;
    wire [1:0] sdram_ba, sdram_dqm;
    wire       LCD_PCLK, LCD_DE, LCD_HS, LCD_VS, LCD_RESET_N, LCD_SPI_CS_N, LCD_SPI_CLK, LCD_SPI_DC, LCD_SPI_MOSI, LCD_BL_EN;
    wire [5:0] LCD_R, LCD_G, LCD_B, cam_led;
    wire       pix_clk_out, led0, led1, tof_xshut, shutdown;
    wire       i2c_scl, i2c_sda, adc_cnv, adc_sck, adc_din;
    wire [5:0] srv;
    reg        slave_sda_low = 0;
    pullup (i2c_scl);
    pullup (i2c_sda);
    assign i2c_sda = slave_sda_low ? 1'b0 : 1'bz;

    fcl_top #(.POR_BITS(8)) dut (                         // reset for 10 us instead of 42 ms
        .clk_25mhz(clk),
        .cmos_pclk(cmos_pclk), .cmos_href(cmos_href), .cmos_vsync(cmos_vsync), .cmos_db(cmos_db),
        .cmos_rst_n(cmos_rst_n), .cmos_pwdn(cmos_pwdn), .cmos_xclk(cmos_xclk), .cmos_scl(cmos_scl), .cmos_sda(cmos_sda),
        .sdram_clk(sdram_clk), .sdram_cke(sdram_cke), .sdram_cs_n(sdram_cs_n), .sdram_ras_n(sdram_ras_n),
        .sdram_cas_n(sdram_cas_n), .sdram_we_n(sdram_we_n), .sdram_addr(sdram_addr), .sdram_dq(sdram_dq),
        .sdram_ba(sdram_ba), .sdram_dqm(sdram_dqm),
        .LCD_PCLK(LCD_PCLK), .LCD_DE(LCD_DE), .LCD_HS(LCD_HS), .LCD_VS(LCD_VS), .LCD_R(LCD_R), .LCD_G(LCD_G), .LCD_B(LCD_B),
        .LCD_RESET_N(LCD_RESET_N), .LCD_SPI_CS_N(LCD_SPI_CS_N), .LCD_SPI_CLK(LCD_SPI_CLK), .LCD_SPI_DC(LCD_SPI_DC),
        .LCD_SPI_MOSI(LCD_SPI_MOSI), .LCD_BL_EN(LCD_BL_EN), .cam_led(cam_led), .pix_clk_out(pix_clk_out),
        .esp_rx(host_tx), .esp_tx(esp_tx), .i2c_scl(i2c_scl), .i2c_sda(i2c_sda),
        .adc_cnv(adc_cnv), .adc_sck(adc_sck), .adc_din(adc_din), .adc_sdo(1'b0),
        .btn_pwr_n(~btn[0]), .btn1_n(~btn[1]), .btn2_n(~btn[2]),
        .imu_int1(1'b0), .imu_int2(1'b0), .mag_drdy(1'b0), .baro_int(1'b0), .tof_int(1'b0),
        .led0(led0), .led1(led1), .tof_xshut(tof_xshut), .shutdown(shutdown),
        .srv_pwm1(srv[0]), .srv_pwm2(srv[1]), .srv_pwm3(srv[2]), .srv_pwm4(srv[3]), .srv_pwm5(srv[4]), .srv_pwm6(srv[5]));

    sdram_model ram (.clk(sdram_clk), .cke(sdram_cke), .cs_n(sdram_cs_n), .ras_n(sdram_ras_n), .cas_n(sdram_cas_n),
                     .we_n(sdram_we_n), .addr(sdram_addr), .ba(sdram_ba), .dqm(sdram_dqm), .dq(sdram_dq));
    ov7670_model cam (.xclk(cmos_xclk), .pclk(cmos_pclk), .href(cmos_href), .vsync(cmos_vsync), .db(cmos_db),
                      .scl(cmos_scl), .sda(cmos_sda));

    // ---------------------------------------------------------------- one I2C device for the bridge: 0x68, 8-bit registers
    reg [7:0]  mem8 [0:255];
    integer    i;
    initial for (i = 0; i < 256; i = i + 1) mem8[i] = i * 3 + 1;
    reg        active = 0, sending = 0, send_next = 0;
    reg [7:0]  sr = 0, txb = 0;
    integer    nbyte = 0, kb = -1;
    reg [7:0]  ptr = 0;
    always @(negedge i2c_sda) if (i2c_scl) begin active = 1; sending = 0; send_next = 0; kb = -1; nbyte = 0; slave_sda_low = 0; end
    always @(posedge i2c_sda) if (i2c_scl) begin active = 0; sending = 0; slave_sda_low = 0; end
    always @(posedge i2c_scl) if (active) begin
        if (!sending && kb >= 0 && kb < 8) sr = {sr[6:0], i2c_sda};
        if (sending && kb == 8 && i2c_sda) begin sending = 0; active = 0; end
    end
    always @(negedge i2c_scl) if (active) begin
        kb = (kb == 8) ? 0 : kb + 1;
        if (kb == 0 && send_next) begin sending = 1; send_next = 0; end
        if (!sending) begin
            if (kb < 8) slave_sda_low = 0;
            else begin
                if (nbyte == 0) begin
                    if (sr[7:1] != 7'h68) active = 0;
                    else begin slave_sda_low = 1; send_next = sr[0]; end
                end else begin
                    slave_sda_low = 1;
                    if (nbyte == 1) ptr = sr;
                    else begin mem8[ptr] = sr; ptr = ptr + 1; end
                end
                nbyte = nbyte + 1;
            end
        end else begin
            if (kb == 0) begin txb = mem8[ptr]; ptr = ptr + 1; end
            if (kb < 8) slave_sda_low = ~txb[7 - kb];
            else slave_sda_low = 0;
        end
    end

    // ---------------------------------------------------------------- UART: bytes from the bridge
    integer fo;
    reg [7:0] rb;
    integer rk;
    always @(negedge esp_tx) begin
        #(BIT_NS * 1.5);
        for (rk = 0; rk < 8; rk = rk + 1) begin rb[rk] = esp_tx; #(BIT_NS); end
        $fwrite(fo, "%02x\n", rb);
        wait (esp_tx == 1);
    end

    // ---------------------------------------------------------------- the panel: set-up bytes, then pictures
    integer fsp, sk = 0;
    reg [7:0] sb = 0;
    initial fsp = $fopen("tb_spi.txt", "w");
    always @(negedge LCD_SPI_CS_N) sk = 0;
    always @(posedge LCD_SPI_CLK) if (!LCD_SPI_CS_N) begin
        sb = {sb[6:0], LCD_SPI_MOSI};
        sk = sk + 1;
        if (sk == 8) begin $fwrite(fsp, "%0d %02x\n", LCD_SPI_DC, sb); sk = 0; end
    end

    integer ff = 0, frame_no = 0, npix = 0, nlines = 0, hs_n = 0, pclk_n = 0;
    reg [8*32-1:0] fname;
    realtime t_frame = 0;
    always @(posedge LCD_PCLK) begin
        pclk_n = pclk_n + 1;
        if (LCD_DE) begin
            if (ff == 0) begin
                $sformat(fname, "tb_lcd_%0d.txt", frame_no);
                ff = $fopen(fname, "w");
            end
            $fwrite(ff, "%h\n", {LCD_R, LCD_G, LCD_B});
            npix = npix + 1;
        end
    end
    always @(negedge LCD_DE) nlines = nlines + 1;
    always @(negedge LCD_HS) hs_n = hs_n + 1;
    always @(negedge LCD_VS) begin                         // the picture is complete
        if (ff != 0) begin
            $fclose(ff);
            $display("FRAME %0d pixels %0d lines %0d hsync %0d at_us %0d period_us %0d sobel %0d", frame_no, npix, nlines, hs_n,
                     $rtoi($realtime / 1000.0), $rtoi(($realtime - t_frame) / 1000.0), dut.aux);
            frame_no = frame_no + 1;
        end
        ff = 0; npix = 0; nlines = 0; hs_n = 0;
        t_frame = $realtime;
    end

    // ---------------------------------------------------------------- clocks as they really are
    integer n_pix = 0, n_ram = 0, n_x = 0;
    always @(posedge pix_clk_out) n_pix = n_pix + 1;
    always @(posedge sdram_clk) n_ram = n_ram + 1;
    always @(posedge cmos_xclk) n_x = n_x + 1;

    // ---------------------------------------------------------------- stimulus
    integer fi, n, val, bk;
    reg [8*8-1:0] op;
    initial begin
        fo = $fopen("tb_out.txt", "w");
        fi = $fopen("tb_stim.txt", "r");
        while (!$feof(fi)) begin
            n = $fscanf(fi, "%s %h\n", op, val);
            if (op == "D") #(val * 1000.0);
            else if (op == "B") begin
                host_tx = 0; #(BIT_NS);
                for (bk = 0; bk < 8; bk = bk + 1) begin host_tx = val[bk]; #(BIT_NS); end
                host_tx = 1; #(BIT_NS);
            end
            else if (op == "P") btn = val[2:0];
            else if (op == "E") begin
                $display("CLOCKS us %0d pix %0d sdram %0d xclk %0d lcd_pclk %0d", $rtoi($realtime / 1000.0), n_pix, n_ram, n_x, pclk_n);
                $display("SDRAM mode_set %0d reads %0d writes %0d words %0d refreshes %0d bad_rows %0d", ram.mode_set, ram.n_read,
                         ram.n_write, ram.words, ram.n_refresh, ram.bad_row);
                $display("CAMERA frames %0d backlight %0d lcd_reset_n %0d", cam.frames, LCD_BL_EN, LCD_RESET_N);
                $fclose(fo); $fclose(fsp);
                $finish;
            end
        end
    end
endmodule
