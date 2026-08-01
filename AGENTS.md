# Agents — praatMaar

Cursor subagent definitions live in **`.cursor/agents/`** (canonical). Shared
behaviour: [`docs/agents/shared-rules.md`](docs/agents/shared-rules.md). Domain
language: [`CONTEXT.md`](CONTEXT.md).

## Default feature flow

1. `/repository-orientation` — ground in architecture, terms, ADRs, code, tests
2. `/change-impact-analysis` — when cross-cutting or ownership/affected areas are unclear
3. `/architecture-decision` — when the choice is significant, hard to reverse, security- or platform-defining
4. `/feature-specification` (and/or `product-owner`) — problem, scope, acceptance criteria, ownership
5. `/implementation-plan` — ordered slices with files, owners, tests, completion criteria
6. `/agent-handoff` — self-contained assignment(s) for specialist subagents
7. `ux-product-design` / `/ux-state-review` / `/privacy-security-review` — when interaction or data risk is in scope
8. Implementation agent(s) — see matrix below
9. `/code-review` — before merge of non-trivial code
10. `/privacy-security-review` — when the diff touches audio, transcripts, network, permissions, packaging, or deps
11. `/release-readiness` — go/no-go before tag
12. `quality-release` — verify evidence against acceptance criteria
13. `product-owner` — acceptance decision

## Specialist agents

| Agent | Role | Writes code? |
|-------|------|--------------|
| `product-owner` | Requirements, prioritisation, acceptance | No (`readonly`) |
| `ux-product-design` | Flows, states, copy, UX specs | No (`readonly`) |
| `privacy-security` | Threat model, privacy review | No (`readonly`) |
| `quality-release` | Verification, release readiness | No (`readonly`) |
| `linux-platform` | Linux discovery / ADR / PoC advice | No (`readonly`) |
| `core-python-architect` | Platform-independent Python & seams | Yes |
| `audio-speech` | Audio→text pipeline & speech quality | Yes |
| `windows-platform` | Native Windows adapters & packaging | Yes |
| `macos-platform` | Native macOS adapters & packaging | Yes |

Invoke with `/agent-name` or by naming the agent in chat.

## Ownership matrix

| Area | Owner | Consult |
|------|-------|---------|
| `Opnamesessie`, dicteercyclus, `dictation.py` wiring | `core-python-architect` | `audio-speech`, platform |
| Generic `host` / `indicator` contracts | `core-python-architect` | platform |
| `host/_win.py`, `indicator/_win.py`, Win32 hotkeys, tray | `windows-platform` | `core-python-architect`, `ux-product-design` |
| `host/_mac.py`, `indicator/_mac.py`, TCC, notarization | `macos-platform` | `core-python-architect`, `ux-product-design` |
| Linux feasibility / support matrix | `linux-platform` | `product-owner`, `core-python-architect` |
| Faster-Whisper, VAD, buffers, incremental transcription, quality | `audio-speech` (+ `/whisper-evaluation`) | `core-python-architect`, `privacy-security` |
| WASAPI device/loopback **adapters** (`wasapi_loopback.py`, Win capture) | `windows-platform` | `audio-speech` |
| Audio **pipeline semantics** consuming loopback/mic streams | `audio-speech` | `windows-platform` / `macos-platform` |
| Meeting Buddy **orchestration** (`modules/_builtin/meeting_buddy/`, module wiring) | `core-python-architect` | `audio-speech`, `ux-product-design`, platform |
| Meeting Buddy capture/diarization/transcript quality | `audio-speech` | `core-python-architect`, `privacy-security` |
| PySide6 **`ui/`** dialogs and settings implementation | `core-python-architect` | `ux-product-design` |
| Interaction design for tray, pill, overlays, settings IA | `ux-product-design` (+ `/ux-state-review`) | platform, `product-owner` |
| Installer / PyInstaller / signing (Windows) | `windows-platform` | `quality-release`, `privacy-security` |
| App bundle / notarization (macOS) | `macos-platform` | `quality-release`, `privacy-security` |
| Docs / i18n / help / locales | skill `/update-documentation` | — |
| Release checklist / tag | skill `/prepare-release` + `/release-readiness` + `quality-release` | `product-owner` |

When ownership is ambiguous, `product-owner` assigns a single responsible agent and
names consultants explicitly.
