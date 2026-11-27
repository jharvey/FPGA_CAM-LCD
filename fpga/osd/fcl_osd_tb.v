// Test bench for fcl_osd.v: draws one 480 x 480 frame over a flat background and writes it as a PPM file.
// Run through fpga/osd/test_osd.py, which supplies tb_text.hex / tb_args and compares the frame with fcl_osd.py.
`timescale 1ns/1ps
module fcl_osd_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg  [9:0]  x = 0, y = 0;
    reg         de = 0;
    wire [23:0] rgb_out;
    wire        de_out;
    reg         we = 0;
    reg  [8:0]  wa = 0;
    reg  [6:0]  wd = 0;
    reg  [9:0]  dot_x, dot_y;
    reg         dot_on, dot_inside;
    reg  [6:0]  text [0:449];
    integer f, i, n, dxi, dyi, oni, insi;

    fcl_osd #(.BITS(8), .FONT_FILE("font16x32.hex")) dut (
        .clk(clk), .x(x), .y(y), .de(de), .rgb_in(24'h586478), .rgb_out(rgb_out), .de_out(de_out),
        .wclk(clk), .char_we(we), .char_addr(wa), .char_data(wd),
        .dot_x(dot_x), .dot_y(dot_y), .dot_on(dot_on), .dot_inside(dot_inside));

    always @(posedge clk) if (de_out) begin
        $fwrite(f, "%0d %0d %0d\n", rgb_out[23:16], rgb_out[15:8], rgb_out[7:0]);
        n = n + 1;
    end

    initial begin
        $readmemh("tb_text.hex", text);
        if (!$value$plusargs("dx=%d", dxi)) dxi = 240;
        if (!$value$plusargs("dy=%d", dyi)) dyi = 240;
        if (!$value$plusargs("on=%d", oni)) oni = 1;
        if (!$value$plusargs("inside=%d", insi)) insi = 1;
        dot_x = dxi; dot_y = dyi; dot_on = oni; dot_inside = insi;
        n = 0;
        f = $fopen("tb_frame.ppm", "w");
        $fwrite(f, "P3\n480 480\n255\n");
        for (i = 0; i < 450; i = i + 1) begin      // the hub writing the text
            @(negedge clk); we = 1; wa = i; wd = text[i];
        end
        @(negedge clk); we = 0;
        for (i = 0; i < 480 * 480; i = i + 1) begin
            @(negedge clk); de = 1; x = i % 480; y = i / 480;
        end
        @(negedge clk); de = 0;
        repeat (4) @(negedge clk);
        $fclose(f);
        $display("pixels written: %0d", n);
        $finish;
    end
endmodule
