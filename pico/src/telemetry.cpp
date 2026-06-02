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

void init_adc() {
    adc_init();
    adc_gpio_init(26);  // GP26
    adc_select_input(config::BATT_ADC_INPUT);
    printf("[ADC] Initialized on GP26/ADC0.\n");
}

void send_stat_frame() {
    const float batt = read_batt_voltage();

    char buf[64];
    // dist placeholder per spec; up=1 as long as firmware runs
    const int n = snprintf(buf, sizeof(buf), "STAT batt=%.2f dist=0 up=1\n", batt);
    if (n > 0) {
        uart_puts(uart0, buf);
    }

    // Diagnostic log (not on UART)
    static uint32_t counter = 0;
    counter++;
    if ((counter % 5) == 0) {  // ~1 Hz (STAT is 5 Hz)
        printf("[STAT] batt=%.2fV dist=0 up=1\n", batt);
    }
}

}  // namespace telemetry

