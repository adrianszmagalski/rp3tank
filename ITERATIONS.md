# ITERATIONS.md — log iteracji

Postmortem każdej sesji generowania kodu. Najnowsze na górze. Szczegółowy plan i
podsumowanie każdej sesji leżą w `docs/iterations/`. Format wpisu — patrz
`docs/iterations/_TEMPLATE.md`.

---

## Faza 5 — Pi: hardening (KI-2 i KI-3 zamknięte) ✅

- **Data:** 2026-06-04
- **Platforma / agent:** Pi (Python) / Pi Agent (Cursor)
- **Branch / commit:** `phase5` (patrz `git log -1`)
- **Plan / podsumowanie:** [`docs/iterations/05-pi-hardening.md`](docs/iterations/05-pi-hardening.md)

**Co zrobiono:**
- **KI-2:** poprawna kolejność shutdown UART (`stop_event` → `STOP` → join wątków →
  `close`), `_port_lock` + `_take_serial()` (anty double-close), `TypeError` w readerze,
  `_handle_disconnect` bez self-join, `stop()` przez `asyncio.to_thread`.
- **KI-3:** w repo brak `rotate(180deg)` w `index.html` — UI już natywny; Picamera2
  nietknięte.
- Graceful shutdown: lifespan + `control-server.service` (SIGTERM, 10 s) — bez zmian,
  potwierdzone w kodzie.

**Test sprzętowy:** ×10 `systemctl restart` na malince — do wykonania (procedura w
podsumowaniu sesji).

---

## Faza 3.1 (dodatkowa) — Pico: tryb serwisowy USB ✅

- **Data:** 2026-06-03
- **Platforma / agent:** Pico (C++) / Pico Agent (Cursor)
- **Branch / commit:** `main` (patrz `git log -1`)
- **Plan / podsumowanie:** [`docs/iterations/03_1-pico-serwis-usb.md`](docs/iterations/03_1-pico-serwis-usb.md)

**Co zrobiono:**
- Drugie wejście komend przez USB CDC (nieblokujący `poll_usb`), wspólny dispatch z UART0.
- Echo, `OK`/`ERR`, `HELP`, `STAT?`, `PING`→`PONG` wyłącznie na USB; UART0 bez zmian (§5.1).
- Dwa bufory linii; baner serwisowy; `STAT?` jednorazowo na USB bez wpływu na STAT 5 Hz do Pi.

**Kontrakt:** §5.1 bez zmian — rozszerzenia HELP/STAT?/ACK/PONG są USB-only.

---

## Faza 3 — Pi: diagnostyka + żywość Pico (KI-1) ✅

- **Data:** 2026-06-03
- **Platforma / agent:** Pi (Python) / Pi Agent (Cursor)
- **Branch / commit:** `phase3`, `8388985`…`f23dadc`
- **Plan / podsumowanie:** [`docs/iterations/03-pi-diagnostyka.md`](docs/iterations/03-pi-diagnostyka.md)

**Co zrobiono:**
- Żywość Pico po świeżości ramek `STAT` (`pico_alive`, `stat_age_ms`); `pico_connected` = port otwarty (KI-1 naprawione w UI).
- `GET /events` + ring buffer zdarzeń; task diagnostyczny 250 ms; logowanie przez `logging`/journald.
- Panel diagnostyczny w `index.html`: 3 stany Pico, alarmy, pas 8 zdarzeń; prog batt z histerezą i strażnikiem ważności.

**KI-1:** zamknięte (fałszywe „Pico połączony” zastąpione rozróżnieniem port / STAT / żywy).

---

## Faza 2 — Pico: drive + serwa + watchdog + STAT ✅

- **Data:** 2026-06-02
- **Platforma / agent:** Pico (C++) / Pico Agent (Cursor)
- **Branch / commit:** `main`, `29b964e` (`feat(pico): drive PWM, servos, watchdog and STAT`)
- **Plan / podsumowanie:** `docs/iterations/02-pico-drive.md`

**Co zrobiono:**
- Firmware Pico 1 (RP2040) od zera, zgodny z kontraktami `PROJECT.md`.
- Parser UART `DRIVE/CAM/STOP/PING` (bufor linii, tolerancja `\r\n`, drop overflow,
  clamp wartości).
- PWM 2 silników MX1508 (GP2/GP3, GP4/GP5): sign-magnitude, brake na STOP/failsafe,
  rampa + limit mocy.
- PWM 2 serw (GP6/GP7): 50 Hz, mapowanie stopnie→µs, clamp pan 10–170 / tilt 30–150.
- Watchdog: logiczny ~300 ms (brak DRIVE → brake) + sprzętowy RP2040 z logiem
  `watchdog_caused_reboot()`.
- Telemetria `STAT batt=<x.xx> dist=0 up=1` 5 Hz po UART0; `batt` z ADC0 (×2).
- Logi diagnostyczne po USB CDC; UART0 czysty (stdio tylko USB).
- Dodatkowo: miganie wbudowanej LED jako sygnał życia (`docs/iterations/02-pico-led-blink-update.md`).

**Stan na sprzęcie (bring-up „na sucho", bez zasilania wykonawczego):**
- Potwierdzone: build/flash/start, bezpieczny stan startowy, logi USB, watchdog
  (failsafe w logach), **pełna dwukierunkowa komunikacja UART** — czyste `STAT`
  Pico→Pi oraz `[UART] PING` / `[UART] CAM 90 90` Pi→Pico.
- `batt ≈ 1.4 V` to pływający pin GP26 (brak dzielnika) — oczekiwane.
- Odroczone do zasilania/podwozia: realny ruch silników i serw, strojenie rampy/limitu
  (`MOTOR_RAMP_STEP`, `MOTOR_MAX_DUTY`), realny odczyt napięcia AA.

**Problemy napotkane i rozwiązane w trakcie (warstwa systemowa Pi, nie firmware):**
- UART sypał nieczytelnym, ale regularnym strumieniem. Dwie przyczyny naraz:
  (1) konsola szeregowa `agetty` na `ttyS0` mieszała bajty w ramki → wyłączona przez
  `raspi-config`; (2) `/dev/serial0` na mini-UART (`ttyS0`), którego baud dryfuje z
  core clock przy niestabilnym zasilaniu (Pi szło okrężnie przez Pico). Stabilny
  zasilacz dał czyste STAT; docelowy fix to PL011 (`ttyAMA0`) przez
  `dtoverlay=disable-bt`. Szczegóły: `PROJECT.md` §9a.
- Pułapka `sudo cmd > /dev/serial0`: przekierowanie wykonuje shell użytkownika, nie
  `sudo` → `Permission denied`. Rozwiązanie: `sudo bash -c "... > /dev/serial0"`.

**Następny krok:** Faza 3 — Pi: panel diagnostyczny w UI + wykrywanie żywości Pico po
świeżości STAT (KI-1) + logowanie zdarzeń.

## Faza 1 — Pi: serwer + kamera ✅

- **Data:** 2026-06-01
- **Platforma / agent:** Pi (Python) / Pi Agent (Cursor)
- **Branch / commit:** `main`
- **Plan / podsumowanie:** `docs/iterations/01-pi-server-camera.md`

**Co zrobiono:**
- Serwer FastAPI: `GET /`, `GET /status`, `GET /stream.mjpg`, `WS /ws/control`.
- Stream MJPEG z Picamera2: sprzętowy `MJPEGEncoder(bitrate=None)`, jakość przez enum
  `Quality` (config string `HIGH`), wyjście `FileOutput(StreamingOutput)` (dziedziczy
  po `io.BufferedIOBase`), generator czeka na nową klatkę i deduplikuje.
- Most UART do Pico (`/dev/serial0`, 115200) z reconnectem i parserem telemetrii STAT;
  serwer działa dalej, gdy Pico nie ma podłączonego.
- Watchdog aplikacyjny (failsafe STOP przy braku komend).
- UI testowe (vanilla JS): podgląd, d-pad, suwaki pan/tilt, STOP, polling `/status`.
- Uruchamianie przez `python -m src.main` i przez systemd (`User=rp`, `Group=rp`).

**Stan na sprzęcie:** działa. Kamera OV5647 startuje (960×540 @ 30, quality HIGH),
panel żywy, autostart przez systemd potwierdzony po reboocie.

**Problemy napotkane i rozwiązane w trakcie:**
- `status=217/USER` w systemd → przyczyną był **CRLF** w pliku `.service` (`User=rp\r`).
  Naprawione (`sed 's/\r$//'`); na przyszłość wymuszamy LF przez `.gitattributes`.
- Kolizja kamery/portu 8000 przy równoległym uruchomieniu ręcznym i systemd — nie błąd
  kodu, tylko dwie instancje naraz.

**Znane problemy przeniesione dalej (do Fazy 4):**
- **KI-1** — `/status` pokazuje `pico_connected=true` mimo braku Pico (otwarty port ≠
  żywy Pico). Fix: wykrywanie przez heartbeat.
- **KI-2** — wyścig przy shutdownie: `pico-uart-reader` w blokującym `read()` podczas
  zamykania portu → `TypeError`. Fix: join wątku przed `close()`.
- **KI-3** — tymczasowy `transform: rotate(180deg)` w `index.html` (kamera do góry
  nogami do czasu statywu); źródło Picamera2 nieruszane. Do usunięcia gdy kamera
  wyprostowana.

**Następny krok:** Faza 2 — firmware Pico (drive PWM + serwa + watchdog + STAT).

---

<!-- Nowe wpisy dodawaj POWYŻEJ tej linii, najnowszy na górze. -->
