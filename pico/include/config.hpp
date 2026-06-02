#pragma once

#include <stdint.h>

namespace config {

// GPIO pin assignments (from PROJECT.md)
constexpr uint8_t UART_TX_PIN = 0;  // Pico GP0 -> Pi RX
constexpr uint8_t UART_RX_PIN = 1;  // Pico GP1 -> Pi TX

// MX1508 motor driver pins
constexpr uint8_t MOTOR_LEFT_IN1_PIN  = 2;  // GP2
constexpr uint8_t MOTOR_LEFT_IN2_PIN  = 3;  // GP3
constexpr uint8_t MOTOR_RIGHT_IN1_PIN = 4;  // GP4
constexpr uint8_t MOTOR_RIGHT_IN2_PIN = 5;  // GP5

// Servo pins
constexpr uint8_t SERVO_PAN_PIN  = 6;  // GP6
constexpr uint8_t SERVO_TILT_PIN = 7;  // GP7

// ADC battery sense
constexpr uint8_t BATT_ADC_INPUT = 0;   // ADC0 on GP26
constexpr float   BATT_VREF      = 3.3f;
constexpr uint16_t BATT_ADC_MAX  = 4095;  // 12-bit
constexpr float   BATT_DIVIDER_MULTIPLIER = 2.0f;  // 10k/10k -> x2

// Servo limits (degrees)
constexpr int16_t SERVO_PAN_MIN_DEG   = 10;
constexpr int16_t SERVO_PAN_MAX_DEG   = 170;
constexpr int16_t SERVO_TILT_MIN_DEG  = 30;
constexpr int16_t SERVO_TILT_MAX_DEG  = 150;
constexpr int16_t SERVO_PAN_CENTER_DEG  = 90;
constexpr int16_t SERVO_TILT_CENTER_DEG = 90;

// Watchdog / timing
constexpr uint32_t DRIVE_FAILSAFE_MS = 300;  // ~300 ms
constexpr uint32_t STAT_PERIOD_MS    = 200;  // 5 Hz

// Main loop tick (used for ramp and timers)
constexpr uint32_t MAIN_LOOP_PERIOD_MS = 10;  // 100 Hz loop

// Status LED blink
constexpr uint32_t STATUS_LED_TOGGLE_MS = 250;

// Motor control
constexpr int16_t DRIVE_INPUT_MIN = -100;
constexpr int16_t DRIVE_INPUT_MAX = 100;

// Max duty cycle for motors (protect MX1508 and motors)
constexpr float MOTOR_MAX_DUTY = 0.90f;  // 90%

// Ramping: maximum change of requested power per tick (in % of full scale)
constexpr int16_t MOTOR_RAMP_STEP = 5;  // change of up to 5/100 per MAIN_LOOP_PERIOD_MS

// Servo PWM configuration (50 Hz, 20 ms period)
constexpr uint32_t SERVO_PWM_FREQUENCY_HZ = 50;
constexpr uint16_t SERVO_PULSE_MIN_US     = 1000;
constexpr uint16_t SERVO_PULSE_MAX_US     = 2000;

// UART protocol
constexpr uint32_t UART_BAUD_RATE = 115200;

// UART line buffer
constexpr uint16_t UART_LINE_BUFFER_SIZE = 64;

// ADC averaging
constexpr uint8_t BATT_SAMPLES = 8;

// Hardware watchdog test (manual): if true, hang after N ms to validate reset path.
constexpr bool WDT_TEST_HANG_ENABLED = false;
constexpr uint32_t WDT_TEST_HANG_AFTER_MS = 10000;

}  // namespace config

