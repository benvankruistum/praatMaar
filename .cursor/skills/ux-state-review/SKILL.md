---
name: ux-state-review
description: Review and specify praatMaar interaction states including idle, preparing, recording, paused, transcribing, inserting, cancelled, denied, unavailable, failed, and recovered, with focus, keyboard, accessibility, and platform behaviour.
---

# UX state review (praatMaar)

Review or specify **interaction states** for dictation, Meeting Buddy, and
related UI so the user always knows what the app is doing — without stealing
focus from the dictation target.

This skill produces UX state specs and review findings. It does **not**
implement indicator or UI code (`core-python-architect` / platform agents).

Prefer the `ux-product-design` subagent for large design work; this skill is the
checklist and deliverable format for state-focused passes.

## When to use

- New or changed dicteercyclus / Meeting Buddy / overlay / tray behaviour
- Ambiguous “is it recording?” reports
- Focus, keyboard, or accessibility issues around the pill or dialogs
- Before implementing new `RecordingState` values or parallel status surfaces
- `/feature-specification` or `/code-review` when interaction states are in scope

## Canonical vocabulary

Product-facing states to consider (not all are first-class in code today):

| State | Intent |
|-------|--------|
| `idle` | Not capturing; ready |
| `preparing` | Warm-up / model / device open — not yet recording audio for the user act |
| `recording` | Microphone (and/or loopback) actively capturing |
| `paused` | Capture intentionally suspended; resumable |
| `transcribing` | Audio→text in progress |
| `inserting` | Clipboard/paste or other insertion in progress |
| `cancelled` | User aborted; returning to idle |
| `denied` | Permission denied (mic, Accessibility, …) |
| `unavailable` | Device/model/backend missing or busy |
| `failed` / `error` | Failure the user must understand |
| `recovered` | Recovery path offered or completed after failure/interrupt |

**Implemented dicteercyclus enum today** (`indicator._contract.RecordingState`):
`IDLE`, `RECORDING`, `TRANSCRIBING`, `CANCELLED`, `ERROR`.

When reviewing:

- Map product states → existing enum / tray / overlay / Meeting Buddy UI
- Mark **gap** if a product state is needed but not represented
- Do not invent code changes here; recommend FR/AC or `/implementation-plan`

Use exact domain terms from `CONTEXT.md` (`dicteercyclus`, `Opnamesessie`,
`indicator` / pill, `host`).

## Principles

- Recording vs idle must never be ambiguous
- Passive indicators must not activate the app or steal focus
- Hotkey workflow stays fast and reversible (cancel)
- Errors and denials need an actionable next step
- Dutch UI copy unless product decision says otherwise
- Non-colour differentiation for state; no essential info via animation only
- Windows and macOS may differ in chrome; state *meaning* stays consistent

## Process

### 1. Orient

- `/repository-orientation` on indicator / opnamesessie / Meeting Buddy overlay
- Read `RecordingState`, `notify_state`, pill Qt/native adapters, locales
  `state.*` keys, help snippets
- Diff range if reviewing a change (merge-base vs `HEAD`)

### 2. Inventory current surfaces

List where state is shown or implied:

- Status pill / indicator
- Tray or menu-bar
- Meeting Buddy overlay
- Settings / permission dialogs
- System permission prompts
- Logs (not a UX surface — flag if users must read logs to understand state)

### 3. Build or review the state model

For **each** in-scope state (table above + feature-specific), fill:

| Field | Content |
|-------|---------|
| Trigger | What enters the state |
| Visible indicator | Pill colour/icon/LEDs, overlay, tray |
| Text / icon | Locale keys and wording |
| Audio behaviour | Capturing? muted? loopback? |
| Permitted actions | Hotkey, cancel, open settings, … |
| Focus behaviour | Must not activate / may show dialog |
| Keyboard | Shortcuts still work? |
| Accessibility | Name/announcement; not colour-only |
| Transitions | To which states, on what event |
| Timeout | Auto-return to idle? |
| Error fallback | If underlying op fails |
| Platform notes | Win vs Mac differences |

### 4. Transition diagram

Document legal transitions (text or mermaid). Flag illegal or missing edges
(e.g. recording → idle with no cancelled/error).

### 5. Focus and platform pass

- Pill / overlay: no-activate / nonactivating panel preserved?
- Settings opened from tray: expected activation?
- Paste/`inserting`: focus remains on target app?
- Permission `denied`: guidance before OS settings when possible

### 6. Accessibility pass

- Keyboard-reachable controls where interaction is required
- Passive indicators: no forced focus move
- Contrast / scaling / high-contrast considerations
- Screen-reader-oriented names if applicable

### 7. Decision

| Mode | Outcomes |
|------|----------|
| **Specify** | UX state spec ready for implementation |
| **Review** | Approved / Approved with follow-up / Changes required / Insufficient evidence |

## Output templates

### State specification

```markdown
# UX state specification — [feature or surface]

## User and context
## Surfaces in scope
## State model
### idle
(trigger, indicator, text, actions, focus, audio, transitions, …)
### preparing
…
(include every in-scope state)

## Transition map
## Focus rules
## Keyboard behaviour
## Accessibility
## Platform differences (Windows / macOS)
## Locale / copy keys
## Gaps vs RecordingState / implementation
## Acceptance criteria
## Review evidence required
## Open questions
```

### Review report

```markdown
# UX state review — [change]

## Decision
## Range / surfaces
## Ambiguous states found
## Focus risks
## Keyboard / accessibility gaps
## Platform inconsistencies
## Missing product states (gaps)
## Findings (blocker / should-fix / nit)
## Recommended next step
`/feature-specification` | `/agent-handoff` → ux/core | `/implementation-plan`
```

## Relationship to code

| Concern | Owner after this skill |
|---------|-------------------------|
| State meaning & copy | `ux-product-design` (this skill) |
| `RecordingState` / contracts | `core-python-architect` |
| Pill Win/Mac adapters | `windows-platform` / `macos-platform` |
| Locales help sync | `/update-documentation` |

Do not expand `RecordingState` in a review finding without product justification —
prefer an explicit gap + AC.

## Behavioural boundaries

- Do not implement UI under this skill
- Do not approve mockups as proof of runtime focus behaviour
- Do not require pixel-identical Win/Mac chrome
- Do not hide privacy-relevant capture behind vague “busy” states
- Do not treat log lines as adequate user-facing state

## Done when

- In-scope states are specified or reviewed
- Focus, keyboard, accessibility, and platform notes are present
- Gaps vs implementation are explicit
- Decision / next step is clear
