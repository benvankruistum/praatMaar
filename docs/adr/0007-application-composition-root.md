# 0007 — Application composition root (`app/`)

- **Status:** Aanvaard (product-owner / plan-implementatie 2026-08-11)
- **Datum:** 2026-08-11
- **Context-term:** composition root (`app`) — zie [CONTEXT.md](../../CONTEXT.md)
  *(term toevoegen bij aanvaarding; draft staat al naast dit voorstel)*
- **Design:**
  [2026-08-11-composition-root-strangler-design.md](../superpowers/specs/2026-08-11-composition-root-strangler-design.md)
- **Plan:**
  [2026-08-11-composition-root-strangler.md](../superpowers/plans/2026-08-11-composition-root-strangler.md)
- **Inventory (freeze):**
  [`.scratch/architecture-rework/inventory.md`](../../.scratch/architecture-rework/inventory.md)
- **Gerelateerd:**
  [0001 — platform-seam](0001-platform-seam.md),
  [0003 — hybrid module system](0003-hybrid-module-system.md),
  [0005 — UI toolkit PySide6](0005-ui-toolkit-pyside6.md),
  [0006 — mic lazy rebind](0006-mic-lazy-rebind.md)

## Context

praatMaar is van PoC naar near-v1 gegroeid met sterke seams (`host`,
`indicator._contract`, `ModuleBus` / `CycleEvent`), maar twee god-objecten:

- `dictation.py` — composition root én hotkeys, tray-wiring, settings-apply,
  recovery-actions, splash/startup (~1500 LOC + module-globals).
- `opnamesessie.py` — mic, incremental/chunk, delivery, timing en recovery in
  één platte klasse (~1300 LOC, tientallen kwargs).

Import-time `Opnamesessie`-constructie, gemengde Meeting Buddy-stop via de
dicteer-pill, en hardcoded launch-paden naar `dictation.py` maken packaging,
testbaarheid en latere UX-Musts onnodig duur. Een clean-slate rewrite zou
gedrag, PyInstaller en experimentele modules tegelijk riskeren.

Gedragsfreeze (product-owner): alle huidige capabilities (core + experimentele
opt-in) blijven; geen feature-dump onder “rework”. Zie inventory.

## Beslissing

**Strangler-rework** met twee nieuwe packages achter stabiele publieke seams:

| Laag | Rol |
|------|-----|
| `dictation.py` | Dunne entry: `main` → `app.run`; tijdelijke re-exports zolang nodig |
| **`app/`** | Composition root: `AppRuntime`, `bootstrap`, `run`, `startup`, `settings_service`, `hotkey_router`, plus clipboard/recent/recovery_actions |
| **`dicteercyclus/`** | `Opnamesessie` façade + interne `mic_stream` / `incremental` / `delivery` / `timing` |
| `host/`, `indicator/`, `modules/`, `ui/` | **Stabiele publieke seams** — geen rename van ModuleBus, CycleEvent of Opnamesessie |

### Harde invarianten

1. **Geen import-time `Opnamesessie`.** Sessie-constructie en side effects horen
   in `run` / bootstrap na splash-intent (single-instance, splash, model-download).
2. **Eén `ModuleBus` → journal-pad** voor alle `CycleEvent`s (inclusief recovery).
3. **`host` / `indicator` / ModuleBus / CycleEvent blijven publiek stabiel** —
   geen schema-break, geen dual-stack (Opnamesessie ≠ AudioCaptureEngine).
4. **WASAPI-pad-rename uitgesteld** (bijv. naar `modules/adapters`) — weinig
   architectuurwinst, hoog packaging-risico; eventueel post-v1 / aparte epic.
5. **Thin `dictation.py`:** geen nieuwe god-root; tijdelijke facades alleen om
   imports en PyInstaller groen te houden tijdens de migratie.

### Parallel in dezelfde epic (geen feature-creep)

- Dictation pill/hotkey stopt **alleen** de dicteercyclus; Meeting Buddy-stop
  via eigen overlay/tray.
- Default geen full-transcript in `praatMaar.log` (journal blijft
  `transcript_chars`-only).
- macOS `host.paste` herstellen achter de seam; entrypoint-resolutie i.p.v.
  hardcoded `dictation.py` in host-launchers (adapters lockstep).

## Alternatieven overwogen

- **Clean-slate (`src/praatmaar` big-bang rename + herschrijf).** Verworpen:
  breekt PyInstaller, import-paden, experimentele modules en characterization
  tegelijk; geen bewijsbaar “gedrag behouden” zonder maanden dual-run.
- **Alleen `opnamesessie.py` opsplitsen, `dictation.py` laten.** Verworpen:
  composition root blijft een god-module; settings/hotkeys/startup blijven
  ontestbaar verweven.
- **WASAPI + modules engines/adapters in dezelfde epic.** Uitgesteld: hangt
  van stabiele imports na slice 4–5 af; dual-stack unificatie is bewust niet
  het doel.
- **Nieuwe namen voor ModuleBus / CycleEvent / Opnamesessie.** Verworpen:
  onnodige churn in modules, journal-schema en CONTEXT-taal.

## Gevolgen

**Positief**

- Composition root heeft een naam en een package; tests kunnen `AppRuntime` /
  `SettingsService` / `HotkeyRouter` injecteren zonder tray/splash.
- `Opnamesessie` blijft de domeinfaçade; interne audio/transcript-delivery
  diept uit zonder platform-leaks.
- Packaging en entrypoint blijven via dunne `dictation.py` + expliciete
  collectie van `app/` / `dicteercyclus/`.
- Ruimte voor dicteercyclus UX Musts op schone seams.

**Negatief / acceptatie**

- Tijdelijke re-exports en dual paths tijdens de strangler (discipline nodig
  om niet terug te groeien in `dictation.py`).
- WASAPI/module-layout blijft “rommelig maar stabiel” tot een latere epic.
- Docs (ADR-0002 vs shipping `indicator._qt`, SECURITY.md) moeten eerlijk
  meelopen — anders blijft drift.

## Verificatie

- Characterization/contract tests **vóór** file moves: journal-redactie,
  `apply_settings` parity, hotkey→session, ModuleBus fail-soft,
  `has_external_streams` / PortAudio skip, live-paste.
- Per slice: gerichte pytest + ruff; na thin-main: splash→ready en
  **PyInstaller lockstep**.
- Windows packaged smoke + upgrade/config survives vóór “gedrag ongewijzigd”
  of “v1.0 ready” te claimen.
- Privacy-review op journal/logs/startup; UX AC-01–06 op Windows na Musts.
- CONTEXT-term `composition root (app)` aanwezig na aanvaarding.
