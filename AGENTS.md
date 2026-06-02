# AGENTS.md — role i zasady dla agentów

> Czytasz to jako agent (człowiek lub AI) pracujący w tym repo. **Zanim cokolwiek
> zrobisz, przeczytaj `PROJECT.md`** — to jedyne źródło prawdy. Ten plik opisuje:
> kto za co odpowiada, czego nie wolno ruszać i jak wygląda jedna iteracja pracy.

---

## 1. Role

### Architekt — Claude (poza Cursorem)
Projektuje architekturę, zadaje pytania projektowe, pilnuje kontraktów i spójności
między platformami, produkuje **prompty dla agentów** (markdown artifact).
**Nie pisze kodu do repo.** Aktualizuje `PROJECT.md` i `ITERATIONS.md`.

### Pi Agent (Cursor)
- **Stack:** Python, FastAPI, asyncio, uvicorn.
- **Katalog:** `pi/` (i tylko `pi/`).
- **Odpowiada za:** serwer WiFi, stream kamery, most UART do Pico, UI testowe, systemd.

### Pico Agent (Cursor)
- **Stack:** C++, Pico SDK, cmake, arm-none-eabi-gcc.
- **Katalog:** `pico/` (i tylko `pico/`).
- **Odpowiada za:** PWM silników (MX1508), serwa, watchdog, czujnik HC-SR04, ADC, telemetria.

### ESP32 Agent (Cursor)
- **Stack:** C++, Arduino-ESP32, LVGL.
- **Katalog:** `esp32/` (i tylko `esp32/`).
- **Odpowiada za:** pilot bezprzewodowy + panel statusu (klient WiFi do API Pi).

**Zasada izolacji:** każdy agent pracuje wyłącznie w katalogu swojej platformy.
Jeden agent = jedna platforma = jedna sesja Cursora. Nie edytuj cudzego katalogu.
Pliki w roocie (`PROJECT.md`, `README.md`, `AGENTS.md`, `ITERATIONS.md`, `.cursor/`)
zmienia architekt; agent może je tylko czytać (wyjątek: dopisanie własnego
podsumowania do `ITERATIONS.md` i `docs/iterations/`).

---

## 2. Czego NIE wolno ruszać bez architekta

Kontrakty z `PROJECT.md` są zamrożone. Bez zgody architekta agent **nie zmienia**:
- protokołu UART (komendy, format ramek),
- API WiFi (ścieżki, kształt JSON, format WS),
- mapy pinów i domen zasilania,
- limitów serw (pan 10–170°, tilt 30–150°) i czasów watchdoga (~300 ms Pico / 500 ms Pi).

Jeśli zadanie wymaga zmiany kontraktu — **zatrzymaj się i zgłoś to architektowi**,
nie improwizuj. Lepiej zapytać niż rozjechać dwie platformy.

---

## 3. Workflow jednej iteracji

1. **Review stanu repo** — architekt robi krótki przegląd (project knowledge search /
   `ITERATIONS.md` + `docs/iterations/`).
2. **Pytania projektowe** — architekt zadaje 4–7 pytań z opcjami literowanymi i
   rekomendacją (np. „rekomendacja: `1=a, 2=b`").
3. **Odpowiedzi** — Adrian odpowiada zwięźle (np. `1=a, 2=c, 3=b`).
4. **Prompt** — architekt produkuje prompt dla Cursora jako **markdown artifact**
   (kontekst, zakres, kontrakty, edge case'y, definicja „done").
5. **Cursor** — tryb **Plan** → akceptacja przez Adriana → **Agent** („implementuj").
6. **Zamknięcie** — commit w Conventional Commits, postmortem w `ITERATIONS.md`,
   plan i podsumowanie sesji w `docs/iterations/`.

---

## 4. Obowiązkowe podsumowanie sesji

**Po każdej sesji generowania kodu agent przygotowuje podsumowanie.** Cel: żeby
Adrian, architekt albo inny agent mógł wrócić do wiedzy bez czytania całego diffa.

- Utwórz `docs/iterations/<faza>-<krótki-tytuł>.md` na wzór `docs/iterations/_TEMPLATE.md`.
- Dopisz krótki wpis (postmortem) do `ITERATIONS.md` z linkiem do powyższego pliku.
- Podsumowanie ma odpowiadać na: **co zrobiono, jak to ze sobą działa, jak uruchomić/
  zbudować, układ plików, stan repo (branch/commit), znane problemy i następne kroki.**

Podsumowanie piszesz **swoimi słowami o faktycznym stanie kodu** — nie kopiuj
promptu. Jeśli coś odbiega od planu, napisz to wprost.

---

## 5. Commity — Conventional Commits

Format: `typ(scope): opis`

- **typy:** `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `build`
- **scope:** `pi`, `pico`, `esp32`, `docs`, `repo`
- przykłady:
  - `feat(pico): drive PWM MX1508 + watchdog 300ms`
  - `fix(pi): wykrywanie Pico przez heartbeat zamiast otwarcia portu`
  - `docs(repo): aktualizacja planu fazowego w PROJECT.md`

---

## 6. Higiena techniczna (częste pułapki)

- **Końce linii LF, nie CRLF** — pliki czytane wprost przez Linuksa (`*.service`,
  `*.sh`, `*.yaml`, `*.mdc`) muszą mieć LF. CRLF psuje systemd (`status=217/USER`)
  i shebangi. Repo wymusza to przez `.gitattributes`.
- **Pi:** kod ma działać **bez podłączonego Pico** (degradacja, nie crash).
- **Pico:** bez dynamicznej alokacji; watchdog niezależny od reszty logiki.
- **Wszyscy:** żadnych sekretów w repo; konfiguracja przez pliki configów/`.env`.
