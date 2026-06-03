#pragma once

#include <stdint.h>

namespace uart_protocol {

enum class Source : uint8_t {
    UART_PI,
    USB_SERVICE,
};

struct CommandHandlers {
    void (*on_drive)(int16_t left, int16_t right) = nullptr;
    void (*on_cam)(int16_t pan_deg, int16_t tilt_deg) = nullptr;
    void (*on_stop)() = nullptr;
    void (*on_ping)() = nullptr;
};

void init(const CommandHandlers& handlers);

// Poll UART0 RX and feed the line-buffered parser.
void poll();

// Drain USB CDC stdin (non-blocking) and feed the USB line parser.
void poll_usb();

// Service-mode banner on USB (no-op if disabled in config).
void print_service_banner();

}  // namespace uart_protocol
