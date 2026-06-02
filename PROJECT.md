# PROJECT.md — RP3 Tank (źródło prawdy)

> Ten plik jest **jedynym źródłem prawdy** o projekcie. W razie konfliktu między tym
> plikiem a kodem, komentarzem, czyimś podsumowaniem albo wcześniejszą rozmową —
> wygrywa `PROJECT.md`. Zmiany w kontraktach (protokoły, piny, domeny zasilania)
> wprowadza wyłącznie **architekt** (Claude), nigdy agent samodzielnie.

Właściciel: Adrian (student elektrotechniki, embedded / vibe-coding).
Architekt: Claude (planuje, projektuje, pisze prompty — **nie pisze kodu do repo**).
Kod: generowany przez wyspecjalizowanych agentów Cursora (patrz `AGENTS.md`).

---

## 1. Cel

Robot gąsienicowy sterowany przez WiFi. Raspberry Pi 3A+ na pokładzie jest centrum
sterowania: odbiera komendy, streamuje obraz z kamery, steruje jazdą i ruchomą
kamerą (pan/tilt). Operator steruje z telefonu/laptopa, docelowo też z fizycznego
pilota na ESP32. Warstwa real-time (PWM, serwa, watchdog, czujnik) żyje na Pico.

---

## 2. Podział ról sprzętowych

| Platforma | Język / stack | Rola | Katalog |
|---|---|---|---|
| Raspberry Pi 3A+ | Python (FastAPI, asyncio, uvicorn) | serwer WiFi, stream kamery, most UART | `pi/` |
| Raspberry Pi Pico | C++ (Pico SDK, cmake) | PWM silników + serwa, watchdog, czujnik | `pico/` |
| ESP32 + ekran dotykowy 1,9" | C++ (Arduino-ESP32 + LVGL) | bezprzewodowy pilot + panel statusu | `esp32/` |

Granica niezmienna: **ESP32 łączy się z Pi tylko po WiFi** — nie wpina się w
okablowanie robota i nie współdzieli masy.

---

## 3. Domeny zasilania (3 osobne, JEDNA wspólna masa)

- **Powerbank A** → Pi (microUSB 5V). Z 5V Pi: Pico (VSYS) i HC-SR04 (VCC).
- **Powerbank B** → tylko serwa SG-90 (osobny rail, brak brownoutu Pi przy ruchu serw).
- **Koszyk 4×AA NiMH (~4,8 V)** → VM sterownika MX1508 → silniki.
- **Wszystkie GND spięte w jeden punkt** (Pi, Pico, MX1508, powerbank B, pakiet AA).
- Odsprzęganie: 100 nF na zaciskach każdego silnika + 1000 µF na VM/GND sterownika.

---

## 4. Mapa pinów (kontrakt sprzętowy)

| Połączenie | Po stronie A | Po stronie B | Uwagi |
|---|---|---|---|
| UART | Pi GPIO14 (TX) | Pico GP1 (RX) | 115200 8N1 |
| UART | Pi GPIO15 (RX) | Pico GP0 (TX) | oba 3,3 V — bez konwertera |
| Zasilanie Pico | Pi 5V | Pico VSYS | |
| Silnik lewy | Pico GP2, GP3 | MX1508 kanał A | 2 wejścia PWM / silnik |
| Silnik prawy | Pico GP4, GP5 | MX1508 kanał B | |
| Serwo pan | Pico GP6 | SG-90 sygnał | 3,3 V wystarcza |
| Serwo tilt | Pico GP7 | SG-90 sygnał | |
| HC-SR04 Trig | Pico GP8 | HC-SR04 Trig | |
| HC-SR04 Echo | Pico GP9 | HC-SR04 Echo | **przez dzielnik 1k/2k → 3,3 V** (RP2040 nie jest 5V-tolerant) |
| Napięcie AA | Pico GP26 / ADC0 | dzielnik 10k/10k z pakietu AA | firmware mnoży ×2 |

**Limity serw (ochrona taśmy CSI kamery): pan 10–170°, tilt 30–150°.** Każda
warstwa (Pi i Pico) clampuje niezależnie.

---

## 5. Kontrakty komunikacyjne (NIE zmieniać bez architekta)

### 5.1 UART Pi ↔ Pico — ASCII, linie zakończone `\n`, 115200 8N1, `/dev/serial0`

Pi → Pico:
```
DRIVE <left> <right>    # int -100..100 (% mocy; znak = kierunek)
CAM <pan> <tilt>        # int w stopniach, w granicach limitów serw
STOP                    # natychmiastowe zatrzymanie
PING                    # heartbeat
```

Pico → Pi:
```
STAT batt=<float> dist=<int> up=<0|1>   # napięcie AA [V], HC-SR04 [cm], flaga życia
```

### 5.2 API WiFi Pi ↔ klient (przeglądarka / ESP32)

```
GET  /              # UI testowe
GET  /status        # JSON: uptime_s, pico_connected, batt_v, dist_cm, mode
GET  /stream.mjpg   # MJPEG (multipart/x-mixed-replace)
WS   /ws/control    # {type:"drive",left,right} | {type:"cam",pan,tilt} | {type:"stop"}
```

### 5.3 Watchdog (dwie niezależne warstwy)

- **Pico (twardy, lokalny): brak komendy > ~300 ms → STOP silników.** To jest realny
  failsafe — działa nawet gdy serwer Pi leży.
- **Pi (aplikacyjny): brak komendy > 500 ms → wysyła STOP, mode="failsafe".** Druga
  warstwa, nie zastępuje watchdoga Pico.

---

## 6. Plan fazowy (przeplanowany — jedna platforma na fazę)

Każda faza = jedna platforma = jeden agent = jedna sesja Cursora. Numer fazy nie
zmienia się wstecz; nowe ustalenia trafiają tu i do `ITERATIONS.md`.

| Faza | Platforma | Agent | Zakres | Status |
|---|---|---|---|---|
| **1** | Pi (Python) | Pi Agent | serwer + kamera MJPEG + WS + /status + most UART (degraduje bez Pico) + systemd | ✅ ukończona |
| **2** | Pico (C++) | Pico Agent | parser UART, PWM MX1508 (2 silniki), 2 serwa (limity), watchdog ~300 ms, STAT (batt z ADC; dist placeholder) | ⬜ następna |
| **3** | Pico (C++) | Pico Agent | HC-SR04 (dystans), ADC napięcia AA (×2), lokalny auto-stop, pełna telemetria STAT | ⬜ |
| **4** | Pi (Python) | Pi Agent | integracja + hardening: wykrywanie Pico przez heartbeat, naprawa wyścigu shutdown, telemetria w UI, usunięcie tymczasowego CSS rotate | ⬜ |
| **5** | ESP32 (C++/LVGL) | ESP32 Agent | WiFi klient do API Pi, ekran dotykowy 170×320, sterowanie, panel statusu, wykrywanie utraty łączności / resetu Pi | ⬜ |

Uwaga do kolejności: Faza 4 (hardening Pi) celowo jest **po** Fazie 2/3, bo
wykrywanie Pico przez heartbeat da się rzetelnie przetestować dopiero gdy istnieje
firmware odpowiadający ramkami STAT.

---

## 7. Konwencje per platforma

### Python (Pi)
- Zawsze `venv` z `--system-site-packages` (dostęp do systemowego Picamera2/libcamera).
- `asyncio` zamiast `threading` dla I/O (gdzie się da).
- Konfiguracja w `config.yaml` ładowana do `dataclass` z fallbackami; brak hardcode.
- `logging` z poziomami, nie `print`. Type hints wszędzie. Klasy dla sterowników.

### C++ (Pico)
- `pico-sdk` + `cmake` + `arm-none-eabi-gcc`. Flash przez `.uf2` / `picotool`.
- Typy z `<stdint.h>`. `#pragma once`. `constexpr` zamiast `#define`.
- Bez dynamicznej alokacji (`new`/`malloc`) — statyczne bufory.
- `stdio_init_all()` przed jakimkolwiek `printf()`. Rozważyć hardware watchdog timer.

### C++ (ESP32)
- Arduino-ESP32 + LVGL (do potwierdzenia na starcie Fazy 5).
- Tylko klient WiFi do Pi; brak fizycznego połączenia z robotem.

---

## 8. Zasady stałe

**Dla architekta (Claude):**
- Nie pisze kodu do repo — produkuje plan i prompty (markdown artifact).
- Pilnuje, by kontrakty z sekcji 4–5 były spójne między platformami.
- Aktualizuje `PROJECT.md` i `ITERATIONS.md` gdy zmieniają się ustalenia.

**Dla agentów (Cursor):**
- Najpierw czytają `PROJECT.md` i `AGENTS.md`, dopiero potem działają.
- Pracują tylko w katalogu swojej platformy; nie dotykają cudzych.
- Nie zmieniają kontraktów (protokoły, piny, zasilanie, limity) — propozycje zmian
  zgłaszają architektowi.
- Po sesji: Conventional Commits + podsumowanie sesji (patrz `AGENTS.md`).

---

## 9. Znane problemy / decyzje otwarte

- **KI-1 — fałszywe „Pico: połączony".** Otwarcie `/dev/serial0` zawsze się udaje
  (port istnieje na Pi niezależnie od tego, czy Pico jest podłączone), więc
  `connected=true` znaczy tylko „port otwarty", nie „Pico żyje". **Fix: Faza 4** —
  połączenie uznawane za żywe tylko gdy ramka STAT (odpowiedź na PING) przyszła
  < N ms temu.
- **KI-2 — wyścig przy shutdownie.** Wątek `pico-uart-reader` siedzi w blokującym
  `read()`, gdy wątek główny zamyka port → `TypeError` z pyserial. **Fix: Faza 4** —
  kolejność: ustaw stop event → join wątku z timeoutem → zamknij port; łapać wyjątek
  w readerze, gdy fd znika.
- **KI-3 — tymczasowy obrót obrazu.** W `pi/src/web/index.html` jest tymczasowy
  `transform: rotate(180deg)` (kamera zamontowana do góry nogami do czasu statywu).
  Źródło Picamera2 **nie jest ruszane** (decyzja Adriana). Do usunięcia w Fazie 4,
  gdy kamera będzie wyprostowana fizycznie.

---

## 10. Sprzęt — odniesienie

Pełny inwentarz: `Inwentarz_warsztatowy__Arkusz1_1.pdf` (project files).
Podzespoły kluczowe dla projektu: Pi 3A+ (512 MB), Pico / Pico 2 / Pico 2W
(target firmware do potwierdzenia w Fazie 2), kamera OV5647, uchwyt Pan/Tilt,
2× SG-90, podwozie gąsienicowe (2 silniki 130, 3–8 V), sterownik MX1508
(1 A ciągłe / 1,5 A szczyt / kanał — **headroom względem prądu stall silników do
sprawdzenia w Fazie 2**), L293D (zapas), HC-SR04, 4× AA NiMH 2000 mAh + koszyk,
2× powerbank 10000 mAh 5V/2,4A, ESP32 z ekranem dotykowym 1,9" (170×320, LVGL).

System Pi: Raspberry Pi OS Lite 64-bit (Bookworm). Picamera2 + sprzętowy
MJPEGEncoder + `FileOutput(StreamingOutput)`. Usługa systemd jako `User=rp`,
`Group=rp`.
