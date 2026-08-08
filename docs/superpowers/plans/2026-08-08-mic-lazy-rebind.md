# Mic lazy rebind Implementation Plan

> **For agentic workers:** Use `/agent-handoff` per task (or
> superpowers:subagent-driven-development / executing-plans). Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sticky warme mic op Windows herbinden bij dicteercyclus-start /
mic-save, alleen als device-identiteit wijzigde — zonder OS device-watcher.
**Spec:** [2026-08-03-mic-lazy-rebind-product.md](../specs/2026-08-03-mic-lazy-rebind-product.md)
**ADR:** [0006 — Microfoon lazy rebind](../../adr/0006-mic-lazy-rebind.md)
**Architecture:** Identity `(name, hostapi)` in `mic_errors`; `Opnamesessie`
bewaart bound identity, peilt vóór warm-reuse zonder `refresh_portaudio`,
heropent alleen bij mismatch.
**Tech stack:** Python 3, sounddevice/PortAudio, pytest

## Global constraints

- Geen OS-watcher / geen nieuwe `host`-API
- Geen commits op `main`; branch: `feat/mic-lazy-rebind`
- Geen app kill/restart tenzij de gebruiker dat vraagt
- `refresh_portaudio` overslaan bij externe streams (Meeting Buddy)

## File map

| File | Role |
|------|------|
| `mic_errors.py` | `device_identity(sd, index \| None)` |
| `opnamesessie.py` | Bound identity, compare in `_ensure_stream`, clear on stop |
| `dictation.py` | Bestaand `apply_settings` mic-change → `refresh_input_device` |
| `tests/test_mic_errors.py` | Identity helper |
| `tests/test_opnamesessie.py` | Reuse / reopen / pinned-gone |
| `docs/user/help.{nl,en,de}.md` | Korte herbind-note |
| `CHANGELOG.md` / `docs/STATUS.md` | Unreleased + status |

## Task order overview

1. Docs accept (ADR/spec) — dit bestand
2. Pure identity helper (TDD)
3. Opnamesessie lazy rebind (TDD)
4. Settings-pad verify
5. User docs / CHANGELOG / STATUS
6. pytest + Windows smoke note

---

### Task 1: Pure identity helper

**Owner:** `core-python-architect`
**Consult:** `audio-speech`, `windows-platform`
**Depends on:** none

**Files:**
- Modify: `mic_errors.py`
- Test: `tests/test_mic_errors.py`

**In scope:**
- [ ] `device_identity(sd, device: int | None) -> tuple[str, int] | None`
- [ ] `None` → `query_devices(kind="input")`; int → `query_devices(device)`
- [ ] Fout / lege naam → `None`

**Verification:**
- [ ] `pytest tests/test_mic_errors.py`

**Completion criteria:** Maps to identity decision in ADR 0006 / FR-02.

---

### Task 2: Opnamesessie lazy rebind

**Owner:** `core-python-architect`
**Consult:** `audio-speech`, `windows-platform`
**Depends on:** Task 1

**Files:**
- Modify: `opnamesessie.py`
- Test: `tests/test_opnamesessie.py`

**In scope:**
- [ ] `_bound_device_identity`; store on open; clear on `stop_audio_stream`
- [ ] Peek desired identity without terminate when warm stream alive
- [ ] Same identity → reuse; mismatch/unknown → close → refresh_if_safe → open
- [ ] Tests: unchanged / changed / pinned-gone / external streams

**Verification:**
- [ ] `pytest tests/test_opnamesessie.py tests/test_opnamesessie_stream.py`

**Completion criteria:** FR-01..05, AC 1–5 (unit), QR-03.

---

### Task 3: Settings path verify

**Owner:** `core-python-architect`
**Depends on:** Task 2

**Files:**
- Review: `dictation.py` `apply_settings`

**In scope:**
- [ ] Mic-wijziging → `refresh_input_device()` → bound cleared → volgende start heropent
- [ ] Geen UI-re-enumeratie bij dropdown-open (out of scope)

---

### Task 4: Docs surfaces

**Owner:** `core-python-architect` (+ `/update-documentation` surfaces)
**Depends on:** Task 2

**Files:**
- Modify: `docs/user/help.{nl,en,de}.md`, `CHANGELOG.md`, `docs/STATUS.md`

**In scope:**
- [ ] Herbindt bij start/opslaan; geen idle auto-switch

---

### Task 5: Verify

**Owner:** `core-python-architect` / `quality-release`
**Depends on:** Tasks 1–4

**Verification:**
- [ ] `pytest tests/test_mic_errors.py tests/test_opnamesessie.py tests/test_opnamesessie_stream.py`
- [ ] Manual Windows smoke note: warm → BT connect → Shift+Esc

## Out of scope

- OS device-watcher / `IMMNotificationClient`
- Meeting Buddy mid-meeting reconnect
- Altijd heropenen bij elke start
- Linux parity / macOS warm path
