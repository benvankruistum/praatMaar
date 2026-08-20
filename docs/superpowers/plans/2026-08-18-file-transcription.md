# Bestandstranscriptie Implementation Plan

> **For agentic workers:** Use `/agent-handoff` per task. Steps use checkbox
> (`- [ ]`) syntax for tracking. Do not implement until the user asks to execute.

**Goal:** Experimentele module `file-transcription`: gebruiker kiest één of meer
WAV’s, lokale sequentiële transcriptie in ~30 s-plakjes via `SharedWhisper`,
discrete `file_YYYY-MM-DD_HHMMSS.txt` in de actieve bestemming, status in een
eigen dialoog — zonder herstel-audio, pill of auto-plakken.

**Spec:** [2026-08-18-file-transcription-product.md](../specs/2026-08-18-file-transcription-product.md) (Accepted)  
**ADR:** [0003 aanvulling 2026-08-18](../../adr/0003-hybrid-module-system.md)  
**Architecture:** Nieuwe builtin onder `modules/_builtin/file_transcription/`.
Jobs (geen Qt) + dialoog (Qt). Composition root bindt een smalle `FileJobHost`
(busy / `transcribe_kwargs` / discrete save / `emit`) ná `load_enabled_modules`;
`Opnamesessie` komt niet op `ModuleContext`. `EventJournal` stript `transcript`
én `audio_path`. Lock: `try_locked_model` only.

**Tech stack:** Python 3, PySide6, Faster-Whisper 1.2.1 (`decode_audio` + numpy
slices), pytest, bestaande `i18n` / `destinations` / `SharedWhisper`.

## Global constraints

- Feature branch: `cursor/file-transcription` vanaf `main`. Nooit committen op
  `main`. Niet mengen met stash `WIP whisper-decode-settings`.
- Do not kill/restart the running app unless the user asks.
- Windows is primary evidence; macOS should; Linux could.
- WAV-only; geen ffmpeg.exe; geen cloud.
- Geen `dictation_priority` / `locked_model()` voor file-jobs.
- Geen `notify_state` / pill voor deze bron.
- Geen nieuwe config-keys behalve `modules.file-transcription.enabled`.
- CONTEXT-termen exact: module, dicteercyclus, Opnamesessie, bestemming,
  herstel-audio, CycleEvent, SharedWhisper, bestandstranscriptie.

## File map

| File | Rol |
|------|-----|
| `modules/_contract.py` | Optioneel `CycleEvent.audio_path` |
| `modules/journal.py` | Strip `audio_path` (naast `transcript`) |
| `modules/registry.py` | Builtin `FileTranscriptionModule` |
| `modules/_builtin/file_transcription/` | `module.py`, `jobs.py`, `dialog.py` |
| `app/recovery_actions.py` | `save_transcript_discrete` (`file_`-stem) |
| `app/module_bindings.py` (nieuw) | Bind `FileJobHost` na module-load |
| `dictation.py` | `_reload_modules` roept bind aan |
| `ui/dialogs/modules.py` | Experimental-id `file-transcription` (kebab) |
| `locales/{nl,en,de}.json` | Module + dialoog-copy |
| `docs/modules-integration.md` | `source: "file"`, journal-redactie |
| `docs/STATUS.md`, `CHANGELOG.md`, help | Experimentele module |
| `tests/test_journal.py` (of bestaand) | Redactie `audio_path` |
| `tests/test_file_transcription_jobs.py` | Queue, slices, lock, save, events |
| `tests/test_save_transcript_discrete.py` | Prefix, geen append |
| `tests/test_modules_registry.py` | id, default uit |

## Task order overview

1. CycleEvent + journal-redactie (TDD)
2. Discrete `file_`-save helper (TDD)
3. Job-engine: WAV-gate, decode, 30 s-plakjes, lock/yield, events (TDD)
4. Module + `FileJobHost`-bind + shutdown
5. Dialoog + locales
6. Docs / Help / STATUS / CHANGELOG
7. Privacy-review + Windows smoke / AC-matrix

---

### Task 1: CycleEvent.audio_path + journal-redactie

**Owner:** `core-python-architect`  
**Consult:** `privacy-security`  
**Review:** `privacy-security` (op diff, Task 7)  
**Depends on:** none

**Files:**
- Modify: `modules/_contract.py`, `modules/journal.py`
- Test: bestaande journal-tests (uitbreiden) of `tests/test_journal.py`

**In scope:**
- [ ] Optioneel veld `audio_path: str | None = None` op `CycleEvent`; in `to_dict`
      alleen als gezet
- [ ] `EventJournal.write` verwijdert `audio_path` vóór JSONL (net als `transcript`)
- [ ] `recovery_path` ongewijzigd voor herstel-audio
- [ ] Geen nieuw `CycleEventType`

**Out of scope:**
- Module/UI; emitters voor `source: "file"`

**Implementation notes:**
- In-memory `on_event` mag `audio_path` blijven zien; alleen het journal strippen.
- `error` nog niet sanitizen in deze task (hoort bij jobs: i18n, geen `str(exc)`).

**Verification:**
- [ ] Automated: journalregel met `audio_path` in het event bevat het veld niet;
      `transcript` → `transcript_chars` blijft werken; `path` van `.txt` blijft
- [ ] Manual: n.v.t.

**Completion criteria:**
- FR-14 journal-helft; ADR-0003 aanvulling 2026-08-18

**Handoff:** `/agent-handoff` → `core-python-architect`

---

### Task 2: `save_transcript_discrete`

**Owner:** `core-python-architect`  
**Consult:** `privacy-security` (naamgeving)  
**Review:** —  
**Depends on:** none (parallel met Task 1)

**Files:**
- Modify: `app/recovery_actions.py` (of dunne helper ernaast als dat schoner is)
- Test: `tests/test_save_transcript_discrete.py`

**In scope:**
- [ ] `save_transcript_discrete(text, *, active_destination, destinations_list) -> Path`
- [ ] Map via `destinations.resolve_save_dir` — **nooit** `resolve_append_file`
- [ ] Stem `file_YYYY-MM-DD_HHMMSS` + `_N` via bestaande `_unique_path`
- [ ] Prune alleen in de default transcripts-map (zelfde regel als `save_transcript`)
- [ ] `retranscribe_recovery_wav` blijft `save_transcript_routed` gebruiken

**Out of scope:**
- Clipboard/paste; recovery-sandbox

**Implementation notes:**
- Prefix `file_` zorgt dat `parse_transcript_stem` faalt → Recente transcripts
  negeert deze files (FR-11 / FR-15).
- Geen bronstam in de bestandsnaam.

**Verification:**
- [ ] Automated: schrijft naar bestemmingsmap; append-log ongewijzigd; naam matcht
      `^file_\d{4}-\d{2}-\d{2}_\d{6}`; `parse_transcript_stem` is `None`
- [ ] Manual: n.v.t.

**Completion criteria:**
- FR-11

---

### Task 3: Job-engine (geen Qt)

**Owner:** `core-python-architect`  
**Consult:** `audio-speech`  
**Review:** `audio-speech` (decode/slice/lock)  
**Depends on:** Task 1, Task 2

**Files:**
- Create: `modules/_builtin/file_transcription/jobs.py`
- Create: `tests/test_file_transcription_jobs.py`

**In scope:**
- [ ] WAV-gate: bestaat, suffix `.wav` (case-insensitive), decodeerbaar
- [ ] Decode **buiten** lock: `faster_whisper.audio.decode_audio(path, sampling_rate=16000)`
      (injecteerbaar in tests)
- [ ] Slices ~30 s numpy @ 16 kHz; `try_locked_model` per slice; generator
      exhausten in de `with`
- [ ] Tussen slices/files: wachten terwijl `whisper.dictation_active` of
      `host.is_busy()` (poll, geen `dictation_priority`)
- [ ] Start-refuse als `host.is_busy()` of model niet ready of worker al loopt
- [ ] Per file: `session_id`; events `transcribing` → `completed`/`error` →
      `transcript.saved` (alleen succes) → `idle`; `source: "file"`;
      in-memory `audio_path`; `path` alleen op saved `.txt`
- [ ] Lege tekst → per-file error, rest gaat door
- [ ] Cancel = vlag; huidig plakje loopt uit; rest niet starten
- [ ] `error` i18n/generiek; geen pad/transcript in event of print
- [ ] Nooit `preserve_audio` / schrijven naar `recovery_dir()`
- [ ] Injecteerbare `FileJobHost` + fake Whisper in tests

**Out of scope:**
- Qt-dialoog; registry; echte Faster-Whisper in CI

**Implementation notes:**
- Protocol `FileJobHost`: `is_busy()`, `transcribe_kwargs()`, `save_discrete()`,
  `emit()`.
- `SLICE_SECONDS = 30.0`.
- Meeting Buddy deelt de lock fair; niet “winnen” met priority.
- Decode-temps (als decode_audio die maakt) in `finally` wissen.

**Verification:**
- [ ] Automated: busy-refuse; sequential; slice 2 wacht tot fake dicteren klaar is;
      nooit `locked_model`/`dictation_priority`; cancel skip rest; journal-payload
      zonder `audio_path` (via fake journal of `to_dict`+redact helper);
      recovery_dir leeg na fout; non-WAV rejected
- [ ] Manual: n.v.t. in deze task

**Completion criteria:**
- FR-04–FR-10, FR-14, FR-16, QR-07 lock/yield

**Handoff:** `/agent-handoff` → `core-python-architect` (consult `audio-speech`)

---

### Task 4: Module, registry, composition-root bind

**Owner:** `core-python-architect`  
**Consult:** —  
**Review:** —  
**Depends on:** Task 3

**Files:**
- Create: `modules/_builtin/file_transcription/__init__.py`, `module.py`
- Create: `app/module_bindings.py`
- Modify: `modules/registry.py`, `dictation.py` (`_reload_modules`)
- Test: `tests/test_modules_registry.py` (uitbreiden)

**In scope:**
- [ ] `FileTranscriptionModule`: id `file-transcription`, `default_enabled() False`,
      `on_event` no-op, `ModuleWithActions` + `ModuleWithShutdown`
- [ ] Na `load_enabled_modules`: duck-type bind van `FileJobHost` (sessie-busy,
      `transcribe_kwargs`, `save_transcript_discrete`, `module_bus.emit`)
- [ ] Shutdown/reload: cancel + join worker vóór nieuwe module-set
- [ ] Geen `Opnamesessie` op `ModuleContext`

**Out of scope:**
- Dialoog-inhoud (stub action mag no-op tot Task 5)

**Implementation notes:**
- `module_bus.shutdown()` bestaat al; module moet eigen thread stoppen in
  `on_app_shutdown`.
- Experimental badge: Task 5 (UI).

**Verification:**
- [ ] Automated: module in `all_builtin_modules()`, default uit, unknown config
      sanitized
- [ ] Manual: n.v.t.

**Completion criteria:**
- FR-01, FR-19 (enabled-key volgt uit registry)

---

### Task 5: Dialoog, tray-actie, locales

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`  
**Review:** `ux-product-design` (copy/states)  
**Depends on:** Task 4

**Files:**
- Create: `modules/_builtin/file_transcription/dialog.py`
- Modify: `modules/_builtin/file_transcription/module.py`
- Modify: `ui/dialogs/modules.py` (`_EXPERIMENTAL_IDS`)
- Modify: `locales/nl.json`, `locales/en.json`, `locales/de.json`
- Test: `tests/test_file_transcription_dialog.py` (Qt offscreen of zwaar gemockt)

**In scope:**
- [ ] `ModuleAction` `in_tray=True`: **Bestanden transcriberen…**
- [ ] Eén non-modal dialoog; tweede open → raise existing
- [ ] Layout volgens UX-spec: intro (vs herstel-audio), bestemming + append-hint,
      lijst, banners, kies/verwijder/start/wachtrij stoppen/sluiten, Naar klembord
- [ ] WAV multi-select `QFileDialog`; non-WAV niet in de lijst
- [ ] States: idle / busy / paused-for-dictation / cancelling; per-file
      wait/running/done/error/cancelled
- [ ] Geen `notify_state`; geen paste; klembord alleen op `done`
- [ ] Esc/Enter zoals spec; sluiten tijdens job = confirm + cancel remaining
- [ ] `_EXPERIMENTAL_IDS` gebruikt **kebab** `file-transcription` en corrigeert
      bestaande `meeting-buddy` / `local-llm` (huidige underscore-ids matchen
      `module.id` niet)

**Out of scope:**
- Help-markdown (Task 6); macOS-specifieke picker-adapter

**Implementation notes:**
- Copy-keys: `modules.file_transcription.*` (UX-spec 2026-08-18).
- Bronnaam in de rij; `.txt`-naam `file_…` bij done.
- Hervatten na dicteren: dialoog niet re-activaten.
- Inbox-side-effect in `description`.

**Verification:**
- [ ] Automated: action registered `in_tray`; experimental badge voor kebab-id;
      start no-op wanneer host busy (gemockt)
- [ ] Manual (Windows, na Task 7): zie AC-matrix

**Completion criteria:**
- FR-02, FR-03, FR-12, FR-13, FR-17, FR-18, QR-03, QR-04

---

### Task 6: Documentatie

**Owner:** `/update-documentation` (uitvoeren via agent die die skill volgt)  
**Consult:** `privacy-security` (formulering inbox/journal)  
**Review:** `product-owner`  
**Depends on:** Task 5 (copy/gedrag stabiel)

**Files:**
- Modify: `docs/modules-integration.md` (`source` inclusief `"file"`; journal
  zonder transcript én zonder `audio_path`; verwijder verouderde claim dat het
  journal transcripttekst bevat)
- Modify: `docs/STATUS.md` (experimentele modules-lijst)
- Modify: `CHANGELOG.md` `[Unreleased]`
- Modify: `docs/user/help.{nl,en,de}.md` — kort: experimenteel, WAV, lokaal,
  bestemming, niet herstel-audio, inbox-spiegel kopieert `.txt`

**In scope:**
- [ ] User-facing en integrator-docs in lijn met Accepted spec + ADR-aanvulling

**Out of scope:**
- Nieuwe screenshots; non-WAV beloftes

**Verification:**
- [ ] Manual: docs ↔ FR-01/FR-11/FR-14/FR-15

**Completion criteria:**
- Required evidence “Help + Modules-copy”

---

### Task 7: Privacy-review + quality-release smoke

**Owner:** `quality-release` (evidence)  
**Consult:** `privacy-security`, `ux-product-design`, `macos-platform` (optioneel smoke)  
**Review:** `product-owner` (acceptatie)  
**Depends on:** Task 5, Task 6

**Files:**
- Geen productiecode tenzij findings terug naar owner

**In scope:**
- [ ] `/privacy-security-review` op de branch-diff (blockers uit pre-review:
      journal, logs, recovery_dir, default-off, geen auto-paste, picker-only)
- [ ] Windows AC-smoke: enable → dialoog → 2 WAV’s → `file_*.txt` in bestemming;
      geen paste; Recente transcripts ongewijzigd; herstel-audio ongewijzigd;
      start tijdens dicteren geweigerd; tussen file 1 en 2 dicteren → pauze
      zonder focus-steal; cancel; journal grep op bronnaam leeg
- [ ] `/code-review` vóór merge

**Out of scope:**
- Graduation uit experimenteel; installer/ffmpeg

**Verification:**
- [ ] Checklist spec Acceptance criteria
- [ ] pytest voor nieuwe tests groen

**Completion criteria:**
- Spec AC’s hebben evidence; product-owner mag accepteren of findings teruggeven

---

## Follow-ups (niet in dit plan)

- Non-WAV spike op frozen `praatMaar.exe` (`audio-speech` + `windows-platform`).
- Harde max duur/RAM-cap als multi-uur WAV’s pijn doen.
- Sidecar-naast-bron als bewuste job-optie.
