# RP3 Tank

**Gąsienicowy robot sterowany przez WiFi — kamera na żywo, sterowanie napędem i głowicą z poziomu przeglądarki.**

Trzy platformy, ścisły podział odpowiedzialności:

| Platforma | Rola | Język / stack | Katalog |
|---|---|---|---|
| **Raspberry Pi 3A+** | Mózg sieciowy: serwer WWW, stream kamery, WebSocket, most do Pico | Python / FastAPI / asyncio / Picamera2 | `pi/` |
| **Raspberry Pi Pico (RP2040)** | Warstwa real-time: PWM silników i serw, watchdog, telemetria | C++ / Pico SDK | `pico/` |
| **ESP32** | Opcjonalny pilot z ekranem dotykowym (planowany) | C++ / Arduino-ESP32 / LVGL | `esp32/` |

> **Źródło prawdy to [`PROJECT.md`](PROJECT.md).** Ten README jest przewodnikiem na start; w razie sprzeczności (np. dokładny kształt JSON, mapa pinów) obowiązuje `PROJECT.md`.

---

## Spis treści

1. [Jak to działa](#jak-to-działa)
2. [Stack technologiczny](#stack-technologiczny)
3. [Struktura repozytorium i pliki dokumentacji](#struktura-repozytorium-i-pliki-dokumentacji)
4. [Status projektu — fazy](#status-projektu--fazy)
5. [Znane problemy (KI)](#znane-problemy-ki)
6. [Kontrakty (nie zmieniać bez decyzji)](#kontrakty-nie-zmieniać-bez-decyzji)
7. [Szybki start na Linuksie](#szybki-start-na-linuksie)
8. [Workflow pracy](#workflow-pracy)
9. [Reguły warsztatowe (BHP sprzętu)](#reguły-warsztatowe-bhp-sprzętu)
10. [Roadmapa](#roadmapa)

---

## Jak to działa

```
Przeglądarka  ──HTTP/WebSocket/MJPEG──►  Raspberry Pi 3A+  ──UART 115200──►  Pico (RP2040)  ──PWM──►  silniki + serwa
   (klient)        (WiFi, port 8000)        FastAPI + kamera                  firmware real-time         MX1508 / SG-90
                                                  ▲                                  │
                                                  └──────────── STAT 5 Hz ───────────┘
                                                          (telemetria: batt / dist / żywość)
```

- **Pi** serwuje UI i stream kamery (MJPEG), przyjmuje komendy po WebSocket i tłumaczy je na ASCII po UART do Pico. Działa **bez** podłączonego Pico (degradacja, nie crash) — pokazuje wtedy stany alarmowe.
- **Pico** odbiera komendy, generuje PWM dla 2 silników (sterownik MX1508, sign-magnitude + active brake) i 2 serw (głowica pan/tilt), pilnuje **watchdoga** i co 200 ms wysyła ramkę telemetrii `STAT`.
- **Dwie niezależne warstwy bezpieczeństwa:** twardy watchdog Pico (brak `DRIVE` > ~300 ms → hamowanie) działa nawet gdy serwer Pi leży; aplikacyjny watchdog Pi (brak komendy > 500 ms → `STOP`) to druga warstwa.

---

## Stack technologiczny

**Raspberry Pi 3A+** (`pi/`)
- Raspberry Pi OS Lite **Bookworm** 64-bit (DietPi jest niezgodny ze stosem rpicam/libcamera)
- Python 3, **FastAPI** + **asyncio**, **Picamera2** (sprzętowy enkoder MJPEG), **pyserial**
- **NetworkManager** (WiFi), **systemd** (usługa `control-server`)
- UART na `/dev/serial0` → stabilny **PL011/ttyAMA0** dzięki `dtoverlay=disable-bt` (konsola szeregowa wyłączona)

**Raspberry Pi Pico / RP2040** (`pico/`)
- **C++**, **Pico SDK** (2.2.0), `cmake`, `arm-none-eabi-gcc`, flash przez `.uf2` / `picotool`
- Bez dynamicznej alokacji — statyczne bufory; `constexpr` zamiast `#define`
- Sprzętowy watchdog RP2040; logi diagnostyczne po **USB CDC** (UART0 czysty na protokół)

**ESP32** (`esp32/`, planowany)
- Arduino-ESP32 + **LVGL**, ekran dotykowy 170×320; tylko klient WiFi do API Pi (brak fizycznego połączenia z robotem)

**Sterownik silników:** MX1508 (mostek H, sign-magnitude PWM)

---

## Struktura repozytorium i pliki dokumentacji

```
rp3tank/
├── PROJECT.md            ← ŹRÓDŁO PRAWDY: architektura, kontrakty, piny, zasilanie, fazy, KI
├── AGENTS.md             ← role agentów Cursora i podział katalogów
├── ITERATIONS.md         ← log/postmortem każdej sesji (najnowsze na górze)
├── README.md             ← ten plik — przewodnik na start
├── .cursor/
│   └── rules/main.mdc    ← globalne, zawsze aktywne reguły dla agentów Cursora
├── pi/                   ← serwer Raspberry Pi (Pi Agent)
│   ├── src/              ← kod (server.py, pico_link.py, event_log.py, config.py, web/index.html…)
│   ├── config.yaml       ← konfiguracja (progi diagnostyki, batt itd.) — bez hardcode
│   └── requirements.txt
├── pico/                 ← firmware Pico (Pico Agent)
│   ├── src/              ← main.cpp, uart_protocol.cpp, motors, servos, telemetry…
│   ├── include/config.hpp← mapa pinów, limity serw, czasy watchdoga (constexpr)
│   └── build/pico.uf2    ← zbudowane firmware
├── esp32/                ← pilot ESP32 (planowany, ESP32 Agent)
└── docs/
    ├── iterations/       ← plan + podsumowanie KAŻDEJ sesji (wzór: _TEMPLATE.md)
    ├── setup/            ← runbooki (m.in. reinstalacja Pi + WiFi safety net)
    └── zasilanie.svg     ← schemat domen zasilania i wspólnej masy
```

**Do czego służy który plik `.md`:**

| Plik | Rola | Kto edytuje |
|---|---|---|
| `PROJECT.md` | Jedyne źródło prawdy: wszystkie kontrakty i decyzje | architekt |
| `AGENTS.md` | Role agentów, izolacja katalogów, workflow | architekt |
| `ITERATIONS.md` | Skrócony postmortem każdej iteracji (lista) | agent + architekt |
| `docs/iterations/<faza>-*.md` | Szczegółowy plan i podsumowanie pojedynczej sesji | agent |
| `docs/iterations/_TEMPLATE.md` | Wzór wpisu iteracji | — |
| `.cursor/rules/main.mdc` | Reguły wstrzykiwane do każdego promptu Cursora | architekt |
| `README.md` | Wprowadzenie dla nowej osoby | architekt |

---

## Status projektu — fazy

Zasada: **jedna faza = jedna platforma = jeden agent = jedna sesja Cursora.** Numer fazy nie zmienia się wstecz. Faza 5 została celowo wyciągnięta przed Fazę 4 (brak miejsca na czujnik HC-SR04 na podwoziu).

| Faza | Platforma | Zakres | Status |
|---|---|---|---|
| **1** | Pi | Serwer FastAPI + kamera MJPEG + WebSocket + `/status` + most UART + systemd | ✅ ukończona |
| **2** | Pico | Parser UART, PWM 2 silników, 2 serwa (limity), watchdog ~300 ms + sprzętowy, STAT 5 Hz, logi USB | ✅ ukończona |
| **3** | Pi | Panel diagnostyczny, żywość Pico po świeżości STAT (**KI-1 zamknięte**), `/events` + logowanie | ✅ ukończona |
| **3.1** | Pico | Lokalny tryb serwisowy USB CDC (komendy + echo + ACK + `HELP`/`STAT?`/`PONG`); UART0 nietknięty | ✅ ukończona |
| **5** | Pi | Hardening: naprawa wyścigu shutdown (**KI-2**) + usunięcie tymczasowego CSS `rotate(180°)` (**KI-3**) | 🔄 kod gotowy, do domknięcia |
| **4** | Pico | HC-SR04 (realny `dist`), lokalny auto-stop przed przeszkodą | ⏸️ odłożona — brak miejsca; piny GP8/GP9 zarezerwowane |
| **3.2** | Pi (sysadmin) | SSH-over-USB przez USB gadget (awaryjny dostęp przy padzie WiFi) | ⏸️ odłożona — czeka na kabel USB-A↔USB-A z przeciętym 5 V |
| **6** | ESP32 | Pilot z ekranem dotykowym, klient WiFi do API Pi | ⬜ planowana |

**Co zostaje do domknięcia Fazy 5:** test ≥10× `systemctl restart` pod obciążeniem (zero `TypeError` w `journalctl`), merge `phase5` → `main`, aktualizacja `PROJECT.md` (§6 statusy, §9 KI).

> ℹ️ **Uwaga o spójności dokumentacji:** tabela faz i sekcja KI w `PROJECT.md` mogą jeszcze pokazywać Fazę 4 jako „następną", a KI-2/KI-3 jako otwarte — rekoncyliacja `PROJECT.md` z powyższym stanem to zaplanowane zadanie architekta. Ten README opisuje stan **rzeczywisty**.

---

## Znane problemy (KI)

| ID | Problem | Status |
|---|---|---|
| **KI-1** | UI pokazywało „Pico połączony", gdy tylko port UART był otwarty (port ≠ żywe Pico) | ✅ zamknięte — rozróżnienie `pico_connected` (port) vs `pico_alive` (świeżość STAT) |
| **KI-2** | Wyścig przy zamykaniu wątku `pico-uart-reader` → `TypeError` przy shutdown | 🔄 fix w kodzie (kolejność `stop_event → join → close`); czeka na test stresowy |
| **KI-3** | Tymczasowy CSS `rotate(180°)` na streamie (kamera była fizycznie do góry nogami) | 🔄 CSS usunięty — kamera wyprostowana sprzętowo; czeka na merge |
| **KI-4** | Serwa i Pi dzielą 5 V → gwałtowny ruch serw może zapaść napięcie Pi (brownout/reset) | ✅ mitygacja wdrożona — osobny port USB powerbanku + kondensatory (220–470 µF elektrolit + 100 nF ceramik przy serwach) |

**Dodatkowe ryzyko sprzętowe (do hardeningu):** powtarzane spadki napięcia (undervoltage) nie tylko wieszają radio WiFi, ale potrafią **uszkodzić system plików na karcie SD** — wtedy reboot nie pomaga, a leczy dopiero reflash. Mitygacje: lutowane połączenia zamiast płytki prototypowej, solidny zasilacz, brak hot-swapu, oraz docelowo karta read-only/overlay + „złoty obraz" do szybkiego reflashu. Patrz [Reguły warsztatowe](#reguły-warsztatowe-bhp-sprzętu).

---

## Kontrakty (nie zmieniać bez decyzji)

Pełne definicje w `PROJECT.md` §4–§5. Skrót dla orientacji:

**UART Pi ↔ Pico** — ASCII, linie `\n`, 115200 8N1, `/dev/serial0`:
```
Pi → Pico:   DRIVE <left> <right>   # -100..100 (% mocy, znak = kierunek)
             CAM <pan> <tilt>       # stopnie, w granicach limitów serw
             STOP                   # natychmiastowe zatrzymanie
             PING                   # heartbeat
Pico → Pi:   STAT batt=<float> dist=<int> up=<0|1>   # 5 Hz
```
> `HELP`/`STAT?`/`PONG`/echo/ACK to rozszerzenie **lokalne USB** (Faza 3.1) — **nie** są częścią protokołu UART ani sieciowego.

**API WiFi Pi ↔ klient:**
```
GET  /            UI testowe
GET  /status      JSON: uptime_s, pico_connected, pico_alive, stat_age_ms, batt_v, dist_cm, mode
GET  /events      JSON: {"events":[{ts, level, code, message}, ...]}  (ring ostatnich zdarzeń)
GET  /stream.mjpg MJPEG (multipart/x-mixed-replace)
WS   /ws/control  {type:"drive",left,right} | {type:"cam",pan,tilt} | {type:"stop"}
```
> Klienci (ESP32) muszą polegać na **`pico_alive`**, nie na `pico_connected` — inaczej powtórzą KI-1.

**Mapa pinów (Pico):** silniki GP2–GP5 (MX1508), serwa GP6/GP7, UART0 GP0(TX)/GP1(RX), batt GP26/ADC0 (dzielnik ×2), HC-SR04 GP8/GP9 (zarezerwowane; Echo przez dzielnik 1k/2k — RP2040 **nie** jest 5 V-tolerant).

**Limity serw (ochrona taśmy CSI kamery):** pan **10–170°**, tilt **30–150°**. Każda warstwa (Pi i Pico) clampuje niezależnie.

**Domeny zasilania (jedna wspólna masa!):**
- **Powerbank** (USB): port 1 → Pi + Pico (VSYS) + HC-SR04; port 2 → serwa (osobny rail z buforem)
- **4× AA** → wyłącznie silniki przez MX1508 (najgłośniejszy odbiornik, odizolowany od logiki)
- **Masa wspólna w jednym węźle**; dwa „+" (5 V powerbanku i ~4,8 V z AA) nigdy się nie stykają. Schemat: `docs/zasilanie.svg`.

> ⚠️ **MX1508 z „pływającą" masą = niekontrolowany silnik.** VB− sterownika musi być wpięty we wspólną masę, niezależnie od poprawności firmware.

**Watchdog:** Pico twardy ~300 ms (failsafe), Pi aplikacyjny 500 ms (druga warstwa). Świeżość STAT (`pico_stale_ms` ~1000 ms) to osobna sprawa — detekcja życia, nie failsafe.

---

## Szybki start na Linuksie

### Serwer Pi (`pi/`)

Na samym Raspberry Pi (repo sklonowane do `/opt/rp3tank`, użytkownik `rp`):

```bash
cd pi
python -m venv .venv --system-site-packages   # --system-site-packages: dostęp do systemowego Picamera2/libcamera
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

- UI:        `http://<adres-pi>:8000/`
- Status:    `http://<adres-pi>:8000/status`
- Zdarzenia: `http://<adres-pi>:8000/events`
- Logi:      `journalctl -u control-server -f`

Jako usługa systemd działa pod nazwą `control-server` (ścieżki `/opt/rp3tank/pi`, `User=rp`).

> **Końce linii muszą być LF.** CRLF w pliku `.service` daje `User=rp\r` → usługa nie wstaje (status 217/USER). Repo wymusza LF przez `.gitattributes`.

### Firmware Pico (`pico/`)

Wymaga Pico SDK + `arm-none-eabi-gcc` + `cmake`:

```bash
cd pico
mkdir -p build && cd build
cmake ..
make
# wynik: pico.uf2 — wgraj trzymając BOOTSEL przy podłączaniu USB, albo: picotool load -x pico.uf2
```

Logi/diagnostyka firmware: serial monitor po **USB** (np. `minicom`/`tio` na `/dev/ttyACM0`). UART0 jest zarezerwowany na protokół z Pi.

---

## Workflow pracy

Architekt projektuje i pisze prompty; **kod do repo generują agenci Cursora** (jeden agent = jedna platforma = jeden katalog).

Cykl jednej iteracji:
1. Przegląd stanu repo (`PROJECT.md`, `ITERATIONS.md`, `docs/iterations/`).
2. Architekt zadaje 4–7 pytań projektowych z opcjami i rekomendacją.
3. Decyzje → architekt produkuje **prompt dla Cursora** (markdown).
4. Cursor: **tryb Plan → akceptacja → Agent**.
5. Zamknięcie: **Conventional Commits** (`feat|fix|docs|refactor|chore|test|build(scope)`, scope = `pi|pico|esp32|docs|repo`) + postmortem w `ITERATIONS.md` + plan/podsumowanie w `docs/iterations/`.

**Higiena wymuszana w promptach i kodzie:**
- Pi działa bez Pico (degradacja, nie crash).
- Pico bez dynamicznej alokacji; watchdog niezależny od reszty logiki.
- Końce linii **LF** (CRLF psuje systemd i shebangi).
- Żadnych sekretów w repo — konfiguracja przez `config.yaml` / `.env`.
- Kontrakty (UART, API, piny, zasilanie, limity serw, watchdog) zamrożone — zmiana wymaga jawnej decyzji.

Role i izolacja katalogów: szczegóły w [`AGENTS.md`](AGENTS.md) i `.cursor/rules/main.mdc`.

---

## Reguły warsztatowe (BHP sprzętu)

Wyciągnięte z realnych awarii — warto przeczytać przed pierwszym podłączeniem:

- **Nigdy nie przepinaj niczego pod napięciem.** Odłącz oba zasilania (powerbank + AA) przed jakąkolwiek zmianą okablowania. **Masa podłączana pierwsza, odłączana ostatnia.** Hot-swap = transient/undervoltage → zawieszone radio WiFi (wraca po reboocie) lub, przy powtarzaniu, **uszkodzona karta SD** (wraca dopiero po reflashu).
- **Diagnostyka undervoltage:** `vcgencmd get_throttled` (bit 16 = undervoltage wystąpiło; `0x0` = czysto).
- **Płytka prototypowa = drgające styki = te same transienty** co hot-swap (losowe ruchy silników/serw, pady WiFi). Docelowo: lutowanie.
- **Pad WiFi to zwykle NIE konfiguracja** — to zasilanie. Na Bookworm sprawdź też `rfkill list` (WiFi bywa soft-blocked dopóki nie ustawisz kraju) oraz `ip link` (czy jest `wlan0`).
- 3A+ ma **jeden combo-chip** WiFi+Bluetooth — undervoltage psuje oba tak samo; Bluetooth nie obchodzi problemu z zasilaniem.

Runbook reinstalacji + WiFi safety net (kraj PL na stałe, watchdog timer, backup `.nmconnection` na partycji bootfs): `docs/setup/`.

---

## Roadmapa

**Najbliżej:** domknięcie Fazy 5 (test stresowy restartów + merge + aktualizacja `PROJECT.md`).

**Dalej / odłożone:**
- Faza 4 — HC-SR04 + realny `dist` + auto-stop (czeka na miejsce na podwoziu).
- Faza 3.2 — SSH-over-USB jako awaryjny dostęp (czeka na kabel USB-A↔USB-A z przeciętym 5 V).
- Faza 6 — pilot ESP32 z ekranem dotykowym.
- Przejście breadboard → lut (zdejmuje całą klasę transientów).
- Hardening karty SD: overlay/read-only root + „złoty obraz".

**Rozważane (jeszcze niezdecydowane):** Pi jako własny hotspot (niezależność od routera); bogaty klient sterujący na PC korzystający z istniejącego API Pi.

---

*Szczegóły zawsze w [`PROJECT.md`](PROJECT.md). Historia decyzji i sesji — w [`ITERATIONS.md`](ITERATIONS.md) i `docs/iterations/`.*
