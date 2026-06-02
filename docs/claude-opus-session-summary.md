# Podsumowanie sesji - Faza 1 (Pi control server)

## Co zostalo zrobione w tej sesji

W katalogu `pi/` przygotowano i uporzadkowano komplet serwera sterowania dla Raspberry Pi:

- konfiguracja aplikacji (`dataclass` + YAML + fallbacki),
- strumieniowanie MJPEG z Picamera2 po HTTP,
- most UART do Pico z reconnectem i telemetria,
- API FastAPI (`/`, `/status`, `/stream.mjpg`, `/ws/control`),
- UI testowe (vanilla JS) z podgladem obrazu, d-padem, suwkami pan/tilt i STOP,
- uruchamianie przez `python -m src.main` i przez `systemd`.

W tej zmianie ustawiono docelowego uzytkownika uslugi systemd:

- `User=rp`
- `Group=rp`

## Jak to dziala ze soba

`src/main.py`:
- laduje `config.yaml`,
- konfiguruje logging,
- buduje app FastAPI przez `create_app(config)`,
- startuje uvicorn.

`src/server.py`:
- zarzadza cyklem zycia (start/stop kamery i PicoLink),
- wystawia endpointy:
  - `GET /` - UI,
  - `GET /status` - stan aplikacji i telemetria,
  - `GET /stream.mjpg` - MJPEG stream,
  - `WS /ws/control` - komendy sterowania (`drive`, `cam`, `stop`),
- zawiera watchdog aplikacyjny (failsafe STOP przy braku komend).

`src/camera.py`:
- uruchamia Picamera2,
- streamuje MJPEG przez `MJPEGEncoder(bitrate=None)`,
- uzywa `FileOutput(StreamingOutput)` gdzie `StreamingOutput` dziedziczy po `io.BufferedIOBase`,
- generator streamu czeka na nowa klatke i deduplikuje kolejne buforowane klatki.

`src/pico_link.py`:
- utrzymuje polaczenie UART (`/dev/serial0`, 115200),
- gdy Pico nie ma: serwer dziala dalej, a link robi cykliczne reconnecty,
- parsuje telemetrie `STAT batt=... dist=... up=...`,
- wysyla komendy `DRIVE`, `CAM`, `STOP`, `PING` z coalescingiem ok. 50 ms.

## Jak uruchomic na malince

1. Wejdz do projektu:

```bash
cd /opt/rp3tank/pi
```

2. Utworz venv z dostepem do pakietow systemowych (Picamera2):

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Uruchom recznie:

```bash
python -m src.main
```

4. Otworz:
- `http://<ip-maliny>:8000/`
- status: `http://<ip-maliny>:8000/status`

5. systemd:
- plik uslugi: `pi/systemd/control-server.service`,
- od teraz uruchamiane jako `User=rp`, `Group=rp`.

Przyklad aktywacji:

```bash
sudo cp pi/systemd/control-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now control-server
sudo systemctl status control-server
```

Uwaga praktyczna: uzytkownik `rp` powinien miec dostep do UART i kamery (grupy np. `dialout`, `video`).

## Rozklad plikow (Faza 1)

- `pi/src/main.py` - entry point, logging, start uvicorn.
- `pi/src/config.py` - dataclass config + `load_config()` + `clamp()`.
- `pi/src/camera.py` - `CameraStream` i MJPEG.
- `pi/src/pico_link.py` - UART, telemetria, reconnect.
- `pi/src/server.py` - FastAPI i endpointy.
- `pi/src/web/index.html` - UI testowe.
- `pi/config.yaml` - konfiguracja runtime.
- `pi/requirements.txt` - zaleznosci pip.
- `pi/systemd/control-server.service` - unit uslugi.

## Stan repo po tej zmianie

- branch: `main`
- wykonana zmiana konfiguracyjna: `pi/systemd/control-server.service` (`User=rp`, `Group=rp`)
- dodany dokument sesji: `docs/claude-opus-session-summary.md`

