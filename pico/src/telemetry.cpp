#include "telemetry.hpp"

#include <stdio.h>
#include <stdint.h>

#include "hardware/adc.h"
#include "hardware/uart.h"

#include "config.hpp"

namespace telemetry {

static float read_batt_voltage() {
    uint32_t sum = 0;
    for (uint8_t i = 0; i < config::BATT_SAMPLES; i++) {
        sum += adc_read();
    }
    const float avg = static_cast<float>(sum) / static_cast<float>(config::BATT_SAMPLES);
    const float v = (avg / static_cast<float>(config::BATT_ADC_MAX)) * config::BATT_VREF;
    return v * config::BATT_DIVIDER_MULTIPLIER;
}

static int format_stat_line(char* buf, size_t len) {
    const float batt = read_batt_voltage();
    return snprintf(buf, len, "STAT batt=%.2f dist=0 up=1\n", batt);
}

void init_adc() {
    adc_init();
    adc_gpio_init(26);  // GP26
    adc_select_input(config::BATT_ADC_INPUT);
    printf("[ADC] Initialized on GP26/ADC0.\n");
}

void send_stat_frame() {
    char buf[64];
    const int n = format_stat_line(buf, sizeof(buf));
    if (n > 0) {
        uart_puts(uart0, buf);
    }

    static uint32_t counter = 0;
    counter++;
    if ((counter % 5) == 0) {
        const float batt = read_batt_voltage();
        printf("[STAT] batt=%.2fV dist=0 up=1\n", batt);
    }
}

void print_stat_usb() {
    char buf[64];
    const int n = format_stat_line(buf, sizeof(buf));
    if (n > 0) {
        printf("%s", buf);
    }
}

}  // namespace telemetry
