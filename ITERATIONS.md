# ITERATIONS.md — log iteracji

Postmortem każdej sesji generowania kodu. Najnowsze na górze. Szczegółowy plan i
podsumowanie każdej sesji leżą w `docs/iterations/`. Format wpisu — patrz
`docs/iterations/_TEMPLATE.md`.

---

## Faza 2 — Pico: drive + serwa + watchdog + STAT ✅

- **Data:** 2026-06-02
- **Platforma / agent:** Pico (C++) / Pico Agent (Cursor)
- **Branch / commit:** `main`
- **Plan / podsumowanie:** `docs/iterations/02-pico-drive.md`

**Co zrobiono:**
- UART parser komend `DRIVE/CAM/STOP/PING` (bufor linii, tolerancja `\r\n`, drop overflow).
- PWM silników MX1508 (GP2–GP5): ~20 kHz, sign-magnitude, STOP=faktyczny brake, rampa i limit mocy.
- PWM serw (GP6/GP7): 50 Hz, mapowanie stopni→µs, clamp do limitów.
- Watchdog: logiczny failsafe ~300 ms (brak `DRIVE` → brake) + sprzętowy WDT RP2040.
- Telemetria: `STAT batt=<x.xx> dist=0 up=1` 5 Hz po UART0; `batt` z ADC0 (×2).
- Logi diagnostyczne po USB CDC (UART0 czysty).

**Stan na sprzęcie:** build przechodzi i generuje `pico.uf2`; na obecnym bring-up „na sucho” PWM i STAT są weryfikowalne miernikiem/terminalem.

**Następny krok:** podpiąć zasilanie silników/serw i potwierdzić realny ruch oraz dobrać rampę/limit; potem Faza 3 (HC-SR04).

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
