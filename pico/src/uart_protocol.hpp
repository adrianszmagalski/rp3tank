#pragma once

#include <stdint.h>

namespace uart_protocol {

struct CommandHandlers {
    void (*on_drive)(int16_t left, int16_t right) = nullptr;
    void (*on_cam)(int16_t pan_deg, int16_t tilt_deg) = nullptr;
    void (*on_stop)() = nullptr;
    void (*on_ping)() = nullptr;
};

void init(const CommandHandlers& handlers);

// Poll UART0 RX and feed the line-buffered parser.
void poll();

}  // namespace uart_protocol

