# RP3 Tank

Robot gąsienicowy sterowany przez WiFi. Raspberry Pi 3A+ na pokładzie streamuje
obraz z kamery i przyjmuje sterowanie; Raspberry Pi Pico (C++) odpowiada za warstwę
real-time (PWM silników, serwa, watchdog, czujnik odległości); ESP32 z ekranem
dotykowym to opcjonalny bezprzewodowy pilot. Operator steruje z telefonu/laptopa.

Projekt prowadzony w modelu „architekt + agenci": **Claude** planuje i pisze prompty,
**agenci Cursora** generują kod (osobny agent per platforma).

---

## Gdzie co jest

| Plik | Do czego |
|---|---|
| **[`PROJECT.md`](PROJECT.md)** | źródło prawdy — architektura, kontrakty (UART/API), piny, zasilanie, fazy |
| **[`AGENTS.md`](AGENTS.md)** | role i zasady dla agentów, workflow iteracji, commity |
| **[`ITERATIONS.md`](ITERATIONS.md)** | log wszystkich sesji generowania kodu (postmortemy) |
| `docs/iterations/` | szczegółowe plany i podsumowania pojedynczych sesji |
| `.cursor/rules/main.mdc` | reguły dla agentów Cursora (ładowane automatycznie) |

---

## Układ repo

```
rp3tank/
├── PROJECT.md / README.md / AGENTS.md / ITERATIONS.md
├── .cursor/rules/main.mdc
├── docs/iterations/            # plan + podsumowanie każdej sesji
├── pi/                         # Pi Agent (Python) — Faza 1 ✅
│   ├── src/{main,config,camera,pico_link,server}.py
│   ├── src/web/index.html
│   ├── config.yaml · requirements.txt
│   └── systemd/control-server.service
├── pico/                       # Pico Agent (C++) — Faza 2/3
│   ├── src/ · include/ · CMakeLists.txt
└── esp32/                      # ESP32 Agent (C++/LVGL) — Faza 5
```

---

## Status

| Faza | Platforma | Co | Status |
|---|---|---|---|
| 1 | Pi (Python) | serwer + kamera MJPEG + WS + /status + most UART + systemd | ✅ ukończona |
| 2 | Pico (C++) | drive PWM + serwa + watchdog + STAT + logi USB | ✅ ukończona |
| 3 | Pi (Python) | panel diagnostyczny + żywość Pico po STAT (KI-1) + logi zdarzeń | ⬜ następna |
| 4 | Pico (C++) | HC-SR04 + auto-stop + pełny `dist` w STAT | ⬜ |
| 5 | Pi (Python) | hardening: wyścig shutdown (KI-2), usunięcie CSS rotate (KI-3) | ⬜ |
| 6 | ESP32 (C++/LVGL) | pilot + panel statusu | ⬜ |

Szczegóły, kontrakty i uzasadnienie kolejności: `PROJECT.md`. Log sesji: `ITERATIONS.md`.

---

## Szybki start — serwer Pi (Faza 1)

Wymagania systemowe (Raspberry Pi OS Lite 64-bit / Bookworm) wykonane ręcznie raz:
włączona kamera (auto-detekcja na Bookworm), `python3-picamera2` doinstalowane
przez `apt`, użytkownik `rp` w grupach `video` i `dialout`, UART na stabilnym PL011
(`dtoverlay=disable-bt` → `/dev/serial0` = `ttyAMA0`) z wyłączoną konsolą szeregową.
Szczegóły: `PROJECT.md` §9a oraz `docs/iterations/`.

```bash
cd /opt/rp3tank/pi
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt

# uruchomienie ręczne (do testów):
python -m src.main
# panel: http://<ip-pi>:8000/   ·   status: http://<ip-pi>:8000/status
```

Autostart przez systemd (usługa jako `User=rp`):

```bash
sudo cp pi/systemd/control-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now control-server
systemctl status control-server --no-pager -l
```

Uwaga: nie uruchamiaj równocześnie instancji ręcznej i usługi systemd — obie biją się
o kamerę i port 8000.

---

## Build — Pico (od Fazy 2)

Do uzupełnienia przez Pico Agenta w Fazie 2 (pico-sdk + cmake, output `.uf2`).

## Build — ESP32 (od Fazy 5)

Do uzupełnienia przez ESP32 Agenta w Fazie 5 (Arduino-ESP32 + LVGL).