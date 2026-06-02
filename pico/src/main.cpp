#include <stdio.h>
#include <stdint.h>

#include "pico/stdlib.h"
#include "pico/time.h"
#include "hardware/uart.h"
#include "hardware/watchdog.h"

#include "config.hpp"
#include "uart_protocol.hpp"
#include "motors.hpp"
#include "servos.hpp"
#include "telemetry.hpp"

// Global state for watchdog/failsafe timing
static absolute_time_t g_last_drive_cmd_time;
static bool g_failsafe_logged = false;
static bool g_wdt_test_enabled = false;
static absolute_time_t g_wdt_test_hang_at;

static void mark_drive_command_received() {
    g_last_drive_cmd_time = get_absolute_time();
}

int main() {
    // Initialize stdio (USB CDC only, UART stdio disabled in CMake)
    stdio_init_all();

    sleep_ms(2000);  // Give USB some time to enumerate

    const bool watchdog_reset = watchdog_caused_reboot();
    if (watchdog_reset) {
        printf("[BOOT] Reboot caused by hardware watchdog.\n");
    } else {
        printf("[BOOT] Power-on or external reset.\n");
    }

    // Initialize hardware watchdog (timeout slightly above main loop period * some factor)
    // Here: 1000 ms timeout, main loop ~10 ms period
    watchdog_enable(1000, 1);

    // Init UART0 for protocol (115200 8N1)
    uart_init(uart0, config::UART_BAUD_RATE);
    gpio_set_function(config::UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(config::UART_RX_PIN, GPIO_FUNC_UART);
    // No stdio on UART0; UART used only for protocol frames

    // Initialize peripherals
    motors::init();
    servos::init();
    telemetry::init_adc();

    // Safe outputs before entering main loop
    motors::brake_all();
    servos::set_pan_deg(config::SERVO_PAN_CENTER_DEG);
    servos::set_tilt_deg(config::SERVO_TILT_CENTER_DEG);

    printf("[BOOT] Peripherals initialized: UART0, motors (MX1508), servos, ADC.\n");
    printf("[BOOT] Safe state set: motors=brake, servos=center.\n");

    // Initialize UART parser with callbacks to modules
    uart_protocol::CommandHandlers handlers{};
    handlers.on_drive = [](int16_t left, int16_t right) {
        motors::set_target(left, right);
        mark_drive_command_received();
    };
    handlers.on_cam = [](int16_t pan_deg, int16_t tilt_deg) {
        servos::set_pan_deg(pan_deg);
        servos::set_tilt_deg(tilt_deg);
    };
    handlers.on_stop = []() {
        motors::brake_all();
        // Avoid immediate failsafe spam after an explicit STOP
        g_last_drive_cmd_time = get_absolute_time();
    };
    handlers.on_ping = []() {
        // No-op for now; STAT frames provide liveness
    };

    uart_protocol::init(handlers);

    // Initialize timers
    g_last_drive_cmd_time = get_absolute_time();
    absolute_time_t next_stat_time = make_timeout_time_ms(config::STAT_PERIOD_MS);
    if (config::WDT_TEST_HANG_ENABLED) {
        g_wdt_test_enabled = true;
        g_wdt_test_hang_at = make_timeout_time_ms(config::WDT_TEST_HANG_AFTER_MS);
        printf("[WDTTEST] Enabled: will hang after %u ms.\n", config::WDT_TEST_HANG_AFTER_MS);
    }

    printf("[MAIN] Entering main loop.\n");

    while (true) {
        if (g_wdt_test_enabled &&
            absolute_time_diff_us(get_absolute_time(), g_wdt_test_hang_at) <= 0) {
            printf("[WDTTEST] Hanging main loop to trigger hardware watchdog.\n");
            while (true) {
                tight_loop_contents();
            }
        }

        // Feed hardware watchdog
        watchdog_update();

        // Poll UART RX and feed parser
        uart_protocol::poll();

        // Logical watchdog for DRIVE commands
        const int64_t since_last_drive_ms =
            absolute_time_diff_us(g_last_drive_cmd_time, get_absolute_time()) / 1000;
        if (since_last_drive_ms > static_cast<int64_t>(config::DRIVE_FAILSAFE_MS)) {
            motors::brake_all();
            // Log once per trigger window
            if (!g_failsafe_logged) {
                printf("[FAILSAFE] No DRIVE command for %lld ms, braking motors.\n",
                       since_last_drive_ms);
                g_failsafe_logged = true;
            }
        } else {
            // Reset flag if commands are coming again
            g_failsafe_logged = false;
        }

        // Update motor ramp
        motors::update();

        // Periodic STAT telemetry
        if (absolute_time_diff_us(get_absolute_time(), next_stat_time) <= 0) {
            telemetry::send_stat_frame();
            next_stat_time = delayed_by_ms(next_stat_time, config::STAT_PERIOD_MS);
        }

        sleep_ms(config::MAIN_LOOP_PERIOD_MS);
    }
}

