# Faza 3.1 (dodatkowa) — Pico: tryb serwisowy USB

- **Data:** 2026-06-03
- **Platforma / agent:** Pico (C++) / Pico Agent (Cursor)
- **Branch / commit:** `main`, `762e685` (przed commitem sesji — zmiany lokalne)

---

## Plan (przed sesją — architekt)

**Cel iteracji:** lokalny tryb serwisowy przez USB CDC — komendy i odpowiedzi jak w terminalu, bez Pi/WiFi; kontrakt UART §5.1 bez zmian.

**Zakres (w tej sesji):**
- Parser z kontekstem per źródło (UART0 + USB), wspólny dispatch.
- Nieblokujący drenaż USB RX w pętli głównej.
- Echo, ACK `OK`/`ERR`, `HELP`, `STAT?`, `PING`→`PONG` tylko na USB.
- Baner serwisowy przy starcie.

**Poza zakresem (świadomie):**
- Zmiany `pi/`, `esp32/`, `PROJECT.md`.
- `PONG`/ACK/HELP na UART0.

**Kontrakty, których dotyczy (z PROJECT.md):**
- §5.1 UART Pi↔Pico — bez zmian (tylko `STAT` Pico→Pi, komendy Pi→Pico).
- §5.3 watchdog ~300 ms — `DRIVE` z USB odświeża failsafe tak samo.

**Definicja „done":**
- [x] Dwa bufory linii, wspólny `handle_command` z `Source`.
- [x] `poll_usb()` + echo/ACK/komendy lokalne USB.
- [x] UART0 czysty (brak echo/ACK/PONG/HELP na UART).
- [x] `STAT?` → jedna ramka na USB; kadencja STAT 5 Hz na UART0 bez zmian.
- [x] Build `pico.uf2`.

---

## Podsumowanie (po sesji — agent)

**Co zrobiono:**
- Zrefaktorowano `uart_protocol` na dwa statyczne konteksty linii (`g_uart_ctx`, `g_usb_ctx`) z funkcją `feed_char()` — terminator `\r` lub `\n`, puste linie ignorowane (CRLF bez fantomowej komendy).
- `poll()` czyta UART0; `poll_usb()` drenuje `getchar_timeout_us(0)` aż timeout — bez blokowania pętli głównej.
- Na USB: echo znaków (w tym Backspace/DEL → `\b \b`), po komendzie `OK …` / `ERR …`, komendy `HELP`, `STAT?`, `PING`→`PONG` + `OK PING`.
- Logi dispatchu z prefiksem `[UART]` lub `[USB]`; nic z USB-only nie trafia na `uart_puts(uart0)`.
- `telemetry::format_stat_line()` wspólne dla UART i `print_stat_usb()` (tylko na żądanie `STAT?`).
- `config.hpp`: `USB_LINE_BUFFER_SIZE`, `SERVICE_BANNER_ENABLED`.
- Baner serwisowy po `init()` w `main.cpp`.

**Jak to ze sobą działa:**
- Oba źródła wołają ten sam zestaw callbacków (`on_drive`, `on_cam`, …) z `main.cpp` — ostatnia komenda wygrywa dla stanu silników/serw.
- UART0 nadal wysyła wyłącznie ramki `STAT …\n` co 200 ms; diagnostyka `[STAT]` ~1 Hz idzie na USB jak wcześniej.
- Watchdog logiczny 300 ms: każde `DRIVE` (UART lub USB) resetuje timer w `mark_drive_command_received()`.

**Jak uruchomić / zbudować:**
```powershell
# Build (ninja z pico-sdk)
& "$env:USERPROFILE\.pico-sdk\ninja\v1.12.1\ninja.exe" -C pico/build

# Test: wgraj pico/build/pico.uf2, USB serial monitor, line ending LF lub CRLF
```

**Test na sprzęcie:**
1. Serial monitor (baud dowolny — CDC), LF lub CRLF.
2. Baner + okresowy `[STAT]` na USB.
3. `HELP`, `PING` (→ `PONG` + `OK PING`), `STAT?` (jedna linia `STAT …`).
4. `CAM 90 90` / `CAM 999 999` → `OK CAM …` z kątami po clampie w parserze.
5. `DRIVE 60 60` → ruch; po ~300 ms bez `DRIVE` → `[FAILSAFE]` i brake.
6. Linia > 63 znaki → `ERR line too long`.
7. Równolegle Pi: logi `[UART]`/`[USB]`; dla czystego testu zatrzymaj `control-server`.

**Układ plików (dodane/zmienione):**
- `pico/include/config.hpp`
- `pico/src/uart_protocol.hpp`, `pico/src/uart_protocol.cpp`
- `pico/src/telemetry.hpp`, `pico/src/telemetry.cpp`
- `pico/src/main.cpp`
- `docs/iterations/03_1-pico-serwis-usb.md`

**Stan repo:** branch `main`, commit bazowy `762e685`; artefakt `pico/build/pico.uf2` przebudowany lokalnie.

**Odstępstwa od planu:** brak — `PING` na USB zwraca `PONG` oraz `OK PING` (zgodnie z planem „PONG + OK PING”).

**Znane problemy / następne kroki:**
- Commit sesji po review (`feat(pico): serwisowy tryb USB …`).
- Architekt dopisze przypis USB-only w `PROJECT.md`.
- Faza 4: HC-SR04 i realny `dist` w `STAT`.
