// LCD overlay for the FCL video path: a 30 x 15 character text layer (16 x 32 px glyphs) and the "down" dot,
// drawn over the camera picture on its way to the 480 x 480 TFT.
//
// Same pixels as firmware/sim/fcl_osd.py (overlay_pixel), checked by fpga/osd/test_osd.py:
//   * a character cell that holds a character: glyph pixels white, the rest of the cell at half brightness
//   * the dot: filled centre (r <= 3) and ring (8 <= r <= 11) in the dot colour, black edge out to r = 13
//   * the graphics, each switched by a bit of hud[2:0], drawn under the text and the dot:
//       bit 0  reticle: a cross at the centre (240, 240) with a gap, white with a black edge
//       bit 1  horizon: the line a*dx + b*dy + 128*c = 0 (dx, dy from the centre; a, b = 512 x the line's unit
//              normal; c in quarter pixels), white with a black edge, between 48 and 176 px from the centre
//       bit 2  compass tape: a band at the top (x 152..327, y 18..29) with a tick every 16 px (5 degrees), tall
//              every 32, moved right by `tape` pixels (0..31), and a fixed pointer above it
//
// The bridge (fpga/bridge/fcl_bridge.v) writes the text through the char_* port (address = row * 30 + col,
// ASCII) on its own clock wclk, and sets the dot registers (screen pixels, 0..479).  fcl_osd_stream.v wraps
// this module for a de / hs / vs video stream; fpga/full/fcl_top.v puts it in the camera design.
//
// Latency: 3 clocks.  Delay hsync / vsync by 3 clocks alongside (de_out is provided).
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
    // text memory, written by the bridge on wclk
    input  wire              wclk,
    input  wire              char_we,
    input  wire [8:0]        char_addr,          // 0..449
    input  wire [6:0]        char_data,
    // down dot
    input  wire [9:0]        dot_x,
    input  wire [9:0]        dot_y,
    input  wire              dot_on,
    input  wire              dot_inside,         // 1: green (in the picture), 0: amber (on the rim)
    // graphics: {tape[4:0], c[10:0], b[10:0], a[10:0], flags[2:0]}, see above
    input  wire [40:0]       hud
);
    localparam COLS = 30;

    reg [6:0]  text [0:449];
    reg [15:0] font [0:3071];                    // 96 glyphs x 32 rows
    integer i;
    initial begin
        for (i = 0; i < 450; i = i + 1) text[i] = 7'd32;
        $readmemh(FONT_FILE, font);
    end
    always @(posedge wclk) if (char_we && char_addr < 450) text[char_addr] <= char_data;

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
    // graphics
    wire signed [10:0] ha = hud[13:3], hb = hud[24:14], hc = hud[35:25];
    wire signed [10:0] dx = $signed({1'b0, x1}) - 11'sd240;
    wire signed [10:0] dy = $signed({1'b0, y1}) - 11'sd240;
    wire [9:0] adx = dx[10] ? -dx : dx, ady = dy[10] ? -dy : dy;
    wire [9:0] far = (adx > ady) ? adx : ady;
    wire [4:0] tv  = x1[4:0] + 5'd16 + hud[40:36];           // (x - 240 + tape) mod 32
    wire       band = (x1 >= 10'd152) && (x1 <= 10'd327) && (y1 >= 10'd18) && (y1 <= 10'd29);
    reg signed [22:0] he;
    reg        h_ring, r_core, r_edge, t_band, t_tick;
    always @(posedge clk) begin
        he     <= ha * dx + hb * dy + (hc <<< 7);
        h_ring <= hud[1] && (far >= 10'd48) && (far <= 10'd176);
        r_core <= hud[0] && ((dy == 0 && adx <= 10'd28 && (adx >= 10'd6 || adx == 0)) || (dx == 0 && ady >= 10'd6 && ady <= 10'd28));
        r_edge <= hud[0] && ((ady <= 10'd1 && adx <= 10'd29 && (adx >= 10'd5 || adx <= 10'd1)) || (adx <= 10'd1 && ady >= 10'd5 && ady <= 10'd29));
        t_band <= hud[2] && band;
        t_tick <= hud[2] && ((band && (tv < 5'd2 || ((tv == 5'd16 || tv == 5'd17) && y1 >= 10'd24)))
                             || (adx <= 10'd1 && y1 >= 10'd10 && y1 <= 10'd15));
    end
    wire h_core = h_ring && (he >= -23'sd512) && (he <= 23'sd512);
    wire h_edge = h_ring && (he >= -23'sd1100) && (he <= 23'sd1100);
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
        if (t_band)                 px = {r2 >> 1, g2 >> 1, b2 >> 1};
        if (t_tick)                 px = {3*BITS{1'b1}};
        if (h_core)                 px = {3*BITS{1'b1}};
        else if (h_edge)            px = {3*BITS{1'b0}};
        if (r_core)                 px = {3*BITS{1'b1}};
        else if (r_edge)            px = {3*BITS{1'b0}};
        if (cell_used) px = text_px ? {3*BITS{1'b1}} : {px[3*BITS-1:2*BITS] >> 1, px[2*BITS-1:BITS] >> 1, px[BITS-1:0] >> 1};
        if (dot_core)      px = {cr[7:8-BITS], cg[7:8-BITS], cb[7:8-BITS]};
        else if (dot_edge) px = {3*BITS{1'b0}};
    end
    always @(posedge clk) begin
        rgb_out <= px;
        de_out  <= de2;
    end
endmodule
