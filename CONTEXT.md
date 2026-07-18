# CONTEXT — praatMaar

Glossarium van de domein- en architectuurtermen van deze codebase. Gebruik deze
termen exact in issues, specs, tests en refactor-voorstellen; wijk niet uit naar
synoniemen. Beslissingen staan in `docs/adr/`.

## Termen

### platform-seam (`host`)

De ene module waarachter alles zit wat per besturingssysteem verschilt: de
plak-toets, het automatisch meestarten en de map voor gebruikersdata. De rest van
de app praat alleen met `host` en raakt nooit rechtstreeks `winreg`, `ctypes` of
een OS-specifieke plak-toets aan.

- **Interface:** `Host`-Protocol — `paste()`, `set_autostart()`,
  `is_autostart_enabled()`, `app_dir()`, `acquire_single_instance()`.
- **Adapters:** `host._win` (Windows, absorbeert het vroegere `autostart.py`) en
  `host._mac` (macOS; `paste`/`app_dir` compleet, LaunchAgent nog ongetest).
- **Selectie:** één instantie, gekozen op `sys.platform` (`host.default`).
- Heet bewust `host` en niet `platform` (dat zou de stdlib schaduwen).
- Buiten scope van de seam (voorlopig): het no-activate indicator-venster — een
  ander soort, GUI-toolkit-gebonden seam.

### dicteercyclus

De toestandsketen van één dicteeractie: opname → transcriberen → geannuleerd →
fout, terug naar idle. Gemodelleerd als `RecordingState` in `indicator.py`. De
lifecycle-logica zit in `Opnamesessie` (`opnamesessie.py`); `dictation.py` is de
entrypoint (splash, hotkeys, tray, wiring).

### Opnamesessie

De runtime van één dicteercyclus: microfoonbuffer, transcriptie-thread,
klembord/plakken via geïnjecteerde `Host` en recovery-hooks. Module:
`opnamesessie.py`. Toetsenbordrouting blijft in `dictation.py`.

### indicator (pill)

De kleine, altijd-zichtbare status-pill die de dicteercyclus toont zonder de focus
te stelen van het actieve invoerveld. Package `indicator/`:

- **Contract:** `RecordingState`, `notify_state` / `push_level` / `reset_levels`
  (`indicator._contract`) — platform-neutraal.
- **Windows:** tkinter + `WS_EX_NOACTIVATE` (`indicator._win`).
- **macOS:** native overlay via AppKit `NSPanel` / `nonactivatingPanel` (PyObjC,
  `indicator._mac`) — [ADR-0002](docs/adr/0002-macos-native-overlay-indicator.md).
- **Façade:** `indicator.RecordingIndicator` lazy per `sys.platform`.

### i18n (UI-taal)

Interface-teksten via `i18n.py` en JSON onder `locales/` (`nl`/`en`/`de`).
Config: `ui_language`. Spraakherkenning is apart: `speech_language` → Whisper
via `Opnamesessie.language`.

### bestemming

Een benoemd transcriptdoel: **naam + map** in `config.json` (`destinations`).
De actieve bestemming is **sticky** — blijft gelden tot je wisselt of reset.
Wisselen via stem: na transcriptie exacte match (genormaliseerd) op de
bestemmingsnaam; reset-frase **`standaard`** zet terug naar de defaultmap
(`%APPDATA%\praatMaar\transcripts\`). Geen fuzzy match in v1.

- **Pill:** toont de actieve naam in idle (`indicator.py` / `set_destination`).
- **Tray:** beheer via menu-item **Bestemmingen** (`destinations_dialog.py`),
  naast Instellingen en Help — niet in het algemene Instellingen-scherm.
- **Logica:** `destinations.py` (normaliseren, matchen, padresolutie);
  wiring in `dictation.py`; commando-check in `Opnamesessie` vóór plakken.
- **Opslaan:** `recovery.save_transcript` naar actieve map; prune alleen default.
