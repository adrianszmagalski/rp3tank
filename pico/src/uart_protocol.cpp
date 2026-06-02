#include "uart_protocol.hpp"

#include <stdio.h>
#include <string.h>

#include "hardware/uart.h"

#include "config.hpp"

namespace uart_protocol {

static CommandHandlers g_handlers;
static char g_line_buffer[config::UART_LINE_BUFFER_SIZE];
static uint16_t g_line_length = 0;
static bool g_overflow = false;

static void reset_line() {
    g_line_length = 0;
    g_overflow = false;
}

static int16_t clamp_int16(int16_t v, int16_t lo, int16_t hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static void handle_command(char* line) {
    // Strip trailing \r if present
    size_t len = strlen(line);
    if (len > 0 && line[len - 1] == '\r') {
        line[len - 1] = '\0';
        len--;
    }

    // Skip empty lines
    if (len == 0) {
        return;
    }

    // Simple tokenization on spaces
    char* cmd = strtok(line, " ");
    if (!cmd) {
        return;
    }

    if (strcmp(cmd, "DRIVE") == 0) {
        char* left_s = strtok(nullptr, " ");
        char* right_s = strtok(nullptr, " ");
        if (!left_s || !right_s) {
            printf("[UART] DRIVE: invalid args\n");
            return;
        }
        int l = 0, r = 0;
        if (sscanf(left_s, "%d", &l) != 1 || sscanf(right_s, "%d", &r) != 1) {
            printf("[UART] DRIVE: parse error\n");
            return;
        }
        int16_t left = clamp_int16(static_cast<int16_t>(l),
                                   config::DRIVE_INPUT_MIN,
                                   config::DRIVE_INPUT_MAX);
        int16_t right = clamp_int16(static_cast<int16_t>(r),
                                    config::DRIVE_INPUT_MIN,
                                    config::DRIVE_INPUT_MAX);
        printf("[UART] DRIVE %d %d\n", left, right);
        if (g_handlers.on_drive) {
            g_handlers.on_drive(left, right);
        }
    } else if (strcmp(cmd, "CAM") == 0) {
        char* pan_s = strtok(nullptr, " ");
        char* tilt_s = strtok(nullptr, " ");
        if (!pan_s || !tilt_s) {
            printf("[UART] CAM: invalid args\n");
            return;
        }
        int p = 0, t = 0;
        if (sscanf(pan_s, "%d", &p) != 1 || sscanf(tilt_s, "%d", &t) != 1) {
            printf("[UART] CAM: parse error\n");
            return;
        }
        int16_t pan = static_cast<int16_t>(p);
        int16_t tilt = static_cast<int16_t>(t);
        printf("[UART] CAM %d %d\n", pan, tilt);
        if (g_handlers.on_cam) {
            g_handlers.on_cam(pan, tilt);
        }
    } else if (strcmp(cmd, "STOP") == 0) {
        printf("[UART] STOP\n");
        if (g_handlers.on_stop) {
            g_handlers.on_stop();
        }
    } else if (strcmp(cmd, "PING") == 0) {
        printf("[UART] PING\n");
        if (g_handlers.on_ping) {
            g_handlers.on_ping();
        }
    } else {
        printf("[UART] Unknown command: %s\n", cmd);
    }
}

void init(const CommandHandlers& handlers) {
    g_handlers = handlers;
    reset_line();
}

void poll() {
    while (uart_is_readable(uart0)) {
        const uint8_t ch = uart_getc(uart0);

        if (ch == '\n') {
            if (!g_overflow) {
                // Null-terminate
                g_line_buffer[g_line_length] = '\0';
                handle_command(g_line_buffer);
            } else {
                printf("[UART] Line too long, dropping\n");
            }
            reset_line();
        } else {
            if (g_overflow) {
                continue;  // ignore until newline
            }
            if (g_line_length < config::UART_LINE_BUFFER_SIZE - 1) {
                g_line_buffer[g_line_length++] = static_cast<char>(ch);
            } else {
                // Mark overflow and ignore remaining characters until newline
                g_overflow = true;
            }
        }
    }
}

}  // namespace uart_protocol

