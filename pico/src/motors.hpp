#pragma once

#include <stdint.h>

namespace motors {

void init();

// Set target power in percent -100..100 (clamped internally).
void set_target(int16_t left_percent, int16_t right_percent);

// Apply ramping and update PWM outputs; call periodically from main loop.
void update();

// Immediately brake both motors (active brake).
void brake_all();

}  // namespace motors

