// Simulation models for the full design test (fpga/full/test_full.py): the three Lattice primitives the camera
// design instantiates, an SDRAM, and an OV7670 camera.  Behaviour only: no setup, hold or output delays.
`timescale 1ns/1ps

// ---- PLL: CLKOP = CLKI * CLKFB_DIV / CLKI_DIV (feedback from CLKOP, as the camera design uses it)
module EHXPLLL #(
    parameter PLLRST_ENA = "DISABLED", INTFB_WAKE = "DISABLED", STDBY_ENABLE = "DISABLED", DPHASE_SOURCE = "DISABLED",
    parameter OUTDIVIDER_MUXA = "DIVA", OUTDIVIDER_MUXB = "DIVB", OUTDIVIDER_MUXC = "DIVC", OUTDIVIDER_MUXD = "DIVD",
    parameter CLKOP_ENABLE = "ENABLED", FEEDBK_PATH = "CLKOP",
    parameter CLKI_DIV = 1, CLKFB_DIV = 1, CLKOP_DIV = 1, CLKOP_CPHASE = 0, CLKOP_FPHASE = 0
) (
    input RST, STDBY, CLKI, CLKFB, PHASESEL0, PHASESEL1, PHASEDIR, PHASESTEP, PHASELOADREG, PLLWAKESYNC, ENCLKOP,
    output reg CLKOP, output CLKINTFB, output reg LOCK
);
    realtime t_last = 0, per = 0, half = 0;
    integer  seen = 0;
    initial begin CLKOP = 0; LOCK = 0; end
    always @(posedge CLKI) begin
        per = $realtime - t_last;
        t_last = $realtime;
        seen = seen + 1;
        if (seen == 4) begin half = per * CLKI_DIV / CLKFB_DIV / 2.0; LOCK = 1; end
    end
    always begin
        wait (LOCK);
        #(half) CLKOP = ~CLKOP;
    end
    assign CLKINTFB = 1'b0;
endmodule

module ODDRX1F (input D0, D1, SCLK, RST, output reg Q);
    always @(posedge SCLK) Q <= D0;
    always @(negedge SCLK) Q <= D1;
endmodule

module TRELLIS_IO #(parameter DIR = "BIDIR") (inout B, input I, input T, output O);
    assign B = T ? 1'bz : I;
    assign O = B;
endmodule

// ---- SDRAM, 16 bits wide, as the controller sets it up: CAS latency 3, full-page bursts of 512 words.
// A burst ends with the next precharge.  Rows above 2047 are not stored (the design uses 300 rows per bank).
module sdram_model (
    input clk, cke, cs_n, ras_n, cas_n, we_n,
    input [12:0] addr, input [1:0] ba, input [1:0] dqm,
    inout [15:0] dq
);
    reg [15:0] mem [0:(1 << 22) - 1];
    reg [12:0] row [0:3];
    reg [21:0] ptr = 0;
    reg        reading = 0, writing = 0, mode_set = 0;
    reg [15:0] p1 = 0, p2 = 0, p3 = 0, dq_o = 0;
    reg        v1 = 0, v2 = 0, v3 = 0, dq_oe = 0;
    integer    n_read = 0, n_write = 0, n_refresh = 0, bad_row = 0, words = 0;
    wire [3:0] cmd = {cs_n, ras_n, cas_n, we_n};
    assign dq = dq_oe ? dq_o : 16'hzzzz;
    always @(posedge clk) if (cke) begin
        dq_o <= p3; dq_oe <= v3;                 // a read command at edge n: first word on the pins from edge n + 3
        p3 <= p2; v3 <= v2;
        p2 <= p1; v2 <= v1;
        v1 <= 0;
        case (cmd)
            4'b0000: mode_set <= (addr[9:0] == 10'b0_00_011_0_111);          // CL 3, sequential, full page
            4'b0001: n_refresh = n_refresh + 1;
            4'b0010: begin reading <= 0; writing <= 0; end                    // precharge
            4'b0110: begin reading <= 0; writing <= 0; end                    // burst stop
            4'b0011: begin row[ba] <= addr; if (addr[12:11] != 0) bad_row = bad_row + 1; end
            4'b0101: begin                                                   // read
                reading <= 1; writing <= 0; n_read = n_read + 1;
                p1 <= mem[{ba, row[ba][10:0], addr[8:0]}]; v1 <= 1;
                ptr <= {ba, row[ba][10:0], addr[8:0] + 9'd1};
            end
            4'b0100: begin                                                   // write: the first word is on the pins now
                writing <= 1; reading <= 0; n_write = n_write + 1; words = words + 1;
                mem[{ba, row[ba][10:0], addr[8:0]}] <= dq;
                ptr <= {ba, row[ba][10:0], addr[8:0] + 9'd1};
            end
            default: begin
                if (reading) begin p1 <= mem[ptr]; v1 <= 1; ptr[8:0] <= ptr[8:0] + 9'd1; end
                if (writing) begin mem[ptr] <= dq; ptr[8:0] <= ptr[8:0] + 9'd1; words = words + 1; end
            end
        endcase
    end
endmodule

// ---- OV7670: takes its set-up over SCCB (every register write goes to tb_sccb.txt) and sends 640 x 480 RGB565
// frames with the sensor's own timing: 784 pixels (1568 clocks) per line, 510 lines, pixel clock = xclk.
// The picture: 40 x 40 pixel blocks, block (bx, by) has colour number (3 bx + 5 by) mod 16 of the table below; or,
// with +photo, the 640 x 480 RGB565 words of tb_photo.hex (one per line, row by row).
module ov7670_model (
    input xclk, output pclk, output reg href, output reg vsync, output reg [7:0] db,
    input scl, inout sda
);
    assign pclk = xclk;
    function [15:0] colour;
        input [3:0] n;
        case (n)
            0: colour = 16'hF800;  1: colour = 16'h07E0;  2: colour = 16'h001F;  3: colour = 16'hFFFF;
            4: colour = 16'h0000;  5: colour = 16'hFFE0;  6: colour = 16'hF81F;  7: colour = 16'h07FF;
            8: colour = 16'h8410;  9: colour = 16'h4208; 10: colour = 16'hA145; 11: colour = 16'h39C7;
            12: colour = 16'h5ACB; 13: colour = 16'hC618; 14: colour = 16'h2D7F; 15: colour = 16'hD2A6;
        endcase
    endfunction
    integer px = 0, ln = 0, frames = 0;
    integer xi, yi;
    reg [15:0] w;
    reg [15:0] photo [0:640 * 480 - 1];
    reg use_photo = 0;
    initial begin
        href = 0; vsync = 0; db = 0;
        if ($test$plusargs("photo")) begin $readmemh("tb_photo.hex", photo); use_photo = 1; end
    end
    always @(negedge xclk) begin                 // the sensor changes its outputs on the falling edge of PCLK
        if (px == 1567) begin
            px = 0;
            if (ln == 509) begin ln = 0; frames = frames + 1; end else ln = ln + 1;
        end else px = px + 1;
        vsync <= (ln < 3);
        if (ln >= 20 && ln < 500 && px < 1280) begin
            xi = px / 2; yi = ln - 20;
            w = use_photo ? photo[yi * 640 + xi] : colour((3 * (xi / 40) + 5 * (yi / 40)) % 16);
            href <= 1;
            db <= px[0] ? w[7:0] : w[15:8];
        end else begin
            href <= 0;
            db <= 0;
        end
    end

    // SCCB: acknowledge every byte; log register writes
    reg        active = 0, ack = 0;
    integer    kb = -1, nbyte = 0, fs;
    reg [7:0]  sr = 0, regn = 0;
    assign (pull0, highz1) sda = ack ? 1'b0 : 1'bz;
    initial fs = $fopen("tb_sccb.txt", "w");
    always @(negedge sda) if (scl === 1'b1 && !ack) begin active = 1; kb = -1; nbyte = 0; end       // START
    always @(posedge sda) if (scl === 1'b1 && !ack) active = 0;                                     // STOP
    always @(posedge scl) if (active && kb >= 0 && kb < 8) sr = {sr[6:0], sda};
    always @(negedge scl) if (active) begin
        kb = (kb == 8) ? 0 : kb + 1;
        ack = (kb == 8);
        if (kb == 8) begin
            if (nbyte == 1) regn = sr;
            if (nbyte == 2) begin $fwrite(fs, "%02x %02x\n", regn, sr); $fflush(fs); end
            nbyte = nbyte + 1;
        end
    end
endmodule
