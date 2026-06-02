#include "motors.hpp"

#include <stdio.h>

#include "hardware/gpio.h"
#include "hardware/pwm.h"

#include "config.hpp"

namespace motors {

struct MotorPins {
    uint8_t in1;
    uint8_t in2;
};

static constexpr MotorPins kLeft{config::MOTOR_LEFT_IN1_PIN, config::MOTOR_LEFT_IN2_PIN};
static constexpr MotorPins kRight{config::MOTOR_RIGHT_IN1_PIN, config::MOTOR_RIGHT_IN2_PIN};

static uint32_t g_pwm_wrap = 0;

static int16_t g_target_left = 0;
static int16_t g_target_right = 0;
static int16_t g_current_left = 0;
static int16_t g_current_right = 0;

static int16_t clamp_percent(int16_t v) {
    if (v < config::DRIVE_INPUT_MIN) return config::DRIVE_INPUT_MIN;
    if (v > config::DRIVE_INPUT_MAX) return config::DRIVE_INPUT_MAX;
    return v;
}

static int16_t approach(int16_t cur, int16_t tgt, int16_t step) {
    if (cur < tgt) {
        const int16_t next = static_cast<int16_t>(cur + step);
        return next > tgt ? tgt : next;
    }
    if (cur > tgt) {
        const int16_t next = static_cast<int16_t>(cur - step);
        return next < tgt ? tgt : next;
    }
    return cur;
}

static uint16_t percent_to_level(int16_t percent) {
    const int16_t mag = percent < 0 ? static_cast<int16_t>(-percent) : percent;
    const float norm = (static_cast<float>(mag) / 100.0f) * config::MOTOR_MAX_DUTY;
    const uint32_t lvl = static_cast<uint32_t>(norm * static_cast<float>(g_pwm_wrap));
    return static_cast<uint16_t>(lvl > g_pwm_wrap ? g_pwm_wrap : lvl);
}

static void set_motor_level(const MotorPins& pins, int16_t percent) {
    // percent: -100..100
    const uint slice1 = pwm_gpio_to_slice_num(pins.in1);
    const uint slice2 = pwm_gpio_to_slice_num(pins.in2);
    (void)slice2;
    // Both pins must be on the same slice for a clean pair; PROJECT.md mapping ensures it.
    const uint ch1 = pwm_gpio_to_channel(pins.in1);
    const uint ch2 = pwm_gpio_to_channel(pins.in2);

    if (percent == 0) {
        // Active brake: both inputs HIGH (100% duty)
        pwm_set_chan_level(slice1, ch1, g_pwm_wrap);
        pwm_set_chan_level(slice1, ch2, g_pwm_wrap);
        return;
    }

    const uint16_t lvl = percent_to_level(percent);
    if (percent > 0) {
        pwm_set_chan_level(slice1, ch1, lvl);
        pwm_set_chan_level(slice1, ch2, 0);
    } else {
        pwm_set_chan_level(slice1, ch1, 0);
        pwm_set_chan_level(slice1, ch2, lvl);
    }
}

void init() {
    // Configure GPIO -> PWM
    gpio_set_function(config::MOTOR_LEFT_IN1_PIN, GPIO_FUNC_PWM);
    gpio_set_function(config::MOTOR_LEFT_IN2_PIN, GPIO_FUNC_PWM);
    gpio_set_function(config::MOTOR_RIGHT_IN1_PIN, GPIO_FUNC_PWM);
    gpio_set_function(config::MOTOR_RIGHT_IN2_PIN, GPIO_FUNC_PWM);

    const uint left_slice = pwm_gpio_to_slice_num(config::MOTOR_LEFT_IN1_PIN);
    const uint right_slice = pwm_gpio_to_slice_num(config::MOTOR_RIGHT_IN1_PIN);

    // Configure PWM frequency ~20 kHz (inaudible-ish) using sys clk.
    // f_pwm = f_sys / (clkdiv * (wrap + 1))
    // With 125 MHz, clkdiv=1, wrap=6249 -> 20 kHz.
    g_pwm_wrap = 6249;

    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_clkdiv(&cfg, 1.0f);
    pwm_config_set_wrap(&cfg, g_pwm_wrap);

    pwm_init(left_slice, &cfg, false);
    if (right_slice != left_slice) {
        pwm_init(right_slice, &cfg, false);
    }

    // Safe default: brake everything (both HIGH)
    set_motor_level(kLeft, 0);
    set_motor_level(kRight, 0);

    pwm_set_enabled(left_slice, true);
    if (right_slice != left_slice) {
        pwm_set_enabled(right_slice, true);
    }

    g_target_left = g_target_right = 0;
    g_current_left = g_current_right = 0;

    printf("[MOTORS] PWM init OK (wrap=%lu, ~20kHz). Safe brake set.\n", g_pwm_wrap);
}

void set_target(int16_t left_percent, int16_t right_percent) {
    g_target_left = clamp_percent(left_percent);
    g_target_right = clamp_percent(right_percent);
}

void update() {
    g_current_left = approach(g_current_left, g_target_left, config::MOTOR_RAMP_STEP);
    g_current_right = approach(g_current_right, g_target_right, config::MOTOR_RAMP_STEP);

    set_motor_level(kLeft, g_current_left);
    set_motor_level(kRight, g_current_right);
}

void brake_all() {
    g_target_left = 0;
    g_target_right = 0;
    g_current_left = 0;
    g_current_right = 0;
    set_motor_level(kLeft, 0);
    set_motor_level(kRight, 0);
}

}  // namespace motors

