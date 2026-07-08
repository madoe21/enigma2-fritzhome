# Codebase map (onboarding 2026-07-08)

**enigma2-fritzhome** — Enigma2 (OpenATV 7.6) plugin: FRITZ!Box Smart Home
(DECT switches/thermostats) control on the TV. Python.

## Layout
- `src/fritz_home/plugin.py` (~244 LOC) — entry.
- `src/fritz_home/api.py` (~496) — FRITZ!Box Smart-Home HTTP API (login/SID,
  device list, switch/thermostat commands). **Data layer.**
- `src/fritz_home/screens.py` (~1311) — enigma2 GUI (largest file, all the
  enigma2 coupling).
- `res/`, `control/`, `build/` (gitignored ipk).

## Conventions
- Enigma2 Py3; network calls need timeouts (main reactor thread).
- SID auth: cache the session id; re-login on expiry.

## Kodi portability: **monolithic (data layer already separate)**
3 files import enigma2, concentrated in `screens.py`/`plugin.py`. `api.py` is
already a clean HTTP client. Port = extract `api.py` to `core/` (verify
enigma2-free, abstract config), add `platform/kodi/`. Target shape: the
core/-split plugins (lotto/stocks/weather).
