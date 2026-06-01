# Raspberry Pi control server (Faza 1)

Serwer sterowania tankiem: stream MJPEG z kamery CSI, WebSocket do jazdy i pan/tilt, most UART do Pico.

## Wymagania

- Raspberry Pi 3A+ z DietPi (Bookworm), Python 3.11
- Kamera OV5647 (CSI), pakiet systemowy Picamera2 / libcamera
- Opcjonalnie: Pico na UART (`/dev/serial0`) — serwer działa też bez Pico

## Instalacja

```bash
cd /opt/rp3tank/pi   # lub ścieżka klonu repo

# venv z dostępem do Picamera2 z systemu
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

Na DietPi doinstaluj Picamera2 jeśli brakuje (np. `apt install python3-picamera2` — nazwa pakietu zależy od repozytorium).

## UART do Pico

1. Włącz UART: `raspi-config` → Interface Options → Serial Port (login shell: No, hardware: Yes), lub w `/boot/firmware/config.txt`:
   ```
   enable_uart=1
   ```
2. Jeśli port jest zajęty przez Bluetooth: `dtoverlay=disable-bt` i wyłącz `hciuart`.
3. Dodaj użytkownika serwisu do grupy `dialout`: `usermod -aG dialout <user>`.
4. Po reboot sprawdź: `ls -l /dev/serial0`.

## Uruchomienie ręczne

```bash
cd pi
source venv/bin/activate
python -m src.main
```

Otwórz w przeglądarce: `http://<adres-pi>:8000/`

Konfiguracja: [`pi/config.yaml`](../pi/config.yaml).

## Systemd

Dostosuj ścieżki w [`pi/systemd/control-server.service`](../pi/systemd/control-server.service) jeśli repo nie jest w `/opt/rp3tank`:

```bash
sudo cp pi/systemd/control-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now control-server
sudo systemctl status control-server
journalctl -u control-server -f
```

## Test kamery (opcjonalnie)

```bash
libcamera-hello -t 2000
```

## API

| Endpoint | Opis |
|----------|------|
| `GET /` | Strona testowa |
| `GET /stream.mjpg` | Stream MJPEG |
| `GET /status` | JSON: uptime, pico_connected, batt_v, dist_cm, mode |
| `WS /ws/control` | JSON: `drive`, `cam`, `stop` |

Przy wysokim obciążeniu CPU obniż rozdzielczość w `config.yaml` (np. 960×540).
