# Composition-root strangler Implementation Plan

> **For agentic workers:** Use `/agent-handoff` per task (or
> superpowers:subagent-driven-development / executing-plans). Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strangler-rework: extract composition root (`app/`), deepen
`Opnamesessie` under `dicteercyclus/`, thin `dictation.py`, preserve
`host` / indicator / ModuleBus / CycleEvent — zonder productregressie
(behaviour freeze).

**Spec:**
[2026-08-11-composition-root-strangler-design.md](../specs/2026-08-11-composition-root-strangler-design.md)  
**ADR:**
[0007-application-composition-root.md](../../adr/0007-application-composition-root.md)
(status Voorstel → eerst Aanvaard vóór code-slices)  
**Inventory:**
[`.scratch/architecture-rework/inventory.md`](../../../.scratch/architecture-rework/inventory.md)

**Architecture:** `dictation.py` → `app.run` / `AppRuntime` (bootstrap,
settings_service, hotkey_router, startup). `dicteercyclus.Opnamesessie`
façade delegeert aan `mic_stream` / `incremental` / `delivery`. Stabiele seams
ongewijzigd. Geen import-time session. WASAPI-pad-rename deferred.

**Tech stack:** Python 3, pytest, PySide6, bestaande `host` / `SharedWhisper` /
ModuleBus, PyInstaller (Windows).

## Global constraints

- Behaviour freeze: alle inventory-capabilities blijven (core + experimental opt-in).
- Geen feature-creep; geen ModuleBus/CycleEvent schema-break; geen WASAPI rename.
- Geen import-time `Opnamesessie`; side effects (model download, module-start)
  pas in `run` na splash-intent.
- Characterization/contract tests **vóór** file moves (P2): journal-redactie,
  `apply_settings` parity, hotkey→session, ModuleBus fail-soft,
  `has_external_streams` / PortAudio skip, live-paste.
- ADR-0007 moet `Aanvaard` zijn vóór Task 1 code landt (docs-artefacten mogen
  al bestaan als Voorstel/Draft).
- No commits on `main`; branch: `cursor/…` or `feat/…`
- Do not kill/restart the running app unless the user asks
- Claim “gedrag ongewijzigd” / “packaging groen” / “v1.0 ready” alleen met
  packaged Windows evidence (P8 / quality-release).

## File map

| File | Role |
|------|------|
| `dictation.py` | Thin entry + tijdelijke re-exports |
| `app/__init__.py` | Package exports |
| `app/runtime.py` | `AppRuntime` |
| `app/bootstrap.py` | Single-instance, wiring zonder session side effects |
| `app/run.py` / `app/startup.py` | Splash → model → ready |
| `app/settings_service.py` | current / apply / save + ADR-0006 rebind |
| `app/hotkey_router.py` | Toggle/PTT/cancel; geen MB-stop |
| `app/` clipboard/recent/recovery_actions | Extract uit dictation |
| `dicteercyclus/__init__.py` | `Opnamesessie` façade (publieke naam) |
| `dicteercyclus/mic_stream.py` | Warm mic / open / rebind |
| `dicteercyclus/incremental.py` | Chunk/incremental worker |
| `dicteercyclus/delivery.py` | Clipboard / paste / live-paste / destinations gate |
| `opnamesessie.py` | Tijdelijke shim of delete na import-migratie |
| `host/_mac.py`, `host/_win.py`, (linux) | Paste restore + entrypoint helper |
| `praatMaar.spec` / packaging | Collect `app/`, `dicteercyclus/` lockstep |
| `docs/adr/0002-*.md`, `SECURITY.md`, CONTEXT | Honesty / term |
| `tests/test_*` | Characterization + slice suites |

## Task order overview

1. AppRuntime + bootstrap (geen import-time session)
2. SettingsService
3. HotkeyRouter + MB stop ontkoppelen
4. `dicteercyclus/` interne split
5. startup + thin `dictation.main` + PyInstaller
6. Parallel: mac paste / entrypoint + log redactie + docs honesty
7. UX Musts op nieuwe seams + Windows AC smoke

---

### Task 1: AppRuntime + bootstrap

**Owner:** `core-python-architect`  
**Consult:** —  
**Review:** `quality-release` (later)  
**Depends on:** ADR-0007 Aanvaard; P2 characterization tests groen

**Files:**
- Create: `app/__init__.py`, `app/runtime.py`, `app/bootstrap.py`
- Modify: `dictation.py` (delegate wiring; nog niet volledig thin)
- Test: `tests/test_app_bootstrap.py` (nieuw) + bestaande suite groen

**In scope:**
- [ ] `AppRuntime` houdt referenties (host, indicator, bus, session factory)
- [ ] `bootstrap` bouwt wiring **zonder** import-time `Opnamesessie`
- [ ] Session factory / lazy build pas bij eerste gebruik of expliciet in `run`
- [ ] `FakeHost` bootstrap-test

**Out of scope:**
- Settings extract (Task 2), hotkeys (Task 3), interne Opnamesessie-split (Task 4)

**Implementation notes:**
- Preserve `host` injection; geen `sys.platform` in `app/`.
- Tijdelijke re-exports uit `dictation` OK als tests/imports dat eisen.

**Verification:**
- [ ] Automated: `pytest tests/test_app_bootstrap.py -q` + full relevant suite groen
- [ ] Manual (if needed): app start nog via bestaande entry (geen herstart tenzij gevraagd)

**Completion criteria:**
- Geen module-level `session = _build_session()` side effect bij `import dictation` / `import app`
- Maps to ADR-0007 invariant “geen import-time Opnamesessie”

**Handoff:** produce with `/agent-handoff` before execution if running as subagent

---

### Task 2: SettingsService

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`  
**Review:** —  
**Depends on:** Task 1

**Files:**
- Create: `app/settings_service.py`
- Modify: `dictation.py` (call sites), eventueel `config.py` alleen als pure helpers
- Test: bestaande settings/config tests; uitbreiden voor apply/rebind parity

**In scope:**
- [ ] `current` / `apply` / `save` geconcentreerd in `SettingsService`
- [ ] ADR-0006 mic lazy rebind bij apply behouden
- [ ] Geen gedragsregressie op destinations / incremental / speech language keys

**Out of scope:**
- UI redesign van Instellingen; nieuwe settings keys

**Implementation notes:**
- Service krijgt session/runtime hooks via injectie, niet via globals.
- Pill/tray blijven consumenten; geen platform imports.

**Verification:**
- [ ] Automated: settings/config/apply tests + ADR-0006 gerelateerde tests
- [ ] Manual (if needed): Instellingen opslaan → mic preference round-trip

**Completion criteria:**
- `apply_settings` parity met characterization baseline
- Maps to design “SettingsService” + inventory mic lazy rebind

**Handoff:** `/agent-handoff`

---

### Task 3: HotkeyRouter + MB stop ontkoppelen

**Owner:** `core-python-architect`  
**Consult:** `windows-platform`, `ux-product-design`  
**Review:** `ux-product-design`  
**Depends on:** Task 1 (Task 2 mag parallel als geen file-conflict)

**Files:**
- Create: `app/hotkey_router.py`
- Modify: `dictation.py`, eventueel `hotkeys.py`, Meeting Buddy overlay/tray stop-paden
- Test: hotkey/router tests; regressie dat pill ■ MB niet stopt

**In scope:**
- [ ] Toggle / PTT / cancel routing via `HotkeyRouter`
- [ ] Dictation pill/hotkey stopt **alleen** dicteercyclus
- [ ] Meeting Buddy stop uitsluitend via eigen overlay/tray controls
- [ ] Focus-safe gedrag behouden (geen activate)

**Out of scope:**
- Nieuwe hotkeybindings; Linux global-shortcut productisatie

**Implementation notes:**
- windows-platform consult voor native hotkey edge cases; core houdt router platform-neutraal.
- Geen `stop_active_meeting` vanuit dicteer-chrome.

**Verification:**
- [ ] Automated: hotkey → session start/stop tests
- [ ] Manual: Windows focus smoke — dicteer-stop laat MB lopen; MB-stop via MB UI

**Completion criteria:**
- Inventory conflict “Pill/hotkey calls stop_active_meeting” opgelost
- Maps to design parallel fix # UX decoupling

**Handoff:** `/agent-handoff`

---

### Task 4: dicteercyclus interne split

**Owner:** `core-python-architect`  
**Consult:** `audio-speech`  
**Review:** `audio-speech`  
**Depends on:** Task 1; characterization suites voor live-paste/incremental groen

**Files:**
- Create: `dicteercyclus/__init__.py`, `mic_stream.py`, `incremental.py`, `delivery.py` (+ `timing` indien nodig)
- Modify: `opnamesessie.py` → façade of shim die publieke API behoudt
- Test: `tests/test_opnamesessie*`, `tests/test_live_paste*`, incremental/chunk suites

**In scope:**
- [ ] Publieke `Opnamesessie` API/naam behouden
- [ ] Mic open/warm/rebind in `mic_stream`
- [ ] Incremental/chunk worker in `incremental`
- [ ] Clipboard/paste/live-paste/destination gate in `delivery`
- [ ] Geen dual-stack met `AudioCaptureEngine`

**Out of scope:**
- WASAPI path rename; MB capture engine merge; Whisper model lifecycle redesign

**Implementation notes:**
- audio-speech owns semantics van buffers/VAD/chunk; core owns package seams.
- CycleEvent emissie blijft via bestaande `emit_event` / bus injectie.

**Verification:**
- [ ] Automated: `pytest tests/test_opnamesessie.py tests/test_live_paste*.py tests/test_incremental*.py tests/test_chunk_transcription.py -q` (pas paden aan op suite)
- [ ] Manual (if needed): één dicteercyclus + incremental live-paste smoke

**Completion criteria:**
- Imports stabiel; geen gedragsdelta vs characterization
- Maps to ADR-0007 `dicteercyclus/` beslissing

**Handoff:** `/agent-handoff`

---

### Task 5: startup + thin main + PyInstaller

**Owner:** `core-python-architect`  
**Consult:** `privacy-security`, `quality-release`, `windows-platform`  
**Review:** `quality-release`  
**Depends on:** Tasks 1–4

**Files:**
- Create/modify: `app/run.py`, `app/startup.py`, clipboard/recent/recovery_actions extracts
- Modify: `dictation.py` → `main` delegeert naar `app.run`
- Modify: `praatMaar.spec` (of equivalent) — collect `app/`, `dicteercyclus/`
- Test: import/startup smoke tests; packaging checklist

**In scope:**
- [ ] Splash → model download → ready in `startup`/`run`
- [ ] `dictation.main` is dun
- [ ] PyInstaller lockstep met nieuwe packages
- [ ] Module-start pas na splash-intent

**Out of scope:**
- Installer UX rewrite; notarization/signing changes (tenzij packaging breekt)

**Implementation notes:**
- privacy: geen verruiming van log/journal content bij verplaatsen startup.
- windows-platform: spec/datas/hiddenimports lockstep.

**Verification:**
- [ ] Automated: pytest suite relevant aan startup + full unit where feasible
- [ ] Manual: splash→ready; packaged zip/Setup smoke op Windows

**Completion criteria:**
- Thin entry + packaged app start; maps to ADR thin `dictation.py` + design success

**Handoff:** `/agent-handoff`

---

### Task 6: Parallel fixes (mac paste, logs, docs honesty)

**Owner:** `macos-platform` (6a) + `core-python-architect` (6b)  
**Consult:** `privacy-security`, `core-python-architect` (voor 6a)  
**Review:** `privacy-security`  
**Depends on:** kan parallel met Tasks 2–5 zolang `host` launch helper stabiel is; merge na Task 5 bij voorkeur

**Files:**
- Modify: `host/_mac.py` (paste restore), `host/_win.py` / shared entrypoint helper
- Modify: `dicteercyclus/delivery.py` of huidige log-site in Opnamesessie — geen full transcript default
- Modify: `docs/adr/0002-macos-native-overlay-indicator.md`, `SECURITY.md`, eventueel CONTEXT cross-links
- Test: host paste unit/fake waar mogelijk; log-redaction tests

**In scope:**
- [ ] **6a:** `host/_mac.paste` werkt zonder verwijderde `mac_input`; gedeelde entrypoint-resolutie i.p.v. hardcoded `…/dictation.py` (alle adapters lockstep)
- [ ] **6b:** default geen full transcript in `praatMaar.log`; journal blijft `transcript_chars`-only
- [ ] ADR-0002 honesty vs shipping `indicator._qt` (ADR-0005); SECURITY.md sync met ADR-0004 netwerkclaims

**Out of scope:**
- Nieuwe paste-injectie strategieën; cloud logging

**Implementation notes:**
- Platform code alleen onder `host/_mac` / `_win` / `_linux`.
- Privacy gate verplicht vóór “done” op 6b.

**Verification:**
- [ ] Automated: redaction/journal tests; host helper tests
- [ ] Manual: Mac paste smoke waar hardware beschikbaar; Windows log inspect na één cyclus

**Completion criteria:**
- Inventory conflicts mac_input / transcript-log / docs drift geadresseerd
- Maps to design parallel fixes 1–3

**Handoff:** `/agent-handoff` (aparte handoffs voor 6a vs 6b aanbevolen)

---

### Task 7: UX Musts op nieuwe seams + Windows AC smoke

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`  
**Review:** `ux-product-design`, `quality-release`  
**Depends on:** Tasks 1–5 (seams stabiel); Task 3 voor stop-ontkoppeling

**Files:**
- Modify: `app/` + `dicteercyclus/` + `indicator/` / `ui/` naar gelang Musts
- Spec ref: [2026-08-01-dicteercyclus-ux-states-product.md](../specs/2026-08-01-dicteercyclus-ux-states-product.md)
- Test: state/contract tests; Windows handmatige AC-01–06

**In scope:**
- [ ] PREPARING / non-modal errors / busy / ready-cue (Must-restanten) op nieuwe seams
- [ ] Geen regressie focus-safe pill
- [ ] Windows AC smoke tegen UX-spec AC-01–06

**Out of scope:**
- macOS/Linux parity-gate; nieuwe productfeatures buiten Musts

**Implementation notes:**
- ux-product-design levert copy/state; core implementeert.
- Geen terugkeer van god-logica in `dictation.py`.

**Verification:**
- [ ] Automated: indicator/state tests waar mogelijk
- [ ] Manual: Windows AC-01–06 checklist uit UX-spec

**Completion criteria:**
- UX Musts aantoonbaar op strangler-architectuur; handoff naar P8
  (`quality-release` / privacy-review / release-readiness) voor v1.0 evidence

**Handoff:** `/agent-handoff`; daarna `quality-release` + `product-owner` acceptance
