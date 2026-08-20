# Product specification — Bestandstranscriptie (file-transcription)

## Status

**Accepted** — 2026-08-18 (human owner in chat: slice + beslissingen 1–3).

Niet in v1.0-scope. Experimentele opt-in module.

## Context

praatMaar is een local-first Windows-primaire dicteerapp (hotkey → `Opnamesessie`
→ Faster-Whisper → plakken). Modules zijn in-process via `ModuleBus` /
`PraatMaarModule` ([ADR-0003](../../adr/0003-hybrid-module-system.md)).
v1.0-belofte: Windows core-dicteercyclus; Meeting Buddy / local-llm / chunk-STT
blijven experimenteel opt-in
([v1.0-scope](2026-08-01-v1-support-scope-product.md)).

**Herstel-audio** transcribeert alleen WAV’s in `recovery.recovery_dir()`
(`app/recovery_actions.py`), met pad-sandbox, optioneel plakken, en
`source: "recovery"`. Dat dekt geen door de gebruiker gekozen bestanden.

`SharedWhisper` (`modules/whisper.py`): één geladen model; live dicteren via
`dictation_priority` / `locked_model()`; modules horen `try_locked_model` te
gebruiken.

Teamoverleg (product-owner, ux-product-design, privacy-security,
core-python-architect, audio-speech) 2026-08-18. Locked human decisions:

1. `.txt`-naam = tijdstempel (geen bronstam); bronnaam alleen in de dialoog.
2. Transcriberen in plakjes (~30 s) met yield naar de dicteercyclus tussen
   plakjes; decode buiten de model-lock.
3. Event-journal: `source: "file"` + lengte + pad van het **opgeslagen `.txt`**;
   geen bronpad of bronnaam.

## Problem

- **User:** Windows-gebruiker (primair) die praatMaar al lokaal gebruikt, of
  privacy-bewust bestaande opnames niet naar de cloud wil sturen.
- **Situation:** Er ligt audio op schijf (memo, interview, les, export) die niet
  via de dicteer-sneltoets is opgenomen.
- **Problem:** Geen pad voor user-gekozen bestanden; herstel-audio is een andere
  job (mislukte dicteercyclus).
- **Impact:** Die audio gaat naar een ander (vaak cloud) hulpmiddel, of blijft
  ongetranscribeerd, terwijl Faster-Whisper al lokaal geladen is.
- **Desired outcome:** Bestanden kiezen → lokale transcriptie → tekst op schijf,
  zonder de live dicteercyclus te breken of de pill te overloaden.

## Goal

Kleinste coherente opt-in: gebruiker wijst één of meer lokale WAV-bestanden aan;
praatMaar transcribeert ze lokaal met het geladen model, in plakjes zodat
dicteren tussendoor voorrang krijgt; bewaart discrete timestamp-`.txt` via de
actieve bestemming; toont status in een eigen dialoog.

## Non-goals

- Uitbreiden of hergebruiken van Instellingen → Herstel-audio als file-picker.
- Migratie van herstel-audio/bestemmingen naar modules (ADR-0003 “later”).
- Cloud-STT/LLM; Meeting Buddy-capture/diarization/agenda-review.
- Auto-plakken (`host.paste`) of de dicteer-doel-focus stelen zonder user-open.
- Sidecar `.txt` naast het bronbestand.
- Map importeren, watcher, recursie, parallelle Whisper-jobs.
- Afspelen, in-app editor, per-file spraaktaal, extra Instellingen-toggles.
- Indicator (pill) als job-status; `notify_state` voor deze bron.
- Mixing in **Recente transcripts** (dat menu is dicteer-`.txt`).
- Onzichtbare achtergrond-run zonder dialoog.
- MP3/M4A/FLAC (pas na spike op de frozen Windows-build).
- ffmpeg CLI bundelen.
- v1.0-ondersteuningsclaim of graduation uit “experimenteel”.
- Implementatie op branch `cursor/whisper-decode-settings`.

## Users and scenarios

**Primair:** Windows-gebruiker met lokale WAV’s.

1. Modules → Bestandstranscriptie aan → actie → dialoog → 1 WAV → `.txt` in
   bestemmingsmap → optioneel Naar klembord (geen plakken).
2. Multi-select van N WAV’s → sequentiële wachtrij → per file klaar/fout; één
   mislukte file stopt de rest niet.
3. Tijdens een plakje start de gebruiker een dicteercyclus → huidige plakje mag
   uitlopen; volgende plakjes/files wachten tot dicteren idle is.
4. Start terwijl `Opnamesessie` opneemt/verwerkt → weigeren, melding in de
   dialoog (zelfde intentie als `recovery.busy`).
5. Herstel-audio blijft ongewijzigd: alleen recovery-WAV’s.

## Functional requirements

- **FR-01** Nieuwe ingebouwde praatMaar-module, id `file-transcription`, in
  `modules/registry.py`. `default_enabled() == False`. Label experimenteel in
  Modules-UI (gebruik het echte kebab-id) en Help.
- **FR-02** Enabled module biedt één `ModuleAction` (`in_tray=True`, niet
  `in_tray_root`) die een eigen PySide6-dialoog opent. Geen extra
  Instellingen-sectie. Tweede actie brengt dezelfde dialoog naar voren.
- **FR-03** Dialoog eerst (niet picker-only): intro, actieve bestemming, WAV-regel
  zichtbaar vóór de OS-picker. Multi-select, alleen lokale bestanden. Geen
  map-select.
- **FR-04** Must-have formaat: **WAV** (case-insensitive). Andere extensies:
  per-file fout of niet toevoegen, geen stille skip. Decode via bestaande
  Faster-Whisper/PyAV-pad (`faster_whisper.audio.decode_audio`), niet via een
  gebundelde ffmpeg.exe.
- **FR-05** Jobs sequentieel (geen parallelle `transcribe` op `SharedWhisper`).
- **FR-06** Inferentie: geladen `SharedWhisper` + `Opnamesessie.transcribe_kwargs()`
  (inclusief `speech_language`). Geen cloud, geen tweede model, geen
  `speech-to-text`-realtime-kwargs.
- **FR-07** Start weigeren als `session.is_recording` of `session.is_processing`,
  of model niet `is_ready`. Geen stille wachtrij bij start. Tweede batch terwijl
  een job loopt: weigeren.
- **FR-08** File-jobs gebruiken **niet** `dictation_priority` / `locked_model()`.
  Decode naar 16 kHz mono float32 **buiten** de model-lock. Transcribeer in
  plakjes van **~30 s**; lock alleen tijdens één plakje (`try_locked_model`);
  tussen plakjes en tussen files yielden als `dictation_active`. Live
  dicteercyclus mag niet achter een *volgend* plakje of bestand staan.
- **FR-09** Eén in-flight Faster-Whisper-plakje is niet cooperatief cancelbaar.
  Dialoog/Help vermelden dat dicteren kan wachten tot het **huidige plakje**
  klaar is.
- **FR-10** Annuleren: rest van de wachtrij stopt na het huidige plakje;
  bronbestanden blijven onaangeroerd. Sluiten tijdens een job = zelfde als
  wachtrij stoppen; dialoog blijft tot de in-flight call klaar is (geen
  achtergrond-run zonder UI).
- **FR-11** Opslaan: discrete `.txt` in de map van de actieve bestemming, anders
  default transcripts-map. **Niet** `resolve_append_file`. Bestandsnaam
  `file_YYYY-MM-DD_HHMMSS.txt` (plus `_N` bij botsing) — **geen** bronstam, zodat
  Recente transcripts (timestamp-stem `^YYYY-MM-DD_HHMMSS`) ze niet toont.
  Snapshot van de bestemming op Start. Bron-audio niet kopiëren naar
  `recovery_dir()`; geen `preserve_audio` op fout.
- **FR-12** Geen `host.paste` en geen `auto_paste`. Optioneel: knop **Naar
  klembord** voor een geslaagd item (user-initiated). Geen auto-copy.
- **FR-13** Dialoog toont per file: wacht / bezig / klaar (opgeslagen `.txt`-naam)
  / fout / overgeslagen, plus de **bronbestandsnaam** in de rij (alleen UI).
  Job-status staat **niet** op de pill. Hervatten na dicteren activeert de
  dialoog niet.
- **FR-14** `CycleEvent` via `ModuleBus`, één `session_id` per file: minstens
  `cycle.transcribing` → `cycle.completed` of `cycle.error` → `transcript.saved`
  bij geslaagde save → `cycle.idle`. `source: "file"`. Geen
  `recovery.retranscribed`; geen `recovery_path`. Optioneel in-memory
  `audio_path` voor UI; **journal stript dat veld** (ADR-0003 aanvulling
  2026-08-18). Journal: geen transcripttekst, geen bronpad/bronnaam; wel
  `transcript_chars` en op `transcript.saved` het pad van het `.txt`.
- **FR-15** `inbox-spiegel` mag kopiëren op `transcript.saved` (disclose in
  modulebeschrijving: inbox staat default aan). `speaker-detection` mag
  file-jobs niet als live-mic behandelen. Recente transcripts: geen
  file-job-`.txt`.
- **FR-16** Fout in de module mag de dicteercyclus niet breken (ADR-0003).
  Worker-exceptions blijven op de job-thread. `error` op events en logs: i18n /
  generiek, geen `str(exc)` met paden of transcript.
- **FR-17** i18n `nl` / `en` / `de`. Modulenaam **Bestandstranscriptie**; actie
  **Bestanden transcriberen…**.
- **FR-18** User-opened dialoog mag focus hebben. Geen extra venster/pill-focus
  wanneer de gebruiker die dialoog niet heeft geopend. Picker-only reads: alleen
  paden uit de picker; geen journal/config-replay van bronpaden.
- **FR-19** Alleen `modules.file-transcription.enabled` als nieuwe config-key.
  Gekozen bronpaden niet in `config.json`.

## Quality requirements

- **QR-01** Local-first inference; geen stille cloud-fallback (ADR-0004).
- **QR-02** Privacy: bronbestanden blijven waar ze zijn; transcripts alleen in
  bestemmings-/defaultmap (+ inbox-spiegel als aan). Journal/logs zonder
  transcript en zonder bronpad. Default-off om privacy, niet alleen “experimenteel”.
- **QR-03** Toestanden in de dialoog ondubbelzinnig (wacht / bezig /
  gepauzeerd-wegens-dicteren / klaar / fout / geannuleerd).
- **QR-04** Toetsenbord: picker + lijst + Start/Annuleren/Sluiten bedienbaar;
  status in tekst, niet alleen kleur. Esc in idle = sluiten; tijdens job =
  wachtrij stoppen.
- **QR-05** UI blijft responsive (werk op achtergrondthread).
- **QR-06** Windows 10/11 must; macOS should (zelfde Qt-dialoog + `SharedWhisper`);
  Linux could, experimenteel, geen extra belofte.
- **QR-07** Tests: busy-refuse; sequential; plakjes yielden naar fake dicteren;
  append-modus genegeerd; geen paste; `source != "recovery"`; journal zonder
  `audio_path`/transcript; recovery_dir ongewijzigd na succes én fout; module-fout
  breekt dicteren niet; WAV-happy-path met mock-model; Recente-transcripts-stem
  matcht `file_…` niet.

## Supported platforms

| Platform | Deze feature |
|----------|----------------|
| Windows 10/11 | Must |
| macOS Apple Silicon (bron/runtime) | Should |
| Linux | Could (experimenteel platform) |

Geen WASAPI, geen extra TCC voor microfoon (geen capture).

## Edge cases

- Lege / geen-spraak: per-file fout (`rec.no_speech`-intentie, eigen i18n-key);
  wachtrij gaat door.
- Unreadable / locked / ontbrekend pad / geen geldige WAV (ADPCM etc.): per-file
  fout.
- Actieve bestemming onbereikbaar: job-fout, bron ongewijzigd.
- Append-bestemming actief: discrete `file_*.txt` in **die map**; append-log
  ongewijzigd; hint in de UI.
- Modelwissel/herstart tijdens job: job ongeldig na herstart, niet hervatten.
- Multi-instance: bestaande single-instance.
- Meeting Buddy live STT deelt `try_locked_model`: fair lock; file-plakje kan
  Buddy kort stalllen (documenteren; geen `dictation_priority` om te “winnen”).

## Privacy considerations

Audio en transcripts blijven op het apparaat. Geen upload. User kiest bronpaden
(UI mag namen tonen; journal/config/log niet). Niet schrijven naar
`recovery_dir()`. Decode-temps (als die ontstaan) wissen in `finally`.
Inbox-spiegel (default aan) kopieert `.txt` — vermelden bij enable/beschrijving.
Klembord alleen na expliciete knop. Transcripts onversleuteld (bestaand model).

Zie `/privacy-security-review` op de implementatie-diff.

## Dependencies

- `SharedWhisper`, geladen model (splash).
- `ModuleBus` / `CycleEvent` / registry / `ModuleAction`.
- `destinations` voor mapresolutie (niet append).
- Nieuwe discrete-save helper (niet 1-op-1 `retranscribe_recovery_wav`).
- PySide6-dialoog in het module-package (ADR-0005).
- ADR-0003 aanvulling 2026-08-18 (`source: "file"`, journal-redactie `audio_path`).

## Risks

| Risico | Mitigatie |
|--------|-----------|
| Lang plakje blokkeert dicteren | ~30 s slices; yield ertussen; copy over huidig plakje |
| Hele-file decode in RAM (~230 MB/uur) | Residual; geen harde cap in deze slice; later herzien |
| Verwarring met herstel-audio | Aparte module + intro-copy |
| Pill toont “transcriberen” | Geen `notify_state` |
| Experimental-badge mist kebab-ids | `_EXPERIMENTAL_IDS` op echte `module.id` |
| `_reload_modules` laat orphan thread achter | `ModuleWithShutdown` join vóór reload |

## Acceptance criteria

- Given de module staat uit, When de gebruiker het tray-menu opent, Then er is
  geen Bestandstranscriptie-actie (wel zichtbaar als uit in Modules).
- Given de module staat aan en het model is geladen, When de gebruiker de actie
  kiest, Then opent een dialoog (geen focus-steal door de pill).
- Given de gebruiker selecteert één geldige WAV en start, When transcriptie
  slaagt, Then ligt een discrete `file_YYYY-MM-DD_HHMMSS.txt` in de
  bestemmings- of defaultmap, de dialoog toont bronnaam + die `.txt`, en er is
  **niet** geplakt.
- Given multi-select van drie geldige WAV’s, When de job loopt, Then volgorde is
  de selectievolgorde en een fout op file 2 laat file 3 nog lopen.
- Given `Opnamesessie` neemt op, When de gebruiker Start kiest, Then de job
  start niet en de gebruiker ziet een busy-melding in de dialoog.
- Given een file-job heeft nog plakjes of files, When een live dicteercyclus
  start, Then die cyclus krijgt het model na het huidige plakje, vóór het
  volgende; de dialoog komt niet naar voren.
- Given herstel-audio, When de gebruiker Instellingen opent, Then de sectie
  toont alleen recovery-WAV’s.
- Given `transcript.saved` met `source: "file"`, When inbox-spiegel aan staat,
  Then het `.txt` wordt gekopieerd zoals bij live save.
- Given Recente transcripts, When een file-job `.txt` in de bestemmingsmap staat,
  Then verschijnt die **niet** in de top-5.
- Given event-journal, When een file-job slaagt, Then events hebben
  `source: "file"`, geen transcripttekst, geen bronpad/bronnaam.
- Given de module gooit tijdens een job, When daarna een dicteercyclus start,
  Then dicteren werkt nog.
- Given de gebruiker sluit de dialoog tijdens een job, When bevestigd, Then de
  rest stopt na het huidige plakje en er is geen job zonder dialoog.

## Required evidence

- Unit: busy-refuse, sequential, slices+yield, geen paste, geen append,
  `file_`-naam, journal-redactie, recovery_dir ongewijzigd, `source: "file"`,
  module-isolatie (mock `SharedWhisper`).
- UI-smoke Windows: picker → job → save-pad zichtbaar; pill blijft dicteer-only;
  geen focus-steal bij hervatten.
- `/privacy-security-review` op pad/journal/inbox/klembord/logs.
- `/ux-state-review` op dialoogstates vs dicteercyclus/pill (optioneel bij
  implementatie).
- Help + Modules-copy: experimenteel, local-first, relatie tot herstel-audio,
  inbox-spiegel-side-effect.
- Geen implementatie op `cursor/whisper-decode-settings`.

## Agent ownership

| Area | Owner | Consult |
|------|--------|---------|
| Module, `CycleEvent`, save-routing, PySide6-dialoog, tests | **`core-python-architect`** | `audio-speech`, `ux-product-design` |
| Decode, 30 s-plakjes, lock/yield | `audio-speech` | `core-python-architect` |
| Dialoog-IA, copy, busy/pause/error | `ux-product-design` | `core-python-architect` |
| macOS file dialog / focus (smoke) | `macos-platform` | `ux-product-design` |
| Privacy | `privacy-security` (review) | — |
| Acceptatie-evidence | `quality-release` | — |
| Docs/i18n na bouw | `/update-documentation` | — |
| Productacceptatie | `product-owner` + human owner | — |

Windows-native adapters en installer: **buiten** deze slice tenzij een latere
non-WAV-beslissing bundling forceert.

## Open questions

Geen blocking. Uitgesteld:

- MP3/M4A/FLAC na frozen-build spike (`audio-speech` + `windows-platform`).
- Harde max duur/grootte als RAM-probleem blijkt.
- Sidecar-naast-bron als aparte, expliciete keuze.
- Bestemming wijzigen vanuit de dialoog (blijft tray **Bestemmingen**).
