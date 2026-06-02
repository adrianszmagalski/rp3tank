# Faza 2 — Pico: drive + serwa + watchdog + STAT

- **Data:** 2026-06-02
- **Platforma / agent:** Pico / Pico Agent (Cursor)
- **Branch / commit:** (uzupełnione po commicie)

---

## Plan (przed sesją — architekt)

**Cel iteracji:** firmware Pico z UART parserem, sterowaniem silnikami/serwami, watchdogiem oraz telemetrią STAT.

**Zakres (w tej sesji):**
- UART: parser komend `DRIVE/CAM/STOP/PING` (ASCII, `\n`), odporny na śmieci i `\r\n`.
- Silniki: PWM dla MX1508 (GP2–GP5), brake na STOP i failsafe.
- Serwa: PWM 50 Hz (GP6/GP7) z clampem do limitów.
- Watchdog: logiczny failsafe ~300 ms + sprzętowy WDT RP2040.
- Telemetria: odczyt ADC (GP26/ADC0, mnożnik ×2) + `STAT ...` 5 Hz po UART.
- Logi po USB CDC.

**Poza zakresem (świadomie):**
- HC-SR04 / `dist` — placeholder `0`.

**Kontrakty, których dotyczy (z PROJECT.md):**
- UART 115200 8N1, linie `\n`, komendy `DRIVE/CAM/STOP/PING`, ramka `STAT batt=<float> dist=<int> up=<0|1>`.
- Mapa pinów: GP2–GP5 (MX1508), GP6/GP7 (serwa), GP26/ADC0 (batt), UART0 GP0/GP1.
- Limity serw: pan 10–170°, tilt 30–150°.
- Watchdog Pico: brak `DRIVE` > ~300 ms → STOP/brake silników.

**Edge case'y / wymagania twarde:**
- Brak alokacji dynamicznej; stałe bufory.
- Przepełnienie linii UART → drop linii + log.
- Clamp wartości zamiast odrzucania całej komendy.
- Logi tylko po USB (UART0 czysty na protokół).

**Definicja „done":**
- [x] `pico/` buduje się, powstaje `pico.uf2`.
- [x] Bezpieczny stan wyjść ustawiony przed pętlą: silniki brake/0, serwa center.
- [x] Parser UART odporny na śmieci / `\r\n` / overflow.
- [x] `STAT` 5 Hz: `dist=0`, `up=1`, `batt` z ADC (może być losowy bez dzielnika).
- [x] PWM generowany na pinach silników i serw.
- [x] Failsafe ~300 ms: brak `DRIVE` → brake + log.
- [x] Sprzętowy WDT: loguje `watchdog_caused_reboot()`; dodana opcja testowego zawieszenia pętli (domyślnie off).

---

## Podsumowanie (po sesji — agent)

**Co zrobiono:**
- Przebudowano projekt `pico/` z „Hello world” do modułowego firmware z plikami w `pico/src/` i konfiguracją w `pico/include/config.hpp`.
- Dodano parser UART komend z Pi (bufor linii, tolerancja `\r\n`, drop overflow) i logi odebranych komend po USB CDC.
- Dodano sterowanie 2 silnikami przez MX1508: PWM ~20 kHz na GP2–GP5, sign-magnitude, brake jako STOP (oba wejścia HIGH), rampa i limit mocy (90%).
- Dodano PWM serw 50 Hz na GP6/GP7 z mapowaniem stopni na impuls 1000–2000 µs i clamp do limitów pan/tilt.
- Dodano telemetrię `STAT` 5 Hz wysyłaną po UART0 (do Pi), z `batt` z ADC0 (GP26) i mnożnikiem ×2 oraz `dist=0`.
- Dodano logiczny failsafe (~300 ms od ostatniego `DRIVE`) → hamowanie silników + log.
- Dodano sprzętowy watchdog RP2040 (timeout 1000 ms) i log rozpoznający reset z WDT.

**Jak to ze sobą działa:**
- `src/main.cpp` inicjalizuje stdio (USB), UART0 (protokół), PWM silników i serw, ADC, ustawia bezpieczny stan wyjść i wchodzi w pętlę 10 ms.
- `src/uart_protocol.cpp` zbiera bajty z UART0 do bufora linii i wywołuje callbacki na `DRIVE/CAM/STOP/PING`.
- `src/motors.cpp` utrzymuje target/current oraz rampę, a `update()` co tick ustawia PWM na pinach; `brake_all()` wymusza aktywny brake.
- `src/servos.cpp` utrzymuje PWM 50 Hz z 1 µs tickami i aktualizuje kanały A/B dla pan/tilt.
- `src/telemetry.cpp` czyta ADC, liczy napięcie i wysyła ramkę `STAT ...\n` po UART0.

**Jak uruchomić / zbudować:**
```bash
# Windows / PowerShell (CMake z pico extension)
$cmake="$env:USERPROFILE\.pico-sdk\cmake\v3.31.5\bin\cmake.exe"
& $cmake -S pico -B pico/build
& $cmake --build pico/build

# output
# pico/build/pico.uf2
```

**Układ plików (dodane/zmienione):**
- `pico/CMakeLists.txt`
- `pico/include/config.hpp`
- `pico/src/main.cpp`
- `pico/src/uart_protocol.hpp`, `pico/src/uart_protocol.cpp`
- `pico/src/motors.hpp`, `pico/src/motors.cpp`
- `pico/src/servos.hpp`, `pico/src/servos.cpp`
- `pico/src/telemetry.hpp`, `pico/src/telemetry.cpp`

**Stan repo:** branch `main`, commit: (uzupełnione po commicie)

**Odstępstwa od planu:**
- Sprzętowy watchdog testowany przez opcjonalne „zawieszenie” pętli sterowane stałą `config::WDT_TEST_HANG_ENABLED` (domyślnie wyłączone), zamiast dodatkowej komendy UART (kontrakt UART bez zmian).

**Znane problemy / następne kroki:**
- `batt` będzie losowe bez dzielnika na GP26 — oczekiwane na obecnym sprzęcie.
- Po podłączeniu zasilania silników i serw: dobrać rampę i limit mocy (`MOTOR_RAMP_STEP`, `MOTOR_MAX_DUTY`) pod realne obciążenie.
- W Fazie 3: HC-SR04 (`dist`) i ewentualne dopracowanie telemetrii.

