// LCD overlay for the FCL video path: a 30 x 15 character text layer (16 x 32 px glyphs) and the "down" dot,
// drawn over the camera picture on its way to the 480 x 480 TFT.
//
// Same pixels as firmware/sim/fcl_osd.py (overlay_pixel), checked by fpga/osd/test_osd.py:
//   * a character cell that holds a character: glyph pixels white, the rest of the cell at half brightness
//   * the dot: filled centre (r <= 3) and ring (8 <= r <= 11) in the dot colour, black edge out to r = 13
//
// The hub CPU writes the text through the char_* port (address = row * 30 + col, ASCII) and sets the dot
// registers (screen pixels, 0..479).  Not yet instantiated in the camera design: that needs the hub CPU.
//
// Latency: 2 clocks.  Delay hsync / vsync / de by 2 clocks alongside (de_out is provided).
module fcl_osd #(
    parameter BITS = 6,                          // bits per colour: 6 for the RGB666 panel
    parameter FONT_FILE = "font16x32.hex"
) (
    input  wire              clk,
    input  wire [9:0]        x,                  // pixel position of rgb_in
    input  wire [9:0]        y,
    input  wire              de,
    input  wire [3*BITS-1:0] rgb_in,             // {r, g, b}
    output reg  [3*BITS-1:0] rgb_out,
    output reg               de_out,
    // text memory, written by the hub
    input  wire              char_we,
    input  wire [8:0]        char_addr,          // 0..449
    input  wire [6:0]        char_data,
    // down dot
    input  wire [9:0]        dot_x,
    input  wire [9:0]        dot_y,
    input  wire              dot_on,
    input  wire              dot_inside          // 1: green (in the picture), 0: amber (on the rim)
);
    localparam COLS = 30;

    reg [6:0]  text [0:449];
    reg [15:0] font [0:3071];                    // 96 glyphs x 32 rows
    integer i;
    initial begin
        for (i = 0; i < 450; i = i + 1) text[i] = 7'd32;
        $readmemh(FONT_FILE, font);
    end
    always @(posedge clk) if (char_we && char_addr < 450) text[char_addr] <= char_data;

    // stage 1: character at this cell
    wire [4:0] col = x[8:4];
    wire [3:0] row = y[8:5];
    wire       in_grid = (x < 480) && (y < 480);
    reg  [6:0] ch;
    reg  [4:0] gy1;
    reg  [3:0] gx1, gx2;
    reg        de1;
    reg  [3*BITS-1:0] rgb1, rgb2;
    reg  [9:0] x1, y1;
    always @(posedge clk) begin
        ch   <= in_grid ? text[row * COLS + col] : 7'd32;
        gy1  <= y[4:0];
        gx1  <= x[3:0];
        de1  <= de;
        rgb1 <= rgb_in;
        x1   <= x;
        y1   <= y;
    end

    // stage 2: glyph row, and the squared distance to the dot
    wire [6:0]  glyph = (ch < 7'd32) ? 7'd0 : ch - 7'd32;
    reg  [15:0] bits;
    reg         cell_used;
    reg         de2;
    wire signed [10:0] ddx = $signed({1'b0, x1}) - $signed({1'b0, dot_x});
    wire signed [10:0] ddy = $signed({1'b0, y1}) - $signed({1'b0, dot_y});
    reg  [21:0] d2;
    always @(posedge clk) begin
        bits      <= font[{glyph, gy1}];
        cell_used <= (ch != 7'd32) && (ch >= 7'd32);
        gx2       <= gx1;
        de2       <= de1;
        rgb2      <= rgb1;
        d2        <= ddx * ddx + ddy * ddy;
    end

    // stage 3 (combinational into the output register)
    wire text_px = bits[15 - gx2];
    wire [BITS-1:0] r2 = rgb2[3*BITS-1:2*BITS], g2 = rgb2[2*BITS-1:BITS], b2 = rgb2[BITS-1:0];
    wire dot_core = dot_on && (d2 <= 22'd9 || (d2 >= 22'd64 && d2 <= 22'd121));
    wire dot_edge = dot_on && (d2 <= 22'd169);
    // dot colours, 8-bit values cut to BITS: green (40, 255, 80), amber (255, 176, 0)
    wire [7:0] cr = dot_inside ? 8'd40  : 8'd255;
    wire [7:0] cg = dot_inside ? 8'd255 : 8'd176;
    wire [7:0] cb = dot_inside ? 8'd80  : 8'd0;
    reg [3*BITS-1:0] px;
    always @* begin
        px = rgb2;
        if (cell_used) px = text_px ? {3*BITS{1'b1}} : {r2 >> 1, g2 >> 1, b2 >> 1};
        if (dot_core)      px = {cr[7:8-BITS], cg[7:8-BITS], cb[7:8-BITS]};
        else if (dot_edge) px = {3*BITS{1'b0}};
    end
    always @(posedge clk) begin
        rgb_out <= px;
        de_out  <= de2;
    end
endmodule
