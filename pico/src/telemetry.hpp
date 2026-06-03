#pragma once

namespace telemetry {

// Initialize ADC for battery measurement.
void init_adc();

// Read battery voltage, format and send STAT frame over UART0:
// STAT batt=<float> dist=0 up=1\n
void send_stat_frame();

// Print one STAT line on USB (service command STAT? only).
void print_stat_usb();

}  // namespace telemetry
