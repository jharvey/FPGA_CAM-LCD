// FCL bridge: lets the ESP32-S3 reach everything that is wired to the FPGA, over the two-wire serial link.
// No CPU: a frame parser, one executor state machine, an I2C master, the AD7689 read-out, six servo outputs,
// button debounce and the write port of the LCD overlay (fpga/osd/fcl_osd.v).
//
// Link: UART 8N1 at BAUD.  Frame: A5 5A | type | len | payload | CRC16-CCITT-FALSE (LE) over type, len, payload.
// Every command is answered by a frame of the same type; the host sends one command and waits for its answer.
//
//   0x20 PING      -                                              -> version, t_us(4)
//   0x21 I2C       addr7, nreg(0-2), wlen(0-16), rlen(0-16),
//                  reg[nreg] (high byte first), wdata[wlen]         -> data[rlen], status
//   0x22 SCHED     slot(0-3), period(2, x100 us, 0 = off), addr7,
//                  nreg, reg_hi, reg_lo, rlen(1-16)                 -> status      (periodic I2C read, see 0x30)
//   0x23 ADC       period(2, x100 us, 0 = off), cfg(2)              -> status      (AD7689 scan of 8 inputs, see 0x31)
//   0x24 SERVO     channel(0-5), pulse_us(2, 0 = off)               -> status
//   0x25 OUT       mask, value   bit 0 LED0, 1 LED1, 2 TOF_XSHUT, 3 SHUTDOWN   -> status
//   0x26 OSD_TEXT  address(2) = row * 30 + col, characters          -> status
//   0x27 OSD_DOT   x(2), y(2), flags (bit 0 on, bit 1 inside)       -> status
//   0x28 INPUTS    -                                              -> as 0x32
// Sent without being asked:
//   0x30 SAMPLE    slot, t_us(4), data[rlen], status      a scheduled read, time-stamped when it started
//   0x31 ADC       t_us(4), 8 x code(2)                   inputs 0..7
//   0x32 INPUTS    t_us(4), buttons (bit 0 PWR, 1 B1, 2 B2; 1 = pressed), interrupt lines (raw levels)
// status: 0 = ok, 1 = no acknowledge from the device, 0xFF = unknown command.  Numbers are little-endian.
//
// Safety net: holding the power button for 8 s raises SHUTDOWN even if the ESP32 never answers.
module fcl_bridge #(
    parameter CLK_HZ = 25000000,
    parameter BAUD   = 921600
) (
    input  wire        clk,
    input  wire        rst,
    // link to the ESP32
    input  wire        uart_rx,
    output wire        uart_tx,
    // sensor I2C bus (open drain: drive low when *_oe = 1)
    input  wire        scl_i,
    output reg         scl_oe,
    input  wire        sda_i,
    output reg         sda_oe,
    // AD7689
    output reg         adc_cnv,
    output reg         adc_sck,
    output reg         adc_din,
    input  wire        adc_sdo,
    // buttons (active low) and interrupt lines
    input  wire [2:0]  btn_n,            // 0 power, 1 B1, 2 B2
    input  wire [4:0]  int_in,           // imu_int1, imu_int2, mag_drdy, baro_int, tof_int
    // outputs
    output reg  [1:0]  led,
    output reg         tof_xshut,
    output wire        shutdown,
    output reg  [5:0]  servo,
    // LCD overlay
    output reg         osd_we,
    output reg  [8:0]  osd_addr,
    output reg  [6:0]  osd_data,
    output reg  [9:0]  dot_x,
    output reg  [9:0]  dot_y,
    output reg         dot_on,
    output reg         dot_inside
);
    localparam integer UDIV = (CLK_HZ + BAUD / 2) / BAUD;         // clocks per UART bit
    localparam integer USDIV = CLK_HZ / 1000000;                  // clocks per microsecond
    localparam integer QDIV = (CLK_HZ + 1599999) / 1600000;       // quarter of a 400 kHz I2C bit
    localparam integer ADIV = (CLK_HZ + 3999999) / 4000000;       // half of a 2 MHz ADC clock
    localparam integer CNVN = CLK_HZ / 250000;                    // 4 us conversion time

    function [15:0] crc8;
        input [15:0] c;
        input [7:0]  d;
        integer k;
        reg [15:0] v;
        begin
            v = c ^ {d, 8'h00};
            for (k = 0; k < 8; k = k + 1) v = v[15] ? ((v << 1) ^ 16'h1021) : (v << 1);
            crc8 = v;
        end
    endfunction

    // ---------------------------------------------------------------- time base
    reg [7:0]  us_div;
    reg        us_tick;
    reg [31:0] t_us;
    reg [6:0]  t100;
    reg        tick100;                                           // every 100 us
    reg [3:0]  t1k;
    reg        tick1k;
    always @(posedge clk) begin
        us_tick <= 0; tick100 <= 0; tick1k <= 0;
        if (rst) begin us_div <= 0; t_us <= 0; t100 <= 0; t1k <= 0; end
        else if (us_div == USDIV - 1) begin
            us_div <= 0; us_tick <= 1; t_us <= t_us + 1;
            if (t100 == 99) begin
                t100 <= 0; tick100 <= 1;
                if (t1k == 9) begin t1k <= 0; tick1k <= 1; end else t1k <= t1k + 1;
            end else t100 <= t100 + 1;
        end else us_div <= us_div + 1;
    end

    // ---------------------------------------------------------------- UART receiver
    reg [2:0]  rx_sync;
    reg [15:0] rx_cnt;
    reg [3:0]  rx_bit;
    reg [7:0]  rx_sr, rx_data;
    reg        rx_busy, rx_stb;
    always @(posedge clk) begin
        rx_sync <= {rx_sync[1:0], uart_rx};
        rx_stb <= 0;
        if (rst) begin rx_busy <= 0; end
        else if (!rx_busy) begin
            if (rx_sync[2:1] == 2'b10) begin rx_busy <= 1; rx_cnt <= UDIV + UDIV / 2 - 2; rx_bit <= 0; end
        end else if (rx_cnt == 0) begin
            rx_cnt <= UDIV - 1;
            if (rx_bit == 8) begin rx_busy <= 0; if (rx_sync[1]) begin rx_data <= rx_sr; rx_stb <= 1; end end
            else begin rx_sr <= {rx_sync[1], rx_sr[7:1]}; rx_bit <= rx_bit + 1; end
        end else rx_cnt <= rx_cnt - 1;
    end

    // ---------------------------------------------------------------- command frame parser
    reg [7:0]  cmd [0:63];                // payload: one read port (cmd_q)
    reg [7:0]  hd [0:7];                  // its first 8 bytes, readable at once
    reg [5:0]  cmd_ra;
    wire [7:0] cmd_q = cmd[cmd_ra];
    reg [7:0]  cmd_type, cmd_len, p_type, p_len, p_n;
    reg [15:0] p_crc, p_rx;
    reg [2:0]  p_state;
    reg        cmd_ready, cmd_done;
    always @(posedge clk) begin
        if (rst) begin p_state <= 0; cmd_ready <= 0; end
        else begin
            if (cmd_done) cmd_ready <= 0;
            if (rx_stb) case (p_state)
                0: if (rx_data == 8'hA5 && !cmd_ready) p_state <= 1;
                1: p_state <= (rx_data == 8'h5A) ? 2 : (rx_data == 8'hA5 ? 1 : 0);
                2: begin p_type <= rx_data; p_crc <= crc8(16'hFFFF, rx_data); p_state <= 3; end
                3: begin
                    p_len <= rx_data; p_n <= 0; p_crc <= crc8(p_crc, rx_data);
                    p_state <= (rx_data > 64) ? 0 : (rx_data == 0 ? 5 : 4);
                end
                4: begin
                    cmd[p_n[5:0]] <= rx_data; if (p_n < 8) hd[p_n[2:0]] <= rx_data; p_crc <= crc8(p_crc, rx_data); p_n <= p_n + 1;
                    if (p_n + 1 == p_len) p_state <= 5;
                end
                5: begin p_rx[7:0] <= rx_data; p_state <= 6; end
                6: begin
                    p_state <= 0;
                    if ({rx_data, p_rx[7:0]} == p_crc) begin cmd_type <= p_type; cmd_len <= p_len; cmd_ready <= 1; end
                end
                default: p_state <= 0;
            endcase
        end
    end

    // ---------------------------------------------------------------- transmit FIFO and UART transmitter
    reg [7:0]  fifo [0:1023];
    reg [9:0]  f_wr, f_rd;
    wire       f_empty = (f_wr == f_rd);
    wire       f_full  = (f_wr + 10'd1 == f_rd);
    reg        f_put;
    reg [7:0]  f_din;
    reg [7:0]  f_dout;
    reg [15:0] tx_cnt;
    reg [3:0]  tx_bit;
    reg [9:0]  tx_sr;
    reg        tx_busy, tx_load;
    assign uart_tx = tx_busy ? tx_sr[0] : 1'b1;
    always @(posedge clk) begin
        if (f_put) begin fifo[f_wr] <= f_din; end
        f_dout <= fifo[f_rd];
        if (rst) begin f_wr <= 0; f_rd <= 0; tx_busy <= 0; tx_load <= 0; end
        else begin
            if (f_put) f_wr <= f_wr + 1;
            if (!tx_busy && !tx_load && !f_empty) tx_load <= 1;                    // one clock for the RAM read
            else if (tx_load) begin
                tx_load <= 0; tx_busy <= 1; tx_sr <= {1'b1, f_dout, 1'b0}; tx_cnt <= UDIV - 1; tx_bit <= 0; f_rd <= f_rd + 1;
            end else if (tx_busy) begin
                if (tx_cnt == 0) begin
                    tx_cnt <= UDIV - 1; tx_sr <= {1'b1, tx_sr[9:1]};
                    if (tx_bit == 9) tx_busy <= 0; else tx_bit <= tx_bit + 1;
                end else tx_cnt <= tx_cnt - 1;
            end
        end
    end

    // ---------------------------------------------------------------- I2C byte engine
    localparam OP_START = 2'd0, OP_STOP = 2'd1, OP_BYTE = 2'd2;
    reg        i2c_go, i2c_done, i2c_run;
    reg [1:0]  i2c_op;
    reg [8:0]  i2c_tx;                    // 8 data bits + the acknowledge slot (1 = released)
    reg [8:0]  i2c_rx;
    reg [8:0]  i2c_sh;                    // the engine's own copy, shifted out
    reg [3:0]  i2c_bit;
    reg [1:0]  i2c_q;
    reg [7:0]  i2c_cnt;
    reg [9:0]  i2c_wait;
    reg [1:0]  scl_s, sda_s;
    always @(posedge clk) begin
        scl_s <= {scl_s[0], scl_i}; sda_s <= {sda_s[0], sda_i};
        i2c_done <= 0;
        if (rst) begin i2c_run <= 0; scl_oe <= 0; sda_oe <= 0; end
        else if (!i2c_run) begin
            if (i2c_go) begin i2c_run <= 1; i2c_sh <= i2c_tx; i2c_q <= 0; i2c_bit <= 0; i2c_cnt <= QDIV - 1; i2c_wait <= 0; end
        end else if (i2c_cnt != 0) i2c_cnt <= i2c_cnt - 1;
        else if (scl_oe == 0 && scl_s[1] == 0 && i2c_wait != 10'h3FF) i2c_wait <= i2c_wait + 1;   // clock stretching
        else begin
            i2c_cnt <= QDIV - 1; i2c_wait <= 0; i2c_q <= i2c_q + 1;
            case (i2c_op)
                OP_START: case (i2c_q)
                    0: sda_oe <= 0;
                    1: scl_oe <= 0;
                    2: sda_oe <= 1;
                    3: begin scl_oe <= 1; i2c_run <= 0; i2c_done <= 1; end
                endcase
                OP_STOP: case (i2c_q)
                    0: sda_oe <= 1;
                    1: scl_oe <= 0;
                    2: sda_oe <= 0;
                    3: begin i2c_run <= 0; i2c_done <= 1; end
                endcase
                default: case (i2c_q)
                    0: sda_oe <= !i2c_sh[8];
                    1: scl_oe <= 0;
                    2: i2c_rx <= {i2c_rx[7:0], sda_s[1]};
                    3: begin
                        scl_oe <= 1; i2c_sh <= {i2c_sh[7:0], 1'b1};
                        if (i2c_bit == 8) begin i2c_run <= 0; i2c_done <= 1; end else i2c_bit <= i2c_bit + 1;
                    end
                endcase
            endcase
        end
    end

    // ---------------------------------------------------------------- schedules
    reg [15:0] s_period [0:3];
    reg [15:0] s_cnt [0:3];
    reg [6:0]  s_addr [0:3];
    reg [1:0]  s_nreg [0:3];
    reg [15:0] s_reg [0:3];
    reg [4:0]  s_rlen [0:3];
    reg [3:0]  s_pend, s_clear;
    reg [15:0] a_period, a_cnt, a_cfg;
    reg        a_pend, a_clear;
    reg        s_set;
    reg [2:0]  s_set_i;
    integer    si;
    always @(posedge clk) begin
        if (rst) begin
            s_pend <= 0; a_pend <= 0; a_period <= 0;
            for (si = 0; si < 4; si = si + 1) begin s_period[si] <= 0; s_cnt[si] <= 0; end
        end else begin
            s_pend <= s_pend & ~s_clear;
            if (a_clear) a_pend <= 0;
            if (tick100) begin
                for (si = 0; si < 4; si = si + 1) if (s_period[si] != 0) begin
                    if (s_cnt[si] <= 1) begin s_cnt[si] <= s_period[si]; s_pend[si] <= 1; end
                    else s_cnt[si] <= s_cnt[si] - 1;
                end
                if (a_period != 0) begin
                    if (a_cnt <= 1) begin a_cnt <= a_period; a_pend <= 1; end else a_cnt <= a_cnt - 1;
                end
            end
            if (s_set) begin                                       // written by the executor (commands 0x22 / 0x23)
                if (s_set_i == 4) begin a_period <= {hd[1], hd[0]}; a_cnt <= {hd[1], hd[0]}; a_cfg <= {hd[3], hd[2]}; end
                else begin
                    s_period[s_set_i[1:0]] <= {hd[2], hd[1]}; s_cnt[s_set_i[1:0]] <= {hd[2], hd[1]};
                    s_addr[s_set_i[1:0]] <= hd[3][6:0]; s_nreg[s_set_i[1:0]] <= hd[4][1:0];
                    s_reg[s_set_i[1:0]] <= {hd[5], hd[6]}; s_rlen[s_set_i[1:0]] <= hd[7][4:0];
                end
            end
        end
    end

    // ---------------------------------------------------------------- inputs
    reg [2:0]  btn_s0, btn_s1, btn_db, btn_sent;
    reg [2:0]  btn_c [0:2];
    reg [4:0]  int_s0, int_s1;
    reg [12:0] hold_ms;
    reg        force_off, out_shutdown, in_pend, in_clear;
    integer    bi;
    assign shutdown = out_shutdown | force_off;
    always @(posedge clk) begin
        btn_s0 <= ~btn_n; btn_s1 <= btn_s0; int_s0 <= int_in; int_s1 <= int_s0;
        if (rst) begin btn_db <= 0; btn_sent <= 0; in_pend <= 0; hold_ms <= 0; force_off <= 0;
            for (bi = 0; bi < 3; bi = bi + 1) btn_c[bi] <= 0; end
        else begin
            if (in_clear) begin in_pend <= 0; btn_sent <= btn_db; end
            else if (btn_db != btn_sent) in_pend <= 1;
            if (tick1k) begin
                for (bi = 0; bi < 3; bi = bi + 1) begin                // 5 equal samples at 1 kHz
                    if (btn_s1[bi] == btn_db[bi]) btn_c[bi] <= 0;
                    else if (btn_c[bi] == 4) begin btn_db[bi] <= btn_s1[bi]; btn_c[bi] <= 0; end
                    else btn_c[bi] <= btn_c[bi] + 1;
                end
                if (!btn_db[0]) hold_ms <= 0;
                else if (hold_ms == 13'd7999) force_off <= 1;
                else hold_ms <= hold_ms + 1;
            end
        end
    end

    // ---------------------------------------------------------------- servos: 20 ms frame, width in microseconds
    reg [14:0] pwm_t;
    reg [11:0] sv_us [0:5];
    integer    pi;
    always @(posedge clk) begin
        if (rst) pwm_t <= 0;
        else if (us_tick) pwm_t <= (pwm_t == 15'd19999) ? 15'd0 : pwm_t + 1;
        for (pi = 0; pi < 6; pi = pi + 1) servo[pi] <= (pwm_t < {3'b000, sv_us[pi]});
    end

    // ---------------------------------------------------------------- executor
    // A frame to send = up to 6 prefix bytes held in registers (slot, time stamp, status ...) followed by
    // the data bytes collected in a small RAM (I2C read data, ADC codes).
    localparam E_IDLE = 0, E_CMD = 1, E_I2C_S = 2, E_I2C_AW = 3, E_I2C_R0 = 4, E_I2C_R1 = 5, E_I2C_WD = 6, E_I2C_RS = 7,
               E_I2C_AR = 8, E_I2C_RD = 9, E_I2C_P = 10, E_PAD = 11, E_FIN = 12, E_SEND = 13, E_SENDW = 14,
               E_ADC_CNV = 15, E_ADC_LO = 16, E_ADC_HI = 17, E_ADC_NEXT = 18, E_OSD = 19, E_ADC_B2 = 20;
    reg [4:0]  e;
    reg [7:0]  pre [0:5];
    reg [2:0]  pre_n;
    reg [7:0]  fb [0:31];
    reg        fb_we;
    reg [4:0]  fb_wa;
    reg [7:0]  fb_wd;
    reg [5:0]  fbn, fb_end;
    reg [7:0]  fb_type;
    reg        job_cmd, op_on, x_fail;
    reg [6:0]  x_addr;
    reg [1:0]  x_nreg;
    reg [15:0] x_reg;
    reg [4:0]  x_wlen, x_rlen, x_i;
    reg [5:0]  x_wptr;
    reg [3:0]  a_k;
    reg [4:0]  a_bit;
    reg [15:0] a_sr, a_out, a_div;
    reg [5:0]  o_i;
    // frame sender
    reg [5:0]  sn;
    reg [2:0]  sh, pn;
    reg [15:0] s_crc;
    reg        snd_go, snd_busy;
    integer    ci;

    wire [1:0] first_slot = s_pend[0] ? 2'd0 : s_pend[1] ? 2'd1 : s_pend[2] ? 2'd2 : 2'd3;
    wire [7:0] fb_q = fb[sn[4:0]];
    wire [7:0] s_len = {2'b00, fbn} + {5'b0, pre_n};
    always @(posedge clk) if (fb_we) fb[fb_wa] <= fb_wd;
    always @* cmd_ra = (e == E_OSD) ? o_i : x_wptr;

    task i2c_issue;
        input [1:0] op;
        input [8:0] data;
        begin i2c_op <= op; i2c_tx <= data; i2c_go <= 1; op_on <= 1; end
    endtask
    task stamp;                                                    // time stamp into prefix bytes k..k+3
        input [2:0] k;
        begin pre[k] <= t_us[7:0]; pre[k + 3'd1] <= t_us[15:8]; pre[k + 3'd2] <= t_us[23:16]; pre[k + 3'd3] <= t_us[31:24]; end
    endtask
    task put;                                                      // one data byte into the frame
        input [7:0] d;
        begin fb_we <= 1; fb_wa <= fbn[4:0]; fb_wd <= d; fbn <= fbn + 1; end
    endtask

    always @(posedge clk) begin
        i2c_go <= 0; f_put <= 0; cmd_done <= 0; s_clear <= 0; a_clear <= 0; in_clear <= 0; s_set <= 0; osd_we <= 0; snd_go <= 0;
        fb_we <= 0;
        if (rst) begin
            e <= E_IDLE; op_on <= 0; snd_busy <= 0; adc_cnv <= 1; adc_sck <= 0; adc_din <= 0;
            led <= 0; tof_xshut <= 0; out_shutdown <= 0; dot_on <= 0; dot_inside <= 0; dot_x <= 240; dot_y <= 240;
            for (ci = 0; ci < 6; ci = ci + 1) sv_us[ci] <= 0;
        end else begin
            // ---- frame sender: A5 5A type len prefix data crc
            if (snd_go) begin snd_busy <= 1; sh <= 0; sn <= 0; pn <= 0; s_crc <= 16'hFFFF; end
            else if (snd_busy && !f_full && !f_put) begin
                f_put <= 1;
                case (sh)
                    0: begin f_din <= 8'hA5; sh <= 1; end
                    1: begin f_din <= 8'h5A; sh <= 2; end
                    2: begin f_din <= fb_type; s_crc <= crc8(s_crc, fb_type); sh <= 3; end
                    3: begin f_din <= s_len; s_crc <= crc8(s_crc, s_len); sh <= (pre_n != 0) ? 4 : (fbn != 0) ? 5 : 6; end
                    4: begin f_din <= pre[pn]; s_crc <= crc8(s_crc, pre[pn]); pn <= pn + 1; if (pn + 3'd1 == pre_n) sh <= (fbn != 0) ? 5 : 6; end
                    5: begin f_din <= fb_q; s_crc <= crc8(s_crc, fb_q); sn <= sn + 1; if (sn + 6'd1 == fbn) sh <= 6; end
                    6: begin f_din <= s_crc[7:0]; sh <= 7; end
                    default: begin f_din <= s_crc[15:8]; snd_busy <= 0; end
                endcase
            end

            case (e)
            E_IDLE: begin
                job_cmd <= 0; x_fail <= 0; op_on <= 0; fbn <= 0; pre_n <= 0;
                if (s_pend != 0) begin
                    s_clear[first_slot] <= 1; fb_type <= 8'h30;
                    pre[0] <= {6'b0, first_slot}; stamp(3'd1); pre_n <= 5; fb_end <= {1'b0, s_rlen[first_slot]};
                    x_addr <= s_addr[first_slot]; x_nreg <= s_nreg[first_slot]; x_reg <= s_reg[first_slot];
                    x_wlen <= 0; x_rlen <= s_rlen[first_slot]; x_i <= 0;
                    e <= E_I2C_S;
                end else if (a_pend) begin
                    a_clear <= 1; fb_type <= 8'h31; stamp(3'd0); pre_n <= 4;
                    a_k <= 0; a_div <= CNVN; adc_cnv <= 1; e <= E_ADC_CNV;
                end else if (in_pend) begin
                    in_clear <= 1; fb_type <= 8'h32; stamp(3'd0); pre[4] <= {5'b0, btn_db}; pre[5] <= {3'b0, int_s1}; pre_n <= 6; e <= E_SEND;
                end else if (cmd_ready && !cmd_done) begin job_cmd <= 1; e <= E_CMD; end
            end

            E_CMD: begin
                fb_type <= cmd_type; pre[0] <= 8'h00; pre_n <= 1; e <= E_SEND;
                case (cmd_type)
                    8'h20: begin pre[0] <= 8'd1; stamp(3'd1); pre_n <= 5; end
                    8'h21: begin
                        x_addr <= hd[0][6:0]; x_nreg <= hd[1][1:0]; x_wlen <= hd[2][4:0]; x_rlen <= hd[3][4:0];
                        x_reg <= (hd[1][1:0] == 2) ? {hd[4], hd[5]} : {8'h00, hd[4]};
                        x_wptr <= 6'd4 + {4'b0, hd[1][1:0]}; x_i <= 0; pre_n <= 0; fb_end <= {1'b0, hd[3][4:0]}; e <= E_I2C_S;
                    end
                    8'h22: begin if (hd[0] < 4) begin s_set <= 1; s_set_i <= hd[0][2:0]; end else pre[0] <= 8'h01; end
                    8'h23: begin s_set <= 1; s_set_i <= 3'd4; end
                    8'h24: begin if (hd[0] < 6) sv_us[hd[0][2:0]] <= {hd[2][3:0], hd[1]}; else pre[0] <= 8'h01; end
                    8'h25: begin
                        if (hd[0][0]) led[0] <= hd[1][0];
                        if (hd[0][1]) led[1] <= hd[1][1];
                        if (hd[0][2]) tof_xshut <= hd[1][2];
                        if (hd[0][3]) out_shutdown <= hd[1][3];
                    end
                    8'h26: begin o_i <= 2; e <= E_OSD; end
                    8'h27: begin dot_x <= {hd[1][1:0], hd[0]}; dot_y <= {hd[3][1:0], hd[2]}; dot_on <= hd[4][0]; dot_inside <= hd[4][1]; end
                    8'h28: begin fb_type <= 8'h32; stamp(3'd0); pre[4] <= {5'b0, btn_db}; pre[5] <= {3'b0, int_s1}; pre_n <= 6; end
                    default: pre[0] <= 8'hFF;
                endcase
            end

            E_OSD: begin                                            // one character per clock into the overlay memory
                if ({2'b0, o_i} >= cmd_len) e <= E_SEND;
                else begin
                    osd_we <= 1; osd_addr <= {hd[1][0], hd[0]} + {3'b0, o_i} - 9'd2; osd_data <= cmd_q[6:0]; o_i <= o_i + 1;
                end
            end

            // ---- I2C transaction: [START addr+W reg.. wdata..] [START addr+R data..] STOP
            E_I2C_S: begin
                if (x_nreg == 0 && x_wlen == 0 && x_rlen != 0) e <= E_I2C_RS;
                else if (!op_on) i2c_issue(OP_START, 9'h1FF);
                else if (i2c_done) begin op_on <= 0; e <= E_I2C_AW; end
            end
            E_I2C_AW: begin
                if (!op_on) i2c_issue(OP_BYTE, {x_addr, 1'b0, 1'b1});
                else if (i2c_done) begin op_on <= 0; if (i2c_rx[0]) begin x_fail <= 1; e <= E_I2C_P; end else e <= E_I2C_R0; end
            end
            E_I2C_R0: begin
                if (x_nreg != 2) e <= E_I2C_R1;
                else if (!op_on) i2c_issue(OP_BYTE, {x_reg[15:8], 1'b1});
                else if (i2c_done) begin op_on <= 0; if (i2c_rx[0]) begin x_fail <= 1; e <= E_I2C_P; end else e <= E_I2C_R1; end
            end
            E_I2C_R1: begin
                if (x_nreg == 0) e <= E_I2C_WD;
                else if (!op_on) i2c_issue(OP_BYTE, {x_reg[7:0], 1'b1});
                else if (i2c_done) begin op_on <= 0; if (i2c_rx[0]) begin x_fail <= 1; e <= E_I2C_P; end else e <= E_I2C_WD; end
            end
            E_I2C_WD: begin
                if (x_i == x_wlen) begin x_i <= 0; e <= (x_rlen != 0) ? E_I2C_RS : E_I2C_P; end
                else if (!op_on) i2c_issue(OP_BYTE, {cmd_q, 1'b1});
                else if (i2c_done) begin
                    op_on <= 0; x_i <= x_i + 1; x_wptr <= x_wptr + 1;
                    if (i2c_rx[0]) begin x_fail <= 1; e <= E_I2C_P; end
                end
            end
            E_I2C_RS: begin
                if (!op_on) i2c_issue(OP_START, 9'h1FF);
                else if (i2c_done) begin op_on <= 0; e <= E_I2C_AR; end
            end
            E_I2C_AR: begin
                if (!op_on) i2c_issue(OP_BYTE, {x_addr, 1'b1, 1'b1});
                else if (i2c_done) begin op_on <= 0; if (i2c_rx[0]) begin x_fail <= 1; e <= E_I2C_P; end else e <= E_I2C_RD; end
            end
            E_I2C_RD: begin
                if (x_i == x_rlen) e <= E_I2C_P;
                else if (!op_on) i2c_issue(OP_BYTE, {8'hFF, (x_i + 5'd1 == x_rlen)});      // acknowledge all but the last
                else if (i2c_done) begin op_on <= 0; put(i2c_rx[8:1]); x_i <= x_i + 1; end
            end
            E_I2C_P: begin
                if (!op_on) i2c_issue(OP_STOP, 9'h1FF);
                else if (i2c_done) begin op_on <= 0; e <= E_PAD; end
            end
            E_PAD: begin
                if (fbn < fb_end) put(8'h00);
                else e <= E_FIN;
            end
            E_FIN: begin put({7'b0, x_fail}); e <= E_SEND; end

            // ---- AD7689: ten 16-bit frames, the result of a conversion comes out two frames later
            E_ADC_CNV: begin
                if (a_div != 0) a_div <= a_div - 1;
                else begin
                    adc_cnv <= 0; a_bit <= 0; a_div <= ADIV - 1; adc_sck <= 0;
                    a_sr <= {a_cfg[13:10], (a_k < 8) ? a_k[2:0] : 3'b000, a_cfg[6:0], 2'b00};
                    e <= E_ADC_LO;
                end
            end
            E_ADC_LO: begin                                         // clock low: put the next configuration bit out
                adc_din <= a_sr[15];
                if (a_div != 0) a_div <= a_div - 1;
                else begin adc_sck <= 1; a_out <= {a_out[14:0], adc_sdo}; a_div <= ADIV - 1; e <= E_ADC_HI; end
            end
            E_ADC_HI: begin
                if (a_div != 0) a_div <= a_div - 1;
                else begin
                    adc_sck <= 0; a_sr <= {a_sr[14:0], 1'b0}; a_div <= ADIV - 1;
                    if (a_bit == 15) e <= E_ADC_NEXT; else begin a_bit <= a_bit + 1; e <= E_ADC_LO; end
                end
            end
            E_ADC_NEXT: begin
                adc_cnv <= 1; a_div <= CNVN;
                if (a_k >= 2) begin put(a_out[7:0]); e <= E_ADC_B2; end
                else begin a_k <= a_k + 1; e <= E_ADC_CNV; end
            end
            E_ADC_B2: begin
                put(a_out[15:8]); a_k <= a_k + 1;
                e <= (a_k == 9) ? E_SEND : E_ADC_CNV;
            end

            E_SEND: begin snd_go <= 1; e <= E_SENDW; end
            E_SENDW: if (!snd_go && !snd_busy) begin
                if (job_cmd) cmd_done <= 1;
                e <= E_IDLE;
            end
            default: e <= E_IDLE;
            endcase
        end
    end
endmodule
