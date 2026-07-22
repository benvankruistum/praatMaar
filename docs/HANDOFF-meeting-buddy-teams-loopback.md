# Handoff — Meeting Buddy: Teams-loopback zichtbaar + hardenen

Geschreven 2026-07-22. Bedoeld om in een **nieuwe sessie** op te pakken.
Werktaal: **Nederlands**.

## Repo-status (op moment van schrijven)

| Item | Status |
|------|--------|
| Branch | `main` — PR #21 gemerged (Spoor B + C1/C2) |
| Spoor B (zichtbaarheid) | **Af** |
| Spoor C1 (device UI prep-dialoog) | **Af** |
| Spoor C2 (loopback reconnect) | **Af** |
| Spoor C3 (mix tunen) | **Deels** — `mic_mix_gain` / `loopback_mix_gain` in yaml |
| Spoor C4 (Teams-acceptatie) | **Open** — zie [teams-loopback-acceptance.md](teams-loopback-acceptance.md) |

---

## Achtergrond (gebruikersdoel)

**Doel:** Meeting Buddy gebruiken tijdens **Microsoft Teams**-calls, zodat:

- **Loopback** = geluid van andere deelnemers / meeting-audio (Windows-uitvoer)
- **Microfoon** = eigen stem
- Beide → STT → hints / meeting state

**Huidige pipeline (al op `main`):**

```text
Teams → Windows output device
         └─ WASAPI loopback ──┐
                               ├─ mix (50/50) → chunks → speech-to-text → Meeting Buddy
Microfoon (config.json) ──────┘
```

Config defaults (`modules/defaults/meeting-buddy.yaml`):

```yaml
enable_loopback: true
loopback_device: null   # null = Windows-default output
```

Meeting Buddy geeft dit door in `MeetingOrchestrator._capture_config()`.

**Fail-soft:** als loopback faalt → alleen microfoon; sessie blijft `ACTIVE` (geen crash).
Gebruiker ziet dat **niet** — dat is het kernprobleem voor Teams.

---

## Wat al werkt (niet opnieuw bouwen)

| Onderdeel | Locatie |
|-----------|---------|
| WASAPI loopback stream | `modules/_builtin/audio_capture.py` → `_try_start_loopback_stream`, `_resolve_loopback` |
| Resample + mix | `modules/_builtin/audio_capture_mix.py` |
| Loopback tests | `tests/test_audio_capture_engine.py` (`test_loopback_*`) |
| Config keys | `modules/_builtin/meeting_buddy/config.py`, yaml defaults |
| Orchestrator wiring | `modules/_builtin/meeting_buddy/orchestrator.py` → `_capture_config()` |
| BT/mic herstel (dicteer) | `opnamesessie.py` — **niet** automatisch voor loopback-stream |

**Nog niet:** loopback-status in UI, device-keuze in UI, observability-event, Teams-acceptatie, docs sync.

---

## Spoor B — Zichtbaarheid + documentatie (kleine PR)

**Doel:** gebruiker en ontwikkelaar zien of meeting-geluid echt wordt opgenomen.

### B1 — Loopback-status uit capture-engine beschikbaar maken

`loopback_enabled` zit nu alleen in interne `_CaptureState`. Voor de UI nodig:

- Optie A (voorkeur, minimaal): uitbreiden `CaptureStatusChanged` met optionele metadata, bijv.
  `sources: ("mic",) | ("mic", "loopback")` of `loopback_active: bool`
- Optie B: apart debug-event `capture_sources_changed` via observability

**Bestanden:**

- `modules/capabilities/continuous_capture.py` — contract uitbreiden (backwards compatible)
- `modules/_builtin/audio_capture.py` — status publiceren bij start, `_disable_loopback`, fail-soft
- `modules/_builtin/meeting_buddy/orchestrator.py` — status doorgeven aan overlay state
- Tests: `tests/test_audio_capture_engine.py`, `tests/test_meeting_buddy_overlay.py`

### B2 — Overlay-teksten

Overlay toont nu generiek “opname actief” (`overlay.py` → `_listening_text`, `_update_recording_banner`).

**Gewenste states (voorbeeld copy, via i18n nl/en/de):**

| Situatie | Gebruiker ziet |
|----------|----------------|
| Mic + loopback actief | “Opname: microfoon + meetinggeluid” |
| Alleen mic (loopback uit of gefaald) | “Opname: alleen microfoon — meetinggeluid niet beschikbaar” |
| Capture error | bestaande fout + hint Instellingen / Herverbinden |

**Bestanden:** `modules/_builtin/meeting_buddy/overlay.py`, `locales/*.json`

### B3 — Logging + observability

- Bij loopback fail-soft: `log.warning` bestaat al; voeg **observability-event** toe, bijv.
  `loopback_unavailable` met reden (zie `modules/_builtin/meeting_buddy/observability.py`)
- Optioneel: één regel in `%APPDATA%\praatMaar\praatMaar.log` bij meeting start met
  `mic_device`, `loopback_device`, `loopback_active`

### B4 — Documentatie sync

| Bestand | Actie |
|---------|--------|
| `docs/STATUS.md` | Loopback op Windows vermelden; “experimenteel” behouden |
| `docs/user/help.nl.md` (+ en/de) | Korte sectie Teams: default output = loopback-bron |
| `modules.audio_capture.description` (locales) | Eventueel “incl. meetinggeluid via loopback op Windows” |

### Acceptatiechecklist Spoor B

- [ ] Meeting start met werkende loopback → overlay toont mic + meetinggeluid
- [ ] Loopback geforceerd falen (test/mock) → overlay toont alleen microfoon + waarschuwing
- [ ] i18n nl/en/de compleet
- [ ] Tests groen (`pytest` relevante subset)
- [ ] `docs/STATUS.md` klopt met code

**Geschatte omvang:** 1 PR, geen UI-dialoog voor device-keuze.

---

## Spoor C — Teams-hardening (grotere slice, na of naast B)

**Doel:** betrouwbaar Teams-gebruik met BT-headset en device-wissels.

### C1 — Loopback-output kiezen (UI)

Nu alleen via:

- `%APPDATA%\praatMaar\meeting-buddy\config.json` (module settings store), of
- `modules/defaults/meeting-buddy.yaml` (defaults)

**Gewenst:**

- Instellingen **of** Meeting Buddy prep-dialoog: dropdown **Uitvoer voor meetinggeluid**
  (Windows output devices, PortAudio-index)
- `null` = Windows-standaard (huidig gedrag)
- Opslaan in `meeting-buddy` module config

**Aanknopingspunten:**

- `settings.py` / apart subdialoog — precedent: microfoon-dropdown (`_input_devices`)
- `sounddevice.query_devices()` — filter op output / loopback-capable (WASAPI)
- `MeetingBuddyConfig.loopback_device`

### C2 — Loopback reconnect (BT / device hotplug)

Dicteer-pad (`opnamesessie.py`) heeft zombie-detectie + `refresh_portaudio`.
Loopback-stream heeft `finished_callback` → `_disable_loopback` maar **geen** auto-reconnect.

**Gewenst:**

- Bij `_loopback_stream_finished` / `_disable_loopback` tijdens actieve meeting:
  - status `RECONNECTING` (bestaat al in contract)
  - retry met backoff (max N pogingen)
  - overlay-knop “Herverbinden” blijft werken (`orchestrator.reconnect_capture`)
- Overweeg `refresh_portaudio` vóór loopback-reopen (alleen als geen streams open)

### C3 — Betere mix (optioneel, kan later)

Huidig: `mix_mono_chunks` = 50/50 clip.

Teams-risico’s:

- Echo via mic + loopback
- Te stille meeting-deelnemers t.o.v. eigen stem

**Later (RFC):** aparte kanalen naar STT, gain per bron, of alleen loopback voor “anderen”
als mic al apart wordt verwerkt. **Niet blokkerend** voor eerste Teams-acceptatie.

### C4 — Handmatige acceptatiechecklist Teams

Uit te voeren op Windows met echte Teams-call (niet geautomatiseerd in CI):

| # | Scenario | Verwacht |
|---|----------|----------|
| 1 | Headset = default output + input, meeting start | Hints over wat **anderen** zeggen (niet alleen eigen stem) |
| 2 | Alleen mic (loopback uit in config) | Alleen eigen uitingen in hints |
| 3 | Loopback faalt (bijv. geen WasapiSettings) | Overlay waarschuwing; app crasht niet |
| 4 | Headset afzetten mid-meeting | Fout of reconnect; “Herverbinden” herstelt |
| 5 | Teams output ≠ Windows default | Documenteer beperking of kies device in C1 |
| 6 | Parallel dicteren tijdens meeting | Dicteer wint; STT `DELAYED`; geen crash |

Resultaat vastleggen in `.scratch/meeting-buddy-teams-loopback/acceptance.md` of PR-beschrijving.

### Acceptatiechecklist Spoor C (technisch)

- [ ] UI: loopback output device kiezen en persistent
- [ ] Reconnect-pad voor loopback gedocumenteerd + getest (unit met fakes)
- [ ] Teams-checklist doorlopen op fysieke machine
- [ ] CHANGELOG `[Unreleased]` bij user-visible wijzigingen

**Geschatte omvang:** 1–2 PR’s (C1+C2 los van C3).

---

## Technische referenties

| Document / code | Inhoud |
|-----------------|--------|
| `docs/RFC-AudioCapture-01.md` | Architectuur mic + loopback + mixer |
| `docs/superpowers/specs/2026-07-19-meeting-buddy-mvp-design.md` | MVP-scope; loopback expliciet “later” bij ontwerp, nu deels ingehaald |
| `modules/_builtin/audio_capture.py` | Implementatie |
| `modules/defaults/meeting-buddy.yaml` | `enable_loopback`, `loopback_device` |
| `tests/test_audio_capture_engine.py` | Loopback unit tests |
| `CONTRIBUTING.md` | CI, ruff, pytest |

**Sounddevice-vereiste:** `WasapiSettings(loopback=True)` — zonder WASAPI-build faalt loopback altijd fail-soft.

**Teams-tip voor gebruikers (help-tekst):**

1. Zet Windows-geluid **uitvoer** op het apparaat waar Teams doorheen speelt.
2. Zet Teams **speaker** op hetzelfde apparaat.
3. Gebruik een **headset** om echo te beperken (mic hoort niet de luidsprekers).

---

## Voorgestelde volgorde

```text
1. Spoor B (zichtbaarheid)     → merge
2. Handmatige Teams-test (C4)  → bevestigt waarde / gaps
3. Spoor C1 (device UI)        → merge
4. Spoor C2 (reconnect)        → merge
5. C3 mix                      → alleen bij bewezen echo-probleem
```

---

## Buiten scope (nu niet doen)

- macOS loopback / CoreAudio
- System-audio op Linux
- Transcriptviewer of export
- `ai.semantic_analysis` provider
- Opname van Teams-interne “recording” API (alleen OS-loopback)

---

## Suggestie issue-tracker (optioneel)

Lokaal aanmaken onder `.scratch/meeting-buddy-teams-loopback/`:

- `issues/01-loopback-status-overlay.md` (Spoor B)
- `issues/02-docs-status-help.md` (Spoor B)
- `issues/03-loopback-device-ui.md` (Spoor C1)
- `issues/04-loopback-reconnect.md` (Spoor C2)
- `issues/05-teams-acceptance.md` (Spoor C4)

---

## Open vragen voor de opvolgende sessie

1. Loopback-device UI in **Instellingen** vs **agenda-prep** — waar verwacht de gebruiker dit?
2. Moet `enable_loopback: false` een zichtbare “alleen microfoon”-modus zijn in de overlay?
3. Is 50/50-mix acceptabel na eerste Teams-test, of direct C3 prioriteren?

---

*Einde handoff.*
