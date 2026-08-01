---
name: change-impact-analysis
description: Analyze the technical, product, platform, privacy, testing, packaging, and documentation impact of a proposed praatMaar change. Use before cross-cutting changes or when ownership and affected components are unclear.
---

# Change impact analysis (praatMaar)

Map the **blast radius** of a proposed change before implementation. Clarify
affected components, owners, risks, and required follow-up work.

This skill is **analysis only**. Do not implement the change here. Prefer
`/repository-orientation` first when the area is unfamiliar.

## When to use

- Cross-cutting changes (lifecycle, `host` seams, modules, audio pipeline, UI)
- Ownership or affected components are unclear
- Before a large refactor, new capability, or platform-specific behaviour
- When `/feature-specification` needs a risk/dependency pass
- Before merging work that touches packaging, privacy, or multiple platforms

Skip for trivial, single-file, clearly owned fixes with no user-visible or seam
impact.

## Inputs

Need at least:

1. What would change (behaviour or technical intent)
2. Suspected area (or “unknown”)

If a product spec exists, use it. If not, restate the change in one paragraph
without inventing scope.

## Process

### 1. Orient

Run `/repository-orientation` for the topic (or reuse a current brief). Confirm
`CONTEXT.md` terms and `AGENTS.md` ownership.

### 2. Characterize the change

Classify (multiple allowed):

- Product behaviour
- Architecture / seam
- Audio / speech pipeline
- Platform-native (Windows / macOS / Linux)
- Privacy / data flow
- Packaging / installer / signing
- Docs / i18n / help
- Tests / CI only

Note whether the change is **user-visible**.

### 3. Trace dependencies

For each touched concern, list:

| Layer | Look for |
|-------|----------|
| Entry / lifecycle | `dictation.py`, `opnamesessie.py`, dicteercyclus states |
| Seams | `host/`, `indicator/` contracts vs adapters |
| Modules | `modules/`, Meeting Buddy orchestration vs capture |
| Audio | capture adapters vs pipeline semantics (see `AGENTS.md`) |
| UI | `ui/`, locales, tray/menu copy |
| Persistence | config, recovery audio, transcripts, caches |
| Packaging | `praatMaar.spec`, `installer/`, `packaging/`, version metadata |
| Tests | `tests/`, CI workflows |
| Docs | README, STATUS, help.nl/en/de, CHANGELOG, ADRs, specs |

Search for callers, Protocols, injectables, and config keys — not only the file
you expect to edit.

### 4. Platform matrix

For each supported platform in `docs/STATUS.md`, state:

- **Affected** / **unaffected** / **unknown**
- Whether behaviour can stay shared or needs a native adapter
- Risk of assuming Windows ≡ macOS ≡ Linux

Linux: if impact is claimed, require an explicit support-matrix caveat
(`linux-platform`).

### 5. Privacy and trust

Flag if the change touches:

- microphone / loopback / system audio
- raw audio retention or recovery files
- transcripts, logs, diagnostics
- model download / cache
- network or external services
- permissions, signing, updater

If any apply, mark `/privacy-security-review` (and `privacy-security`) as
mandatory and note data-flow questions. External transmission needs explicit call-out.

### 6. Product and UX impact

Note impact on:

- recording / processing / error / idle clarity
- focus-steal risk (indicators, overlays, dialogs)
- new settings (justify or reject)
- onboarding / permissions copy
- Meeting Buddy vs dicteercyclus boundaries

Consult `ux-product-design` when interaction or state presentation changes.

### 7. Testing and release impact

Identify:

- existing tests to update
- new tests required (unit / contract / platform / audio fixture)
- manual smoke checks
- packaging / upgrade / uninstall implications
- CI gaps

`quality-release` verifies; do not treat “we’ll test later” as sufficient for
cross-cutting work.

### 8. Documentation impact

Tick surfaces that will need `/update-documentation` if the change ships:

- help.nl / help.en / help.de
- `locales/*`
- README / STATUS / CHANGELOG
- ADR or spec update
- release / permissions docs

### 9. Ownership and sequencing

Using `AGENTS.md`:

- responsible implementer(s)
- consultants
- mandatory reviewers
- suggested order (orientation → spec → handoffs → implement → verify)

If multiple writers would touch the same files, resolve with `/agent-handoff`
boundaries before coding.

## Output template

```markdown
# Change impact analysis — [short name]

## Proposed change
## Change classes
## User-visible?
## Domain terms

## Affected components
| Component / path | How affected | Owner |

## Platform impact
| Platform | Impact | Notes |

## Privacy / data flow
## Product / UX impact
## Testing impact
## Packaging / release impact
## Documentation impact

## Risks
| Risk | Severity | Mitigation |

## Dependencies and sequencing
## Recommended owners
- Responsible:
- Consult:
- Review:

## Spec / ADR needed?
Yes/no — if yes: `/architecture-decision` and/or `/feature-specification`
## Recommendation
proceed | proceed with adjusted scope | investigate first | defer | split into multiple changes

## Suggested next step
`/feature-specification` | `/architecture-decision` | `/agent-handoff` | investigate X | stop
```

## Behavioural boundaries

- Do not implement the change under this skill.
- Do not hide uncertainty — prefer **unknown** over guesses.
- Do not expand product scope while analyzing impact; note temptations under
  risks or “split into multiple changes”.
- Do not ignore packaging or privacy because the core Python change looks small.
- Do not assign overlapping edit ownership without an explicit file boundary.

## Done when

- Affected components and owners are listed
- Platform, privacy, test, packaging, and docs impacts are addressed (even if
  “none” / “unknown”)
- Risks and sequencing are clear
- A concrete next step is recommended
