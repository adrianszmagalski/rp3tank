#include "servos.hpp"

#include <stdio.h>

#include "hardware/gpio.h"
#include "hardware/pwm.h"

#include "config.hpp"

namespace servos {

static uint32_t g_wrap = 0;
static uint slice = 0;
static uint chan_pan = 0;
static uint chan_tilt = 0;

static int16_t clamp_deg(int16_t v, int16_t lo, int16_t hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static uint16_t deg_to_pulse_us(int16_t deg, int16_t min_deg, int16_t max_deg) {
    const int16_t clamped = clamp_deg(deg, min_deg, max_deg);
    const int32_t span_deg = static_cast<int32_t>(max_deg - min_deg);
    const int32_t pos = static_cast<int32_t>(clamped - min_deg);
    const int32_t span_us = static_cast<int32_t>(config::SERVO_PULSE_MAX_US - config::SERVO_PULSE_MIN_US);
    const int32_t pulse = static_cast<int32_t>(config::SERVO_PULSE_MIN_US) +
                          (pos * span_us) / (span_deg == 0 ? 1 : span_deg);
    return static_cast<uint16_t>(pulse);
}

static void set_channel_pulse_us(uint channel, uint16_t pulse_us) {
    // We configured PWM to have 1 tick = 1 us and wrap = 20000-1 for 20 ms.
    uint32_t level = pulse_us;
    if (level > g_wrap) level = g_wrap;
    pwm_set_chan_level(slice, channel, level);
}

void init() {
    // Configure GPIO -> PWM for GP6/GP7 (same slice, channels A/B)
    gpio_set_function(config::SERVO_PAN_PIN, GPIO_FUNC_PWM);
    gpio_set_function(config::SERVO_TILT_PIN, GPIO_FUNC_PWM);

    slice = pwm_gpio_to_slice_num(config::SERVO_PAN_PIN);
    chan_pan = pwm_gpio_to_channel(config::SERVO_PAN_PIN);
    chan_tilt = pwm_gpio_to_channel(config::SERVO_TILT_PIN);

    // Aim for 50 Hz and 1 us resolution:
    // Use PWM clock = 1 MHz (clkdiv = 125 for 125 MHz sys clk).
    // Period 20 ms -> wrap = 20000-1.
    g_wrap = 20000 - 1;
    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_clkdiv(&cfg, 125.0f);
    pwm_config_set_wrap(&cfg, g_wrap);
    pwm_init(slice, &cfg, true);

    // Safe center
    set_pan_deg(config::SERVO_PAN_CENTER_DEG);
    set_tilt_deg(config::SERVO_TILT_CENTER_DEG);

    printf("[SERVOS] PWM init OK (50Hz, 1us ticks). Center set.\n");
}

void set_pan_deg(int16_t deg) {
    const uint16_t pulse = deg_to_pulse_us(deg, config::SERVO_PAN_MIN_DEG, config::SERVO_PAN_MAX_DEG);
    set_channel_pulse_us(chan_pan, pulse);
}

void set_tilt_deg(int16_t deg) {
    const uint16_t pulse = deg_to_pulse_us(deg, config::SERVO_TILT_MIN_DEG, config::SERVO_TILT_MAX_DEG);
    set_channel_pulse_us(chan_tilt, pulse);
}

}  // namespace servos

