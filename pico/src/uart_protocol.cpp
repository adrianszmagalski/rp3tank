#include "uart_protocol.hpp"

#include <stdio.h>
#include <string.h>

#include "hardware/uart.h"
#include "pico/stdio.h"
#include "pico/error.h"

#include "config.hpp"
#include "telemetry.hpp"

namespace uart_protocol {

static CommandHandlers g_handlers;

struct DispatchResult {
    bool ok = false;
    char ack_detail[48] = {};
};

struct LineContext {
    Source source;
    uint16_t max_size;
    char* buffer;
    uint16_t length;
    bool overflow;
};

static char g_uart_buffer[config::UART_LINE_BUFFER_SIZE];
static char g_usb_buffer[config::USB_LINE_BUFFER_SIZE];

static LineContext g_uart_ctx{
    Source::UART_PI,
    config::UART_LINE_BUFFER_SIZE,
    g_uart_buffer,
    0,
    false,
};

static LineContext g_usb_ctx{
    Source::USB_SERVICE,
    config::USB_LINE_BUFFER_SIZE,
    g_usb_buffer,
    0,
    false,
};

static const char* source_tag(Source src) {
    return src == Source::UART_PI ? "[UART]" : "[USB]";
}

static void reset_ctx(LineContext* ctx) {
    ctx->length = 0;
    ctx->overflow = false;
}

static int16_t clamp_int16(int16_t v, int16_t lo, int16_t hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static void usb_emit_ack(bool ok, const char* detail) {
    if (ok) {
        printf("OK %s\n", detail);
    } else {
        printf("ERR %s\n", detail);
    }
}

static void print_help_usb() {
    printf("RP3 Tank — USB service mode\n");
    printf("Commands:\n");
    printf("  DRIVE <left> <right>   motors -100..100 (watchdog ~300ms)\n");
    printf("  CAM <pan> <tilt>       servos (clamped to limits)\n");
    printf("  STOP                   brake motors\n");
    printf("  PING                   reply PONG\n");
    printf("  STAT?                  one STAT frame on USB\n");
    printf("  HELP                   this message\n");
    printf("Note: DRIVE expires after ~%u ms without another DRIVE (failsafe).\n",
           config::DRIVE_FAILSAFE_MS);
    printf("Set serial line ending to LF or CRLF (not None).\n");
}

static DispatchResult handle_command(char* line, Source source) {
    DispatchResult result{};
    const bool usb = (source == Source::USB_SERVICE);
    const char* tag = source_tag(source);

    char* cmd = strtok(line, " ");
    if (!cmd) {
        snprintf(result.ack_detail, sizeof(result.ack_detail), "empty command");
        return result;
    }

    if (strcmp(cmd, "DRIVE") == 0) {
        char* left_s = strtok(nullptr, " ");
        char* right_s = strtok(nullptr, " ");
        if (!left_s || !right_s) {
            printf("%s DRIVE: invalid args\n", tag);
            snprintf(result.ack_detail, sizeof(result.ack_detail), "DRIVE invalid args");
            return result;
        }
        int l = 0, r = 0;
        if (sscanf(left_s, "%d", &l) != 1 || sscanf(right_s, "%d", &r) != 1) {
            printf("%s DRIVE: parse error\n", tag);
            snprintf(result.ack_detail, sizeof(result.ack_detail), "DRIVE invalid args");
            return result;
        }
        const int16_t left = clamp_int16(static_cast<int16_t>(l),
                                         config::DRIVE_INPUT_MIN,
                                         config::DRIVE_INPUT_MAX);
        const int16_t right = clamp_int16(static_cast<int16_t>(r),
                                          config::DRIVE_INPUT_MIN,
                                          config::DRIVE_INPUT_MAX);
        printf("%s DRIVE %d %d\n", tag, left, right);
        if (g_handlers.on_drive) {
            g_handlers.on_drive(left, right);
        }
        result.ok = true;
        snprintf(result.ack_detail, sizeof(result.ack_detail), "DRIVE %d %d", left, right);
        return result;
    }

    if (strcmp(cmd, "CAM") == 0) {
        char* pan_s = strtok(nullptr, " ");
        char* tilt_s = strtok(nullptr, " ");
        if (!pan_s || !tilt_s) {
            printf("%s CAM: invalid args\n", tag);
            snprintf(result.ack_detail, sizeof(result.ack_detail), "CAM invalid args");
            return result;
        }
        int p = 0, t = 0;
        if (sscanf(pan_s, "%d", &p) != 1 || sscanf(tilt_s, "%d", &t) != 1) {
            printf("%s CAM: parse error\n", tag);
            snprintf(result.ack_detail, sizeof(result.ack_detail), "CAM invalid args");
            return result;
        }
        const int16_t pan = clamp_int16(static_cast<int16_t>(p),
                                        config::SERVO_PAN_MIN_DEG,
                                        config::SERVO_PAN_MAX_DEG);
        const int16_t tilt = clamp_int16(static_cast<int16_t>(t),
                                         config::SERVO_TILT_MIN_DEG,
                                         config::SERVO_TILT_MAX_DEG);
        printf("%s CAM %d %d\n", tag, pan, tilt);
        if (g_handlers.on_cam) {
            g_handlers.on_cam(pan, tilt);
        }
        result.ok = true;
        snprintf(result.ack_detail, sizeof(result.ack_detail), "CAM %d %d", pan, tilt);
        return result;
    }

    if (strcmp(cmd, "STOP") == 0) {
        printf("%s STOP\n", tag);
        if (g_handlers.on_stop) {
            g_handlers.on_stop();
        }
        result.ok = true;
        snprintf(result.ack_detail, sizeof(result.ack_detail), "STOP");
        return result;
    }

    if (strcmp(cmd, "PING") == 0) {
        printf("%s PING\n", tag);
        if (g_handlers.on_ping) {
            g_handlers.on_ping();
        }
        if (usb) {
            printf("PONG\n");
        }
        result.ok = true;
        snprintf(result.ack_detail, sizeof(result.ack_detail), "PING");
        return result;
    }

    if (usb && strcmp(cmd, "HELP") == 0) {
        print_help_usb();
        result.ok = true;
        snprintf(result.ack_detail, sizeof(result.ack_detail), "HELP");
        return result;
    }

    if (usb && strcmp(cmd, "STAT?") == 0) {
        telemetry::print_stat_usb();
        result.ok = true;
        snprintf(result.ack_detail, sizeof(result.ack_detail), "STAT?");
        return result;
    }

    printf("%s Unknown command: %s\n", tag, cmd);
    snprintf(result.ack_detail, sizeof(result.ack_detail), "unknown command");
    return result;
}

static void finish_line(LineContext* ctx) {
    if (ctx->overflow) {
        if (ctx->source == Source::USB_SERVICE) {
            printf("ERR line too long\n");
        } else {
            printf("[UART] Line too long, dropping\n");
        }
        reset_ctx(ctx);
        return;
    }

    if (ctx->length == 0) {
        reset_ctx(ctx);
        return;
    }

    ctx->buffer[ctx->length] = '\0';
    const DispatchResult res = handle_command(ctx->buffer, ctx->source);
    if (ctx->source == Source::USB_SERVICE) {
        usb_emit_ack(res.ok, res.ack_detail);
    }
    reset_ctx(ctx);
}

static void usb_echo_char(char ch) {
    putchar(ch);
}

static void feed_char(LineContext* ctx, char ch) {
    const bool usb = (ctx->source == Source::USB_SERVICE);

    if (usb && (ch == '\b' || ch == 0x7F)) {
        if (ctx->length > 0 && !ctx->overflow) {
            ctx->length--;
            printf("\b \b");
        }
        return;
    }

    if (ch == '\r' || ch == '\n') {
        if (usb) {
            printf("\r\n");
        }
        finish_line(ctx);
        return;
    }

    if (usb && !ctx->overflow) {
        usb_echo_char(ch);
    }

    if (ctx->overflow) {
        return;
    }

    if (ctx->length < ctx->max_size - 1) {
        ctx->buffer[ctx->length++] = ch;
    } else {
        ctx->overflow = true;
    }
}

void init(const CommandHandlers& handlers) {
    g_handlers = handlers;
    reset_ctx(&g_uart_ctx);
    reset_ctx(&g_usb_ctx);
}

void poll() {
    while (uart_is_readable(uart0)) {
        feed_char(&g_uart_ctx, static_cast<char>(uart_getc(uart0)));
    }
}

void poll_usb() {
    for (;;) {
        const int ch = getchar_timeout_us(0);
        if (ch == PICO_ERROR_TIMEOUT) {
            break;
        }
        feed_char(&g_usb_ctx, static_cast<char>(ch));
    }
}

void print_service_banner() {
    if (!config::SERVICE_BANNER_ENABLED) {
        return;
    }
    printf("\n");
    printf("========================================\n");
    printf("  RP3 Tank — USB service mode active\n");
    printf("  Type HELP for commands.\n");
    printf("  DRIVE watchdog: ~%u ms (failsafe brake)\n", config::DRIVE_FAILSAFE_MS);
    printf("  Line ending: LF or CRLF (not None)\n");
    printf("========================================\n");
    printf("\n");
}

}  // namespace uart_protocol
