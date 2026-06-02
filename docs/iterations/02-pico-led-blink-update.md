# Faza 2 — Pico: aktualizacja LED statusowej

- **Data:** 2026-06-02
- **Platforma / agent:** Pico / Pico Agent (Cursor)
- **Zakres tej sesji:** dodanie migania wbudowanej diody LED po starcie + rebuild firmware

## Co zostalo zrobione

- Dodano miganie wbudowanej diody LED na Pico (`PICO_DEFAULT_LED_PIN`) jako prosty sygnal, ze firmware zyje.
- Miganie jest realizowane w petli glownej bez blokowania innych zadan (UART parser, watchdog, PWM, STAT).
- Zbudowano ponownie firmware i wygenerowano nowy plik `pico/build/pico.uf2`.

## Zmiany w kodzie

- `pico/include/config.hpp`
  - dodana stala:
    - `STATUS_LED_TOGGLE_MS = 250`
- `pico/src/main.cpp`
  - dodana inicjalizacja pinu LED po starcie (`gpio_init`, `gpio_set_dir`, `gpio_put`)
  - dodane cykliczne przelaczanie stanu LED co `STATUS_LED_TOGGLE_MS`
  - log startowy informujacy o aktywacji LED

## Build / artefakty

- Build wykonany lokalnie przez Pico CMake toolchain (SDK 2.2.0)
- Wynik: sukces
- Artefakt: `pico/build/pico.uf2` (zaktualizowany w tej sesji)

## Uwagi dla architekta

- Nie zmieniano kontraktow (`PROJECT.md`): UART, mapa pinow dla napedu/serw/ADC oraz watchdog pozostaly bez zmian.
- LED korzysta z `PICO_DEFAULT_LED_PIN` i jest niezalezna od protokolu UART.
- Brak zmian w `pi/`, `esp32/` i plikach governance.

