# Faza 5 — Pi: hardening (KI-2 shutdown + KI-3 obrót)

- **Data:** 2026-06-04
- **Platforma / agent:** Pi (Python) / Pi Agent (Cursor)
- **Branch / commit:** `phase5` (patrz `git log -1` po commicie sesji)

---

## Plan (przed sesją — architekt)

**Cel iteracji:** Wąski hardening — naprawa wyścigu przy shutdownie UART (KI-2) oraz
usunięcie tymczasowego obrotu obrazu w UI (KI-3), bez zmian kontraktów.

**Zakres (w tej sesji):**
- KI-2: kolejność zamykania w `pico_link.py`, atomowe wyjęcie portu, szersze łapanie
  wyjątków, brak self-join, `stop()` przez `asyncio.to_thread`.
- KI-3: usunięcie `transform: rotate(180deg)` z `index.html` (jeśli obecne).
- Weryfikacja ścieżki SIGTERM → lifespan → `PicoLink.stop()` → `STOP` na UART.

**Poza zakresem (świadomie):**
- Reconnect policy / backoff, zmiany Picamera2, `pico/`, `esp32/`, kontrakty UART/API.

**Kontrakty, których dotyczy (z PROJECT.md):**
- §5.1 UART — bez zmian (`STOP` przy shutdown to istniejąca komenda).
- §5.2 API WiFi — bez zmian (tylko ewentualny CSS w UI).
- Pipeline kamery — nietknięty.

**Definicja „done":**
- [x] `_disconnect`: stop_event → STOP → join → close; idempotentne.
- [x] Reader/sender: `SerialException | OSError | TypeError`; shutdown cicho.
- [x] Jedna ścieżka zamykania portu (`_take_serial`).
- [x] `_handle_disconnect` bez join readera.
- [x] `stop()` przez `to_thread`.
- [x] KI-3: brak obrotu CSS w repo.
- [x] Lifespan + systemd SIGTERM potwierdzone w kodzie.
- [ ] Test ×10 `systemctl restart` na malince (do wykonania przez Adriana).

---

## Podsumowanie (po sesji — agent)

**Co zrobiono:** W [`pi/src/pico_link.py`](../../pi/src/pico_link.py) naprawiono KI-2:
dodano `_port_lock` i `_disconnect_lock`, helpery `_take_serial()`, `_close_serial()`,
`_send_stop_on_serial()`. `_disconnect()` wykonuje teraz: `stop_event.set()` → zapis
`STOP\n` na otwartym porcie → `join` reader/sender (timeout 1 s, bez self-join) →
atomowe wyjęcie i `close()` portu. `_handle_disconnect()` (błąd read/write w trakcie
pracy) tylko zeruje stan i zamyka port przez `_take_serial()` — nigdy nie joinuje
wątku readera. Reader i `_write_line` łapią też `TypeError` (pyserial przy znikającym
fd); przy ustawionym `stop_event` log na poziomie `debug`, bez degradacji. `stop()`
wywołuje `_disconnect()` przez `await asyncio.to_thread(...)`.

KI-3: w [`pi/src/web/index.html`](../../pi/src/web/index.html) **nie było** reguły
`transform: rotate(180deg)` (ani w historii git repo) — obraz w UI jest już natywny;
Picamera2 nietknięte.

Graceful shutdown: bez zmian w [`pi/src/server.py`](../../pi/src/server.py) —
lifespan po `yield` woła `pico.send_stop()` i `await pico.stop()`. W
[`pi/systemd/control-server.service`](../../pi/systemd/control-server.service) są
`KillSignal=SIGTERM` i `TimeoutStopSec=10` — bez edycji.

**Jak to ze sobą działa:** Przy `systemctl stop` systemd wysyła SIGTERM do uvicorn.
FastAPI lifespan wychodzi z `yield`, anuluje taski watchdog/diagnostyka, kolejkuje
`STOP` w PicoLink, potem `stop()` ustawia `stop_event`, wysyła `STOP\n` na UART,
czeka na zakończenie wątków UART (read timeout 0.1 s → join ≤ ~1 s), dopiero wtedy
zamyka fd. Reader nie dostaje `TypeError` wychodzącego z wątku; ewentualny quirk przy
shutdown jest łapany i ignorowany cicho.

**Jak uruchomić / zbudować:**
```bash
cd /opt/rp3tank/pi
git pull   # po merge phase5
sudo systemctl restart control-server
```

**Układ plików (dodane/zmienione):**
- `pi/src/pico_link.py` — KI-2
- `docs/iterations/05-pi-hardening.md`, `ITERATIONS.md`

**Stan repo:** branch `phase5`

**Odstępstwa od planu:** KI-3 bez diffu w HTML (obrót nigdy nie trafił do repo w tej
gałęzi). Test sprzętowy ×10 restartów nie uruchamiany z Windows — procedura poniżej
do wykonania na malince.

**Znane problemy / następne kroki:**
- **Na przyszłość:** polityka reconnect (backoff, limit prób), dalsze hardeningi poza
  KI-2 — świadomie poza Fazą 5.
- **Test na malince (obowiązkowy przed zamknięciem KI-2 w PROJECT.md):**

```bash
# KI-2 pod obciążeniem (Pico podłączone, STAT lecą)
journalctl -u control-server -f   # drugie okno
for i in $(seq 1 10); do sudo systemctl restart control-server; sleep 3; done
# Oczekiwane: zero TypeError/traceback przy stopie; pico_alive wraca

# Bez Pico
# odłącz Pico, powtórz pętlę restart — czysto, pico_alive:false

# Kabel w trakcie
# wyrwij UART przy żywym serwisie — warning + reconnect, brak crasha

# Graceful stop
sudo systemctl stop control-server
# log: PicoLink stopped, Application stopped

# KI-3
# http://<pi>:8000/ — obraz w naturalnej orientacji
```
