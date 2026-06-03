# Faza 3 — Pi: panel diagnostyczny + żywość Pico (KI-1) + zdarzenia

> Pełne podsumowanie sesji (czat + implementacja + commity):
> [`03-pi-diagnostyka-sesja-pelne-podsumowanie.md`](03-pi-diagnostyka-sesja-pelne-podsumowanie.md)

- **Data:** 2026-06-03
- **Platforma / agent:** Pi (Python) / Pi Agent (Cursor)
- **Branch / commit:** `phase3`, `8388985`…`f23dadc` (3 commity feat)

---

## Plan (przed sesją — architekt)

**Cel iteracji:** Naprawa KI-1 (fałszywe „Pico połączony”), panel diagnostyczny, `/events`, logowanie przejść stanów.

**Zakres:** `PicoLink.alive` po świeżości STAT, addytywne `/status`, `GET /events`, task ~250 ms, UI.

**Poza zakresem:** KI-2 (shutdown reader), KI-3 (obrót streamu), firmware Pico.

---

## Podsumowanie (po sesji — agent)

**Co zrobiono:**

- `PicoLink` zapisuje monotoniczny timestamp przy każdej sparsowanej ramce `STAT`; właściwości `alive` i `stat_age_ms`; zerowanie znacznika przy disconnect/reconnect portu.
- `/status` rozszerzony o `pico_alive` i `stat_age_ms`; `pico_connected` bez zmiany znaczenia (port otwarty).
- Nowy moduł `event_log.py` — ring buffer w pamięci (`deque`, maxlen z configu), zdarzenia z `ts` = uptime serwera (float), kolejność od najstarszego do najnowszego.
- `GET /events` zwraca `{"events": [...]}`.
- Task `_diagnostics_loop` (250 ms) emituje zdarzenia na przejściach: pico alive/dead, failsafe enter/exit, uart connect/disconnect, batt low/ok (histereza + strażnik `batt_min_valid_v`).
- `ws_connect` / `ws_disconnect` w handlerze WebSocket; `uart_parse_error` jako `warning` z debounce 5 s na kod.
- Sekcja `diagnostics` w `config.yaml` / `DiagnosticsConfig`.
- UI: trzy stany Pico, lista alarmów krytycznych, pas 8 ostatnich zdarzeń (poll `/events` 1 s), stream down i WS down po stronie JS.

**Jak to ze sobą działa:**

Wątek `pico-uart-reader` aktualizuje telemetrię i `_last_stat_monotonic` pod `_telemetry_lock`. Endpoint `/status` i task asyncio czytają `alive` (wiek < `pico_stale_ms`, domyślnie 1000 ms). Task diagnostyczny porównuje snapshot z poprzednim tickiem i woła `EventLog.emit`, który jednocześnie loguje do `logging` (journald). UI polluje `/status` i `/events` niezależnie; alarmy stream/WS są lokalne w JS.

**Jak uruchomić / zbudować:**

```bash
cd pi
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
# Przeglądarka: http://<pi-ip>:8000/
# journalctl -u control-server -f   # zdarzenia w logu systemd
```

**Układ plików (dodane/zmienione):**

- `pi/src/event_log.py` — nowy
- `pi/src/config.py`, `pi/config.yaml` — `DiagnosticsConfig`
- `pi/src/pico_link.py` — żywość STAT, parse errors
- `pi/src/server.py` — `/events`, task diagnostyczny, rozszerzony `/status`
- `pi/src/web/index.html` — panel diagnostyczny

**Stan repo:** branch `phase3`, commity:
- `8388985` — `feat(pi): wykrywanie zywosci Pico po swiezosci STAT (KI-1)`
- `f6d23cd` — `feat(pi): endpoint /events i task diagnostyczny zdarzen`
- `f23dadc` — `feat(pi): panel diagnostyczny UI + prog batt z histereza`

**Odstępstwa od planu:**

- `stream_up` / `stream_down` nie są emitowane po stronie serwera — tylko alarm w JS (zgodnie z planem).
- Progi batt w UI zduplikowane jako stałe JS (3.0 / 4.4), bez ekspozycji w `/status`.

**Znane problemy / następne kroki:**

- **KI-1 zamknięte** w warstwie Pi/UI.
- KI-2: wyścig przy shutdown `pico-uart-reader` — Faza 5.
- KI-3: obrót streamu w CSS — bez zmian.
- Na stole: potwierdzić `pico_dead` po odłączeniu Pico > 1 s; batt z dzielnikiem vs placeholder GP26.
