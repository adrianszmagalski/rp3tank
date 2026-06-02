# Faza 2 — Pico: pelne podsumowanie iteracji (od poczatku sesji)

- **Data:** 2026-06-02
- **Platforma / agent:** Pico / Pico Agent (Cursor)
- **Zakres podsumowania:** caly przebieg tej iteracji od pierwszej implementacji firmware do koncowej aktualizacji LED i rebuilda UF2

---

## 1) Co zostalo zrobione w tej iteracji

W tej iteracji zbudowano od zera docelowy firmware dla `pico/` zgodny z kontraktami `PROJECT.md` (UART, piny, limity serw, watchdog), a nastepnie wykonano dodatkowa poprawke z miganiem wbudowanej LED.

Zrealizowane elementy:

- Parser UART komend z Pi:
  - `DRIVE <left> <right>`
  - `CAM <pan> <tilt>`
  - `STOP`
  - `PING`
- Sterowanie silnikami przez MX1508:
  - PWM na GP2/GP3 i GP4/GP5
  - sign-magnitude
  - aktywny brake na STOP/failsafe (oba wejscia HIGH)
  - rampa zmian i limit mocy (ochrona)
- Sterowanie serwami SG-90:
  - PWM 50 Hz na GP6/GP7
  - mapowanie stopnie -> impuls 1000-2000 us
  - clamp limitow: pan 10-170, tilt 30-150
- Watchdog:
  - logiczny failsafe (~300 ms bez `DRIVE`) -> brake silnikow
  - sprzetowy RP2040 WDT + log `watchdog_caused_reboot()`
- Telemetria:
  - odczyt ADC0 (GP26), usrednianie probek, przeliczenie z mnoznikiem x2
  - wysylka `STAT batt=<x.xx> dist=0 up=1` co 200 ms (5 Hz)
- Logowanie i diagnostyka:
  - logi przez USB CDC
  - UART0 zostawiony dla protokolu (bez stdio na UART)
- Dodatkowo po prosbie uzytkownika:
  - miganie wbudowanej LED (`PICO_DEFAULT_LED_PIN`) po starcie i podczas pracy firmware
  - ponowny build i nowy `pico.uf2`

---

## 2) Jak to dziala razem (flow runtime)

`main.cpp`:
- inicjalizuje `stdio`, UART0, silniki, serwa, ADC i watchdog,
- ustawia **bezpieczny stan po starcie** (silniki brake, serwa center),
- uruchamia parser UART i callbacki komend,
- w petli:
  - odswieza hardware watchdog,
  - czyta UART i parsuje komendy,
  - pilnuje logicznego failsafe dla silnikow,
  - aktualizuje rampa PWM silnikow,
  - wysyla `STAT` 5 Hz,
  - przelacza stan LED statusowej co zadany interwal.

Moduly:
- `uart_protocol.*` - parser linii i dispatch komend.
- `motors.*` - PWM MX1508 + rampa + brake.
- `servos.*` - PWM 50 Hz i clamp limitow.
- `telemetry.*` - ADC + format i wysylka ramek `STAT`.
- `config.hpp` - piny, limity, czasy, stale runtime.

---

## 3) Zmodyfikowane / dodane pliki

### Firmware (pico)
- `pico/CMakeLists.txt`
- `pico/include/config.hpp`
- `pico/src/main.cpp`
- `pico/src/uart_protocol.hpp`
- `pico/src/uart_protocol.cpp`
- `pico/src/motors.hpp`
- `pico/src/motors.cpp`
- `pico/src/servos.hpp`
- `pico/src/servos.cpp`
- `pico/src/telemetry.hpp`
- `pico/src/telemetry.cpp`

### Dokumentacja iteracji
- `docs/iterations/02-pico-drive.md`
- `docs/iterations/02-pico-led-blink-update.md`
- `ITERATIONS.md` (wpis dla Fazy 2)

---

## 4) Build i artefakty

Build wykonano lokalnie przez CMake z toolchainem Pico SDK.

Wynik:
- konfiguracja: OK
- kompilacja: OK
- artefakt: `pico/build/pico.uf2` (wygenerowany i zaktualizowany po zmianie LED)

---

## 5) Commity / stan gita

Z tej iteracji zapisany commit firmware:
- `29b964e` - `feat(pico): drive PWM, servos, watchdog and STAT`

Po tym commicie doszla jeszcze zmiana LED + rebuild UF2 (na ten moment lokalnie w working tree, bez nowego commita).

---

## 6) Zgodnosc z kontraktami i ograniczeniami

- Nie zmieniono kontraktow UART/API/pinout/limitow serw.
- Praca wykonana w katalogu `pico/` + wymagane podsumowania w `docs/iterations/` i `ITERATIONS.md`.
- `dist` pozostaje placeholderem `0` (zgodnie z zakresem iteracji).
- Kod bez dynamicznej alokacji (`new`/`malloc`).

---

## 7) Co zostalo do dalszej walidacji na sprzecie

Po podlaczeniu docelowego zasilania i elementow wykonawczych:
- potwierdzenie realnego ruchu silnikow i skutecznosci brake pod obciazeniem,
- strojenie rampy i limitu mocy (`MOTOR_RAMP_STEP`, `MOTOR_MAX_DUTY`),
- fizyczna walidacja ruchu serw w granicach clampow,
- walidacja odczytu `batt` po podlaczeniu dzielnika na GP26.

