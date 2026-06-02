#pragma once

#include <stdint.h>

namespace servos {

void init();

// Degrees; values clamped to configured limits.
void set_pan_deg(int16_t deg);
void set_tilt_deg(int16_t deg);

}  // namespace servos

