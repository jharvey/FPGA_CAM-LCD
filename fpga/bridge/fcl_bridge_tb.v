// Test bench for fcl_bridge.v, driven by fpga/bridge/test_bridge.py.
//   tb_stim.txt   lines:  D <microseconds>   wait
//                         B <hex byte>        send one byte on the UART
//                         P <mask>            hold buttons (bit 0 PWR, 1 B1, 2 B2)
//                         I <mask>            interrupt line levels
//                         E                   finish
//   tb_out.txt    every byte the bridge sent, hex, one per line
//   stdout        OSD <addr> <char>, DOT ..., SERVO <ch> <us>, OUT ...  for the Python side to check
// Models: four I2C devices (0x68, 0x1E, 0x5C with 8-bit registers, 0x29 with 16-bit registers) and the AD7689.
`timescale 1ns/1ps
module fcl_bridge_tb;
    localparam real BIT_NS = 1.0e9 / 921600.0;
    reg clk = 0, rst = 1;
    always #20 clk = ~clk;                               // 25 MHz

    reg        host_tx = 1;
    wire       dut_tx;
    wire       scl_oe, sda_oe;
    reg        slave_sda_low = 0;
    wire       scl = ~scl_oe;
    wire       sda = ~(sda_oe | slave_sda_low);
    wire       adc_cnv, adc_sck, adc_din;
    reg        adc_sdo = 0;
    reg  [2:0] btn = 0;
    reg  [4:0] ints = 0;
    wire [1:0] led;
    wire       tof_xshut, shutdown;
    wire [5:0] servo;
    wire       osd_we;
    wire [8:0] osd_addr;
    wire [6:0] osd_data;
    wire [9:0] dot_x, dot_y;
    wire       dot_on, dot_inside;

    fcl_bridge dut (.clk(clk), .rst(rst), .uart_rx(host_tx), .uart_tx(dut_tx),
        .scl_i(scl), .scl_oe(scl_oe), .sda_i(sda), .sda_oe(sda_oe),
        .adc_cnv(adc_cnv), .adc_sck(adc_sck), .adc_din(adc_din), .adc_sdo(adc_sdo),
        .btn_n(~btn), .int_in(ints), .led(led), .tof_xshut(tof_xshut), .shutdown(shutdown), .servo(servo),
        .osd_we(osd_we), .osd_addr(osd_addr), .osd_data(osd_data),
        .dot_x(dot_x), .dot_y(dot_y), .dot_on(dot_on), .dot_inside(dot_inside));

    // ---------------------------------------------------------------- I2C devices
    reg [7:0]  mem8 [0:767];                             // three devices x 256 registers
    reg [7:0]  mem16 [0:65535];
    integer    i;
    initial begin
        for (i = 0; i < 768; i = i + 1) mem8[i] = (i % 256) * 3 + (i / 256) * 17 + 1;
        for (i = 0; i < 65536; i = i + 1) mem16[i] = (i / 256) * 5 + (i % 256) * 7 + 41;
    end
    reg        active = 0, sending = 0, send_next = 0;
    reg [7:0]  sr = 0, txb = 0;
    integer    dev = -1, nbyte = 0, kb = -1;             // kb: which bit of the byte the next clock pulse carries (8 = acknowledge)
    reg [15:0] ptr = 0;

    function integer dev_of;
        input [6:0] a;
        begin dev_of = (a == 7'h68) ? 0 : (a == 7'h1E) ? 1 : (a == 7'h5C) ? 2 : (a == 7'h29) ? 3 : -1; end
    endfunction
    function [7:0] rd;
        input integer d;
        input [15:0] p;
        begin rd = (d == 3) ? mem16[p] : mem8[d * 256 + p[7:0]]; end
    endfunction

    always @(negedge sda) if (scl) begin active = 1; sending = 0; send_next = 0; kb = -1; nbyte = 0; slave_sda_low = 0; end   // START
    always @(posedge sda) if (scl) begin active = 0; sending = 0; slave_sda_low = 0; end                                    // STOP
    always @(posedge scl) if (active) begin
        if (!sending && kb >= 0 && kb < 8) sr = {sr[6:0], sda};
        if (sending && kb == 8 && sda) begin sending = 0; active = 0; end           // master did not acknowledge: done
    end
    always @(negedge scl) if (active) begin
        kb = (kb == 8) ? 0 : kb + 1;
        if (kb == 0 && send_next) begin sending = 1; send_next = 0; end
        if (!sending) begin
            if (kb < 8) slave_sda_low = 0;
            else begin                                                           // a byte is in: acknowledge it or not
                if (nbyte == 0) begin
                    dev = dev_of(sr[7:1]);
                    if (dev < 0) active = 0;
                    else begin slave_sda_low = 1; send_next = sr[0]; end
                end else begin
                    slave_sda_low = 1;
                    if (dev == 3 && nbyte == 1) ptr[15:8] = sr;
                    else if (dev == 3 && nbyte == 2) ptr[7:0] = sr;
                    else if (dev != 3 && nbyte == 1) ptr = {8'h00, sr};
                    else begin
                        if (dev == 3) mem16[ptr] = sr; else mem8[dev * 256 + ptr[7:0]] = sr;
                        ptr = ptr + 1;
                    end
                end
                nbyte = nbyte + 1;
            end
        end else begin
            if (kb == 0) begin txb = rd(dev, ptr); ptr = ptr + 1; end
            if (kb < 8) slave_sda_low = ~txb[7 - kb];
            else slave_sda_low = 0;                                              // release for the master's acknowledge
        end
    end

    // ---------------------------------------------------------------- AD7689
    reg [13:0] hist0 = 0, hist1 = 0;
    reg [15:0] a_in = 0, a_out = 0;
    always @(negedge adc_cnv) begin a_out = {1'b0, hist0[9:7], 12'h123}; adc_sdo = a_out[15]; end
    always @(posedge adc_sck) a_in = {a_in[14:0], adc_din};
    always @(negedge adc_sck) begin a_out = {a_out[14:0], 1'b0}; adc_sdo = a_out[15]; end
    always @(posedge adc_cnv) begin hist0 = hist1; hist1 = a_in[15:2]; end

    // ---------------------------------------------------------------- UART: bytes from the bridge
    integer fo;
    reg [7:0] rb;
    integer rk;
    always @(negedge dut_tx) begin
        #(BIT_NS * 1.5);
        for (rk = 0; rk < 8; rk = rk + 1) begin rb[rk] = dut_tx; #(BIT_NS); end
        $fwrite(fo, "%02x\n", rb);
        wait (dut_tx == 1);
    end

    // ---------------------------------------------------------------- what the outputs did
    always @(posedge clk) if (osd_we) $display("OSD %0d %0d", osd_addr, osd_data);
    realtime sv_t [0:5];
    genvar g;
    generate for (g = 0; g < 6; g = g + 1) begin : sv
        always @(posedge servo[g]) sv_t[g] = $realtime;
        always @(negedge servo[g]) if ($realtime > 1000) $display("SERVO %0d %0d", g, $rtoi(($realtime - sv_t[g]) / 1000.0 + 0.5));
    end endgenerate
    always @(led or tof_xshut or shutdown) if (!rst) $display("OUT %0d %0d %0d %0d", $rtoi($realtime / 1000.0), led, tof_xshut, shutdown);
    always @(dot_x or dot_y or dot_on or dot_inside) if (!rst) $display("DOT %0d %0d %0d %0d", dot_x, dot_y, dot_on, dot_inside);

    // ---------------------------------------------------------------- stimulus
    integer fi, n, val, bk;
    reg [8*8-1:0] op;
    initial begin
        fo = $fopen("tb_out.txt", "w");
        fi = $fopen("tb_stim.txt", "r");
        repeat (10) @(posedge clk);
        rst = 0;
        while (!$feof(fi)) begin
            n = $fscanf(fi, "%s %h\n", op, val);
            if (op == "D") #(val * 1000.0);
            else if (op == "B") begin
                host_tx = 0; #(BIT_NS);
                for (bk = 0; bk < 8; bk = bk + 1) begin host_tx = val[bk]; #(BIT_NS); end
                host_tx = 1; #(BIT_NS);
            end
            else if (op == "P") btn = val[2:0];
            else if (op == "I") ints = val[4:0];
            else if (op == "E") begin $fclose(fo); $finish; end
        end
        $fclose(fo);
        $finish;
    end
endmodule
