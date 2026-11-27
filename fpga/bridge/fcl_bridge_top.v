// Bridge-only FPGA design: fcl_bridge.v on the board's pins, nothing else (no camera, no LCD).
// For first bring-up of the sensors, buttons, ADC and servos from the ESP32.  The unit itself runs the full
// design (fpga/full/fcl_top.v).  Pins: fcl_bridge_top.lpf.   Build: python fpga/bridge/build_bridge.py
module fcl_bridge_top (
    input  wire clk_25mhz,
    input  wire esp_rx,          // WIFI_TXD: from the ESP32 (GPIO11)
    output wire esp_tx,          // WIFI_RXD: to the ESP32 (GPIO12)
    inout  wire i2c_scl,
    inout  wire i2c_sda,
    output wire adc_cnv,
    output wire adc_sck,
    output wire adc_din,
    input  wire adc_sdo,
    input  wire btn_pwr_n,
    input  wire btn1_n,
    input  wire btn2_n,
    input  wire imu_int1,
    input  wire imu_int2,
    input  wire mag_drdy,
    input  wire baro_int,
    input  wire tof_int,
    output wire led0,
    output wire led1,
    output wire tof_xshut,
    output wire shutdown,
    output wire srv_pwm1,
    output wire srv_pwm2,
    output wire srv_pwm3,
    output wire srv_pwm4,
    output wire srv_pwm5,
    output wire srv_pwm6
);
    reg [7:0] por = 0;                           // hold reset for 256 clocks after configuration
    wire rst = !por[7];
    always @(posedge clk_25mhz) if (rst) por <= por + 1;

    wire scl_oe, sda_oe;
    assign i2c_scl = scl_oe ? 1'b0 : 1'bz;       // open drain; the board has the pull-ups (R76, R77)
    assign i2c_sda = sda_oe ? 1'b0 : 1'bz;
    wire [5:0] servo;
    wire [1:0] led;
    assign {srv_pwm6, srv_pwm5, srv_pwm4, srv_pwm3, srv_pwm2, srv_pwm1} = servo;
    assign {led1, led0} = led;

    fcl_bridge #(.CLK_HZ(25000000), .BAUD(921600)) bridge (
        .clk(clk_25mhz), .rst(rst), .uart_rx(esp_rx), .uart_tx(esp_tx),
        .scl_i(i2c_scl), .scl_oe(scl_oe), .sda_i(i2c_sda), .sda_oe(sda_oe),
        .adc_cnv(adc_cnv), .adc_sck(adc_sck), .adc_din(adc_din), .adc_sdo(adc_sdo),
        .btn_n({btn2_n, btn1_n, btn_pwr_n}), .int_in({tof_int, baro_int, mag_drdy, imu_int2, imu_int1}),
        .led(led), .tof_xshut(tof_xshut), .shutdown(shutdown), .servo(servo),
        .osd_we(), .osd_addr(), .osd_data(), .dot_x(), .dot_y(), .dot_on(), .dot_inside());
endmodule
