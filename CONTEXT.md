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
bestemmingsnaam; reset-frases **`standaard`** / **`default`** / **`standard`** zetten terug naar de defaultmap
(`%APPDATA%\praatMaar\transcripts\`). Geen fuzzy match in v1.

- **Pill:** toont de actieve naam in idle (`indicator.py` / `set_destination`).
- **Tray:** beheer via menu-item **Bestemmingen** (`destinations_dialog.py`),
  naast Instellingen, Modules en Help — niet in het algemene Instellingen-scherm.
- **Logica:** `destinations.py` (normaliseren, matchen, padresolutie);
  wiring in `dictation.py`; commando-check in `Opnamesessie` vóór plakken.
- **Opslaan:** `recovery.save_transcript` naar actieve map; prune alleen default.
- **Plakken:** per bestemming `auto_paste` (default uit). Actief → die flag
  (klembord + plakken of alleen opslaan); geen actieve → globale Instellingen.

### herstel-audio

WAV’s van mislukte transcripties onder `recovery_dir()` (`%APPDATA%\praatMaar\recovery\`
of macOS Application Support). Beheer + opnieuw transcriberen via sectie
**Herstel-audio** in Instellingen (`settings.py`); transcriptie via
`dictation.retranscribe_recovery_wav` (geladen Whisper-model). Op macOS schrijft
het settings-kind `_recovery_retranscribe` terug zodat de parent (met model)
uitvoert. Herstel-transcriptie emitteert dezelfde `CycleEvent`-types als live
dicteren (`source: "recovery"`).

### module (praatMaar-module)

In-process uitbreiding, geregistreerd in `modules/registry.py`. Reageert op
**dicteercyclus-events** via `ModuleBus`. Gebruiker schakelt modules aan/uit
via tray **Modules** (`modules_dialog.py`); state in `config.json` onder
`modules.<id>.enabled`. v1: expliciete ingebouwde lijst (geen download/install).
Beslissing: [ADR-0003](docs/adr/0003-hybrid-module-system.md).

Voorbeeld: **inbox-spiegel** (`inbox-mirror`) kopieert opgeslagen transcripts
naar `%APPDATA%\praatMaar\inbox\`.

### dicteercyclus-event (`CycleEvent`)

Één lifecycle-moment in of rond de dicteercyclus, met stabiele `session_id`.
Types o.a. `cycle.started`, `transcript.partial`, `cycle.completed`,
`transcript.saved`, `destination.command`, `cycle.idle`. Contract:
`modules/_contract.py`. Emissie vanuit `Opnamesessie` (`emit_event`) en
herstel-pad in `dictation.py`.

### event-journal

Append-only JSONL (`events/events.jsonl` onder de app-datamap) — **hybride brug**
voor externe tools. `ModuleBus` schrijft elk event altijd; in-process modules
krijgen dezelfde payload. Schema: `schema_version` + `type` + payload-velden.

### local-first inference

AI-inferentie (STT, LLM, semantische analyse) draait op de machine van de
gebruiker; **geen cloud-inference als default**. LLM hoort in een **eigen
praatMaar-module** (`local-llm`) die capability `ai.semantic_analysis`
registreert; andere modules consumeren die. Eerste runtime: Ollama + Qwen2.5
Instruct. Beslissing: [ADR-0004](docs/adr/0004-local-first-inference.md).
Design: [local-llm module](docs/superpowers/specs/2026-07-23-local-llm-module-design.md).

### local-llm (module)

Builtin module (default uit) die Ollama/Qwen (v1) beheert: detectie, installatie-
begeleiding, model pull, en registratie van `ai.semantic_analysis`. Zelfde rang
als Meeting Buddy in tray **Modules**.

### agenda-review (Meeting Buddy)

Consumer van `ai.semantic_analysis`, gefaseerd: (1) **live samenvatting** in het
meeting-overzicht op configureerbare chunks, (2) **agendapunt-status** via LLM
(chunk `agenda_review`), (3) **vraag-van-anderen** via dezelfde review. Geen
eigen Ollama-client. Zonder klaarstaande LLM: heuristiek mag alleen
`open → treated`; geen vraagherkenning.

### agendapunt-status

Status van één agendapunt in Meeting Buddy (`TopicStatus`):

- **open** — nog niet substantieel besproken
- **treated** (`behandeld`) — wel substantieel besproken, mogelijk uit volgorde
- **sequential** (`sequentieel behandeld`) — treated én alle voorgangers minstens
  sequential (automatische inhaal; bij het eerste punt valt dit samen met treated)
- **confirmed** (`bevestigd behandeld`) — sequential dat **opnieuw** substantieel
  is besproken

Alleen substantiële bespreking telt; noemen of doorlopen in de opening niet.
Oude term “discussed” ≈ minstens **sequential** (journal-checkbox / ✓).

### meeting-fase

LLM-inschatting van waar de meeting zit: `opening` \| `body` \| `closing`. In
`opening` mogen geen latere agendapunten naar **treated** (wel het
opening-punt zelf).

### vraag-van-anderen

Door de LLM herformuleerde open vraag uit het transcript, bedoeld als hint voor
de host. Filter op `audio.speaker_detection`: rol ≠ `ME` (`OTHER` en `UNKNOWN`
mogen). Geen regex-heuristiek wanneer de LLM-review actief is; zonder LLM geen
automatische vragenlijst.
