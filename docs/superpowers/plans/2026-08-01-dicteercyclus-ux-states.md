# Dicteercyclus UX states — Implementation Plan

> **For agentic workers:** Use `/agent-handoff` per task (or
> superpowers:subagent-driven-development / executing-plans). Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Accepted dicteercyclus UX Musts: focus-safe mic errors,
no false “Opname” before mic ready, visible busy while processing, ERROR
next-step sublines, and a transient ready-cue after splash — without stealing
focus from the dictation target.

**Spec:** [2026-08-01-dicteercyclus-ux-states-product.md](../specs/2026-08-01-dicteercyclus-ux-states-product.md) (Accepted)  
**ADR:** n/a (extends existing `RecordingState` / pill contract)  
**Architecture:** Keep `indicator._contract` as the sole dicteercyclus state
seam; `Opnamesessie` owns notify order; `dictation` owns user-error presentation
and splash→ready cue; `indicator._qt` paints states/sublines with existing
no-activate flags. No Meeting Buddy overlay changes.

**Tech stack:** Python 3, PySide6 pill, pytest, existing `i18n` locales.

## Global constraints

- Feature branch only; no commits on `main` (suggested: `cursor/dicteercyclus-ux-states-impl`).
- Do not kill/restart the running app unless the user asks.
- Windows is primary acceptance platform (v1.0 scope).
- Prefer copy/focus fixes over new settings toggles.
- Dutch locale keys first; sync en/de in the same task as nl.
- ERROR checklist dialog only after **explicit** user action (not on hotkey failure).
- **Preparing approach (plan decision):** add `RecordingState.PREPARING` +
  `state.preparing` copy (clearer than silent delay). Avoid waveform “as if
  recording” while PREPARING.
- **ERROR click-through:** copy-hint only in this plan (no Settings navigation
  from pill hit-target) — open question deferred.

## File map

| File | Rol |
|------|-----|
| `indicator/_contract.py` | `PREPARING`; optional status-detail/hint channel; queue shape |
| `indicator/__init__.py` | Re-exports |
| `indicator/_qt.py` | Paint PREPARING; ERROR/busy sublines; ready-cue show/hide |
| `opnamesessie.py` | Notify PREPARING → RECORDING after `_ensure_stream`; ERROR hints |
| `dictation.py` | Non-modal `_report_user_error`; busy tray/pill; splash ready-cue |
| `ui/dialogs/message.py` | Keep for explicit dialogs; stop using from auto mic-fail path |
| `ui/tray.py` | Busy/attention tooltips if needed |
| `locales/{nl,en,de}.json` | `state.preparing`, error hint keys, ready-cue copy |
| `docs/user/help.{nl,en,de}.md` | Short note on mic errors / ready cue if user-visible |
| `tests/test_indicator_contract.py` | Enum + notify + hint API |
| `tests/test_opnamesessie.py` | Notify order; no RECORDING before stream success |
| `tests/test_*` (new or extend) | Non-modal error path; ready-cue trigger |
| `CHANGELOG.md` / `docs/STATUS.md` | Unreleased + roadmap tick |

## Task order overview

1. Contract: `PREPARING` + status hint API (TDD)
2. Pill paint for PREPARING + ERROR/busy sublines
3. `Opnamesessie` notify order + error classification hooks
4. Non-modal mic/user error in `dictation`
5. Busy-while-processing visibility (hotkey + tray)
6. Transient ready-cue after splash (FR-UX-05 B)
7. Locales + Help + CHANGELOG
8. Windows smoke / AC matrix (`quality-release`)

---

### Task 1: RecordingState.PREPARING + status hint channel

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`  
**Review:** `quality-release` (later)  
**Depends on:** none

**Files:**
- Modify: `indicator/_contract.py`, `indicator/__init__.py`
- Modify: `tests/test_indicator_contract.py`

**In scope:**
- [ ] Add `RecordingState.PREPARING`
- [ ] Extend notify/drain API so ERROR (and optionally PREPARING) can carry a
      short **hint/detail** string or hint-key resolved by UI via `i18n`
      (prefer passing already-translated text from call sites to avoid
      indicator importing error taxonomy)
- [ ] Clear hint when leaving ERROR/PREPARING (or on IDLE)
- [ ] Update contract tests for enum membership and queue behaviour

**Out of scope:**
- Qt painting (Task 2)
- Opnamesessie wiring (Task 3)

**Implementation notes:**
- Today: `_status_queue: Queue[tuple[RecordingState, str]]` (state, mode).
  Prefer additive: e.g. optional third element or parallel `set_status_hint` /
  include hint in a small dataclass — keep thread-safety.
- Meeting Buddy may call `notify_state(RECORDING|ERROR|IDLE, "meeting")` —
  must remain compatible (hint optional/default empty).

**Verification:**
- [ ] Automated: `pytest tests/test_indicator_contract.py -q`

**Completion criteria:**
- PREPARING exists; tests green; backward-compatible notify for existing callers
- Enables FR-UX-02 / FR-UX-04 plumbing

**Handoff:** `/agent-handoff` → `core-python-architect`

---

### Task 2: Pill UI — PREPARING, ERROR subline, busy subline hooks

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`, `windows-platform` (no-activate)  
**Depends on:** Task 1

**Files:**
- Modify: `indicator/_qt.py`
- Test: extend `tests/test_indicator_contract.py` and/or lightweight Qt tests if
  present; otherwise paint helpers + manual checklist in Task 8

**In scope:**
- [ ] PREPARING: visible pill, distinct from RECORDING (no recording waveform
      as if capturing — muted/neutral pulse OK); label `state.preparing`
- [ ] ERROR: keep “Mislukt”; draw **subline** from status hint when set
- [ ] TRANSCRIBING: ensure busy remains visible; optional `state.busy_hint` if
      needed when hotkey re-entry fires (may be tray-only in Task 5)
- [ ] Preserve `apply_hud_window_flags` / no-activate behaviour

**Out of scope:**
- Opening Settings from pill click

**Verification:**
- [ ] Automated: whatever unit coverage exists for indicator drain→apply
- [ ] Manual note for Task 8: PREPARING ≠ Opname look

**Completion criteria:**
- Maps to FR-UX-02 (visual), FR-UX-04 (subline), AC-04, AC-06 (no focus regress)

---

### Task 3: Opnamesessie notify order (PREPARING → RECORDING)

**Owner:** `core-python-architect`  
**Consult:** `audio-speech`  
**Depends on:** Task 1

**Files:**
- Modify: `opnamesessie.py` (`start` path ~notify before `_ensure_stream`)
- Modify: `tests/test_opnamesessie.py`

**In scope:**
- [ ] On start: `notify(PREPARING)` (or equivalent) **before** stream open
- [ ] `notify(RECORDING)` only **after** successful `_ensure_stream()`
- [ ] On stream failure: `notify(ERROR)` + set mic-oriented hint text; call
      `on_user_error` with message for tray/log — modal left to Task 4
- [ ] Do not leave UI claiming RECORDING if start rolls back

**Out of scope:**
- Changing warm-mic semantics beyond notify timing
- Meeting Buddy start path (unless it shares the same false-RECORDING pattern —
  if shared helper, keep MB behaviour stable)

**Implementation notes:**
- Current code explicitly comments “UI meteen rood” before `_ensure_stream` —
  remove that assumption; update comments/tests that assert last state is
  RECORDING immediately after `start()` without mocking stream success.
- Tests that mock successful stream should still end in RECORDING.

**Verification:**
- [ ] Automated: `pytest tests/test_opnamesessie.py -q` (update expectations)
- [ ] New/adjusted test: failed `_ensure_stream` never leaves durable RECORDING

**Completion criteria:**
- FR-UX-02 / AC-02

---

### Task 4: Non-modal user error path

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`, `privacy-security` (copy only)  
**Depends on:** Task 1–2 (hint display)

**Files:**
- Modify: `dictation.py` (`_report_user_error`)
- Optionally: `ui/dialogs/message.py` (document: auto-fail must not use `error()`)
- Test: new unit test with fake indicator / spy that `error()` is **not** called
  on auto mic-fail; attention + hint set instead

**In scope:**
- [ ] `_report_user_error`: set tray mic attention; set ERROR status hint;
      **do not** `QMessageBox.critical` automatically
- [ ] Ensure full checklist text remains available via Instellingen / existing
      mic help paths (or tray action if one already exists — do not invent a
      new settings page)
- [ ] Logging/print of the detailed message stays OK

**Out of scope:**
- Redesigning Instellingen Herstel-audio
- Changing destinations/settings modals (those remain intentional)

**Verification:**
- [ ] Automated: test that auto error path does not invoke modal helper
- [ ] Manual (Task 8): Notepad keeps focus on denied/missing mic

**Completion criteria:**
- FR-UX-01 / AC-01

---

### Task 5: Busy-while-processing visibility

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`  
**Depends on:** Task 2 (optional), Task 3

**Files:**
- Modify: `opnamesessie.py` and/or `dictation.py` hotkey path when
  `is_processing`
- Modify: `ui/tray.py` tooltips if needed
- Test: assert processing path updates tray and/or keeps TRANSCRIBING visible

**In scope:**
- [ ] While `_processing` / TRANSCRIBING until IDLE: pill must not look idle
- [ ] Hotkey during busy: visible feedback (tray tooltip and/or reinforce
      TRANSCRIBING / `state.busy_hint`) — not console-only
- [ ] No new recording start while processing (existing guard stays)

**Out of scope:**
- Cancel-during-transcription
- Separate `INSERTING` state

**Verification:**
- [ ] Automated: unit test for busy feedback hook if extractable
- [ ] Manual Task 8: long transcript + mash hotkey → still busy UI

**Completion criteria:**
- FR-UX-03 / AC-03

---

### Task 6: Transient ready-cue after splash (FR-UX-05 B)

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`  
**Depends on:** Task 2 (pill can show idle/ready without bestemming temporarily)

**Files:**
- Modify: `dictation.py` (post-model-load / post-splash)
- Modify: `indicator/_qt.py` if needed for timed show without sticky destination
- Test: unit test that ready-cue schedules ≤5 s hide and does not steal focus flags

**In scope:**
- [ ] After splash/model ready: show non-activating pill (or dedicated ready
      presentation) with `state.ready` + hotkey label for ~3–5 s
- [ ] Then hide unless sticky bestemming requires idle pill
- [ ] Once per process start (not every settings save)

**Out of scope:**
- Permanent always-visible idle HUD (option C rejected)
- Balloon/OS toast that activates the app

**Verification:**
- [ ] Automated: timer/hide behaviour with fake clock if practical
- [ ] Manual Task 8: first launch after splash → brief ready cue, Notepad focus OK

**Completion criteria:**
- FR-UX-05 B / AC-05

---

### Task 7: Locales, Help, CHANGELOG

**Owner:** `/update-documentation` (or `core-python-architect` with docs skill)  
**Consult:** `ux-product-design`  
**Depends on:** Tasks 1–6 copy keys known

**Files:**
- Modify: `locales/nl.json`, `en.json`, `de.json`
- Modify: `docs/user/help.nl.md` (+ en/de) — brief mic-error / ready behaviour
- Modify: `CHANGELOG.md` `[Unreleased]`
- Modify: `docs/STATUS.md` roadmap tick when impl lands

**In scope:**
- [ ] Keys from spec: `state.preparing`, `state.error_mic_hint`,
      `state.error_recovery_hint`, `state.error_retry_hint`, optional
      `state.busy_hint`
- [ ] Help: one short paragraph under Aan de slag / risks — errors via pill/tray,
      checklist in Instellingen; ready cue mentioned lightly
- [ ] Keep three languages in sync

**Verification:**
- [ ] Grep keys used in code exist in all three locale files

**Completion criteria:**
- Docs surfaces match behaviour; CHANGELOG lists user-visible UX fixes

---

### Task 8: Acceptance verification (AC matrix)

**Owner:** `quality-release`  
**Consult:** `windows-platform`, `product-owner`  
**Depends on:** Tasks 1–7

**Files:**
- Evidence only (PR description / checklist); no product code

**In scope:**
- [ ] Run `pytest -q` (or focused suites from tasks)
- [ ] Manual Windows smoke vs AC-01–06:
  - AC-01 mic denied/missing — focus stays in Notepad; pill/tray actionable
  - AC-02 no stable Opname+waveform before ready; fail path clear
  - AC-03 busy hotkey during long transcribe
  - AC-04 ERROR subline present
  - AC-05 ready cue ≤5 s after splash
  - AC-06 pill click does not activate praatMaar over target
- [ ] Report: Verified / Verified with follow-up / Failed

**Out of scope:**
- macOS Gatekeeper / signing
- Meeting Buddy loopback acceptance

**Completion criteria:**
- All Must ACs evidenced or explicitly waived with product-owner note

---

## AC ↔ task traceability

| AC / FR | Tasks |
|---------|-------|
| FR-UX-01 / AC-01 | 4, 8 |
| FR-UX-02 / AC-02 | 1, 2, 3, 8 |
| FR-UX-03 / AC-03 | 5, 8 |
| FR-UX-04 / AC-04 | 1, 2, 4, 7, 8 |
| FR-UX-05 / AC-05 | 6, 7, 8 |
| AC-06 | 2, 8 |

## Deferred (explicit)

- ERROR-pill click → Instellingen
- `INSERTING` first-class state
- `PAUSED` for dicteercyclus
- Meeting Buddy overlay state pass
- Authenticode / macOS signed distribute

## After plan approval

1. Human approves this plan (chat OK).
2. `/agent-handoff` Task 1 → `core-python-architect` (or execute Task 1 in-session).
3. Check off boxes as tasks complete.
4. Task 8 → product-owner acceptance of shipped behaviour.
