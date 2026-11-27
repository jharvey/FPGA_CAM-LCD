// The LCD overlay (fcl_osd.v) for a video stream that only has de / hs / vs and the pixel data, as the camera
// design's LCD driver puts out: recovers the pixel position from de and vs, runs the overlay, and delays the
// sync signals by the overlay's 3 clocks.  The pixel clock itself goes to the panel unchanged.
//
// The text memory is written on wclk (the bridge's clock).  The dot position and the graphics values come from
// the same clock domain; they are taken over during vertical sync, and only when two samples in a row agree, so
// a half-changed value is never drawn.
module fcl_osd_stream #(
    parameter BITS = 6,
    parameter FONT_FILE = "font16x32.hex"
) (
    input  wire              pix_clk,
    input  wire              de,
    input  wire              hs,
    input  wire              vs,                 // low during vertical sync
    input  wire [3*BITS-1:0] rgb,
    output wire              de_o,
    output wire              hs_o,
    output wire              vs_o,
    output wire [3*BITS-1:0] rgb_o,
    input  wire              wclk,
    input  wire              char_we,
    input  wire [8:0]        char_addr,
    input  wire [6:0]        char_data,
    input  wire [9:0]        dot_x,
    input  wire [9:0]        dot_y,
    input  wire              dot_on,
    input  wire              dot_inside,
    input  wire [40:0]       hud
);
    reg [9:0] xc = 0, yc = 0;
    reg       de_d = 0;
    always @(posedge pix_clk) begin
        de_d <= de;
        xc   <= de ? xc + 10'd1 : 10'd0;                 // xc = column of the pixel now on rgb
        if (!vs) yc <= 0;
        else if (de_d && !de) yc <= yc + 10'd1;          // a line has ended
    end

    reg [62:0] s1 = 0, s2 = 0, dot = {41'd0, 1'b0, 1'b0, 10'd240, 10'd240};
    always @(posedge pix_clk) begin
        s1 <= {hud, dot_inside, dot_on, dot_y, dot_x};
        s2 <= s1;
        if (!vs && s1 == s2) dot <= s2;
    end

    reg [2:0] hs_d = 3'b111, vs_d = 3'b111;
    always @(posedge pix_clk) begin
        hs_d <= {hs_d[1:0], hs};
        vs_d <= {vs_d[1:0], vs};
    end
    assign hs_o = hs_d[2];
    assign vs_o = vs_d[2];

    fcl_osd #(.BITS(BITS), .FONT_FILE(FONT_FILE)) osd (
        .clk(pix_clk), .x(xc), .y(yc), .de(de), .rgb_in(rgb), .rgb_out(rgb_o), .de_out(de_o),
        .wclk(wclk), .char_we(char_we), .char_addr(char_addr), .char_data(char_data),
        .dot_x(dot[9:0]), .dot_y(dot[19:10]), .dot_on(dot[20]), .dot_inside(dot[21]), .hud(dot[62:22]));
endmodule
