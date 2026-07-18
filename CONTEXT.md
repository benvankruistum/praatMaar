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
te stelen van het actieve invoerveld (`indicator.py`). Op Windows via een
`WS_EX_NOACTIVATE`-shim; de macOS-tegenhanger is nog een open vraag (zie
`docs/archive/HANDOFF-mac-port.md` en `docs/STATUS.md`).
