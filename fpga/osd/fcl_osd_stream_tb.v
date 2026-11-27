// Test bench for fcl_osd_stream.v: video timing as the camera design's LCD driver makes it (640 x 506 clocks,
// picture in columns 80..559 of lines 0..479), text written from a second, unrelated clock.  Writes the second
// frame as a PPM file and checks that hs / vs come out 3 clocks late.  Run through fpga/osd/test_osd.py.
`timescale 1ns/1ps
module fcl_osd_stream_tb;
    reg pix = 0, wclk = 0;
    always #27.7 pix = ~pix;                     // 18 MHz
    always #20 wclk = ~wclk;                     // 25 MHz
    reg  [9:0]  x = 0, y = 486;
    wire        de = (x >= 80) && (x < 560) && (y < 480);
    wire        hs = ~((x >= 600) && (x < 620));
    wire        vs = ~((y >= 490) && (y < 496));
    wire [23:0] rgb_o;
    wire        de_o, hs_o, vs_o;
    reg         we = 0;
    reg  [8:0]  wa = 0;
    reg  [6:0]  wd = 0;
    reg  [9:0]  dot_x, dot_y;
    reg         dot_on, dot_inside;
    reg  [40:0] hud = 0;
    integer     hfi, hai, hbi, hci, hti;
    reg  [6:0]  text [0:449];
    reg  [2:0]  hs_ref = 7, vs_ref = 7;
    integer f, i, n, frames, bad, dxi, dyi, oni, insi;

    fcl_osd_stream #(.BITS(8), .FONT_FILE("font16x32.hex")) dut (
        .pix_clk(pix), .de(de), .hs(hs), .vs(vs), .rgb(24'h586478), .de_o(de_o), .hs_o(hs_o), .vs_o(vs_o), .rgb_o(rgb_o),
        .wclk(wclk), .char_we(we), .char_addr(wa), .char_data(wd),
        .dot_x(dot_x), .dot_y(dot_y), .dot_on(dot_on), .dot_inside(dot_inside), .hud(hud));

    always @(posedge pix) begin
        if (x == 639) begin
            x <= 0;
            if (y == 505) begin y <= 0; frames = frames + 1; end else y <= y + 1;
        end else x <= x + 1;
        hs_ref <= {hs_ref[1:0], hs};
        vs_ref <= {vs_ref[1:0], vs};
        if (hs_o !== hs_ref[2] || vs_o !== vs_ref[2]) bad = bad + 1;
        if (de_o && frames == 1) begin
            $fwrite(f, "%0d %0d %0d\n", rgb_o[23:16], rgb_o[15:8], rgb_o[7:0]);
            n = n + 1;
        end
    end

    initial begin
        $readmemh("tb_text.hex", text);
        if (!$value$plusargs("dx=%d", dxi)) dxi = 240;
        if (!$value$plusargs("dy=%d", dyi)) dyi = 240;
        if (!$value$plusargs("on=%d", oni)) oni = 1;
        if (!$value$plusargs("inside=%d", insi)) insi = 1;
        if (!$value$plusargs("hf=%d", hfi)) hfi = 0;
        if (!$value$plusargs("ha=%d", hai)) hai = 0;
        if (!$value$plusargs("hb=%d", hbi)) hbi = 0;
        if (!$value$plusargs("hc=%d", hci)) hci = 0;
        if (!$value$plusargs("ht=%d", hti)) hti = 0;
        hud = {hti[4:0], hci[10:0], hbi[10:0], hai[10:0], hfi[2:0]};
        n = 0; frames = 0; bad = 0;
        f = $fopen("tb_frame.ppm", "w");
        $fwrite(f, "P3\n480 480\n255\n");
        // the bridge writes the text and the dot while frame 0 is being drawn; frame 1 is the one compared
        for (i = 0; i < 450; i = i + 1) begin
            @(negedge wclk); we = 1; wa = i; wd = text[i];
        end
        @(negedge wclk); we = 0;
        dot_x = dxi; dot_y = dyi; dot_on = oni; dot_inside = insi;
        wait (frames == 2);
        repeat (8) @(posedge pix);
        $fclose(f);
        $display("pixels written: %0d, sync errors: %0d", n, bad);
        $finish;
    end
endmodule
