# Product specification — v1.0.0 support & release scope

## Status

**Accepted** — 2026-08-01 (human owner: Decisions 1A / 2A / 3A).

## Context

Product Owner en UX-review (2026-08-01) bevelen aan: eerst een betrouwbare
Windows-dicteer-core voor **v1.0.0**, Meeting Buddy experimenteel houden tot er
bewijs is, Linux/cloud uitstellen. Recente merges (#45 chunk-pipeline, #46
WASAPI-loopback) zijn capability, geen graduation.

Bronnen: `docs/STATUS.md`, ADRs 0003–0005, verbeterplannen PO/UX.

## Problem

Zonder expliciete 1.0-scope lopen docs, release-claims en experimentele modules
door elkaar (o.a. STATUS noemt nog `indicator._win` / Tk-settings terwijl
PySide6 + `indicator._qt` de shipping path is). Gebruikers en agents weten niet
wat “ondersteund” betekent voor macOS of Meeting Buddy.

## Goal

Vastleggen wat **v1.0.0** wél en niet belooft: platforms, modules, signing,
bewijs, en wat daarna komt.

## Non-goals (deze beslissing)

- Feature-implementatie of UX-specs zelf (volgen na acceptatie)
- Linux Wayland-product
- Cloud STT/LLM
- Meeting Buddy of Local LLM uit “experimenteel” tillen zonder checklist

## Users and scenarios

- Windows-gebruiker die Setup/portable downloadt en dicteert
- Privacy-bewuste gebruiker die claims in README/Help moet kunnen vertrouwen
- Optioneel: Mac-gebruiker die vanuit bron draait (geen Gatekeeper-belofte tenzij gekozen)

## Functional requirements

- **FR-01** v1.0.0 primaire belofte = **Windows 10/11 dicteercyclus**
  (hotkey → Opnamesessie → lokale Faster-Whisper → klembord/plakken via `host`)
  met focus-veilige indicator (pill).
- **FR-02** Release-docs en `docs/STATUS.md` beschrijven die belofte zonder
  verouderde UI-/privacy-claims (PySide6/`indicator._qt`; journal zonder volle
  transcript-tekst waar van toepassing).
- **FR-03** Experimentele modules (Meeting Buddy, local-llm, speaker-detection,
  optionele incrementele/chunk-transcriptie) blijven **opt-in** en gelabeld
  experimenteel in 1.0 tenzij een aparte graduation-beslissing volgt.
- **FR-04** WASAPI-loopback (#46) telt als experimentele MB-capability; 1.0
  vereist geen “Teams werkt altijd”-claim. Wel: eerlijke limieten in Help/STATUS.
- **FR-05** Linux blijft experimenteel / geen 1.0-distributiedoel.
- **FR-06** Cloud-inference blijft afgewezen als default (ADR-0004).

## Quality requirements

- **QR-01** `/release-readiness` groen (of Ready with waivers) vóór tag `v1.0.0`
  voor Windows packaging in scope.
- **QR-02** Privacy-claims matchen implementatie (`/privacy-security-review` of
  docs-skim op journal/recovery/destinations).
- **QR-03** Bekende limieten (SmartScreen unsigned, model-download first run,
  MB experimenteel) staan in CHANGELOG/STATUS/Help.

## Supported platforms (proposed matrix)

| Platform | v1.0.0 claim | Evidence required |
|----------|--------------|-------------------|
| Windows 10/11 | **Ondersteund (primair)** — Setup + portable | Tests + install/smoke + docs |
| macOS Apple Silicon | **A: vanuit bron ondersteund** (runtime) — geen Gatekeeper-distributiebelofte in 1.0 | Bestaande runtime-check; docs eerlijk |
| macOS signed `.app` | **Buiten 1.0** tenzij Decision 3 = B | Gatekeeper smoke op schone Mac |
| Linux | **Experimenteel** — geen 1.0-belofte | STATUS-noot voldoende |

## Acceptance criteria

- Given de eigenaar heeft Decisions 1–3 bevestigd, When STATUS/README/Help
  worden bijgewerkt (stap 2), Then de support-matrix en experimentele labels
  matchen deze spec.
- Given tag `v1.0.0`, When een gebruiker alleen core-dictation op Windows
  gebruikt, Then product claims geen afhankelijkheid van MB/LLM/signing die
  niet geleverd zijn.
- Given Meeting Buddy enabled, When 1.0 docs gelezen worden, Then de gebruiker
  ziet “experimenteel” en geen “volledig ondersteunde Teams-opname”.

## Required evidence (before tag)

- Docs honesty slice voltooid (stap 2)
- `/code-review` + `/release-readiness` op release-ref
- Windows build/install smoke (zie `docs/release-windows.md`)
- Optioneel: Teams-loopback checklist alleen als Decision 1 = variant “MB
  validated” (niet de default-aanbeveling)

## Agent ownership

| Area | Owner |
|------|--------|
| Deze beslissing | `product-owner` + human owner |
| Docs na acceptatie | `/update-documentation` |
| Release gate | `/release-readiness` + `quality-release` |
| MB bewijs (later) | `audio-speech` + `windows-platform` |
| UX states (na stap 1) | `/ux-state-review` |

## Open questions — Decisions for human owner

### Decision 1 — Wat zit er in v1.0.0?

| Optie | Inhoud |
|-------|--------|
| **A (gekozen)** | Core Windows-dictation + eerlijke docs/privacy + release-evidence. MB/LLM/chunk blijven experimenteel opt-in. |
| **B** | A + Meeting Buddy “loopback-validated” (Teams-checklist groen) nog steeds experimenteel gelabeld |
| **C** | A + MB graduation uit experimenteel (hoog; niet aanbevolen nu) |

**Besluit: A**

### Decision 2 — Code signing (Windows)

| Optie | Inhoud |
|-------|--------|
| **A (gekozen)** | Blijf unsigned; SmartScreen + “Meer info” eerlijk in docs/Help |
| **B** | Authenticode dit kwartaal (budget/ops) |

**Besluit: A**

### Decision 3 — macOS in 1.0

| Optie | Inhoud |
|-------|--------|
| **A (gekozen)** | “Ondersteund vanuit bron” / runtime-geverifieerd; signed `.app`/Gatekeeper = post-1.0 |
| **B** | 1.0 blokkeert op signed `.app` + Gatekeeper-smoke |

**Besluit: A**

---

## Next steps

1. ~~Mark this spec Accepted~~
2. Stap 2: docs honesty (`STATUS`, README, Help/locales, ADR-0003 aanvulling)
3. Daarna: `/ux-state-review` dicteercyclus (UX must-haves)
