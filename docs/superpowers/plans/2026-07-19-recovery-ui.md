# Recovery-UI Implementation Plan

> Spec: `docs/superpowers/specs/2026-07-19-recovery-ui-design.md`

**Goal:** Sectie Herstel-audio in Instellingen: lijst/wissen/map + opnieuw transcriberen + vraag na succes.

**Architecture:** `recovery.py` filesystem helpers; `dictation.retranscribe_recovery_wav` gebruikt geladen model; settings krijgt optionele hooks. Op macOS (settings-subprocess): opnieuw-transcriberen via resultaat-key `_recovery_retranscribe` → parent voert uit.

---

### Task 1: recovery list/delete (TDD)
### Task 2: retranscribe in dictation + busy guard  
### Task 3: settings UI sectie + i18n + macOS result hook
### Task 4: CHANGELOG/STATUS/CONTEXT + pytest
