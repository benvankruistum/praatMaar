---
name: release-readiness
description: Assess whether a praatMaar version is ready for release by checking tests, versions, builds, installers, app bundles, signing, notarization, upgrade behaviour, changelog, documentation, known limitations, and privacy or security reviews.
---

# Release readiness (praatMaar)

Decide whether version **X.Y.Z** is ready to tag and ship. This is a **gate
assessment**, not the release choreography itself.

- To cut versions / CHANGELOG / tag workflow → `/prepare-release`
- To implement packaging fixes → platform agents (`windows-platform`,
  `macos-platform`)
- Independent verification mindset → align with `quality-release`

Default: **read-only**. Run tests and inspect builds; do not bump versions or
push tags here. Report precise gaps to the owning agent.

## When to use

- Before tagging `vX.Y.Z`
- Before `/prepare-release` step “Tag”
- After merge of release PR, before publishing artifacts
- User asks “kunnen we releasen?” / “release ready?”

## Inputs

Confirm:

1. Target version `X.Y.Z` (no `v` in pyproject; tag is `vX.Y.Z`)
2. Platforms in scope (default: Windows required; macOS if port claims ship)
3. Git ref to assess (default: `main` after release merge, or `release/vX.Y.Z`)

## Process

### 1. Orient

```bash
git fetch origin
git status -sb
git branch --show-current
git log -5 --oneline
git tag -l 'v*' --sort=-v:refname | head -10
```

Read:

- `docs/STATUS.md`
- `CHANGELOG.md`
- `docs/release-windows.md`
- `docs/release-macos.md`
- `.cursor/skills/prepare-release/release-checklist.md`
- Recent `/code-review` findings if present in chat

### 2. Version consistency

Check alignment (see Windows release doc table):

| Location | Expected |
|----------|----------|
| `pyproject.toml` `version` | `X.Y.Z` |
| Git tag plan | `vX.Y.Z` (not yet required to exist) |
| `CHANGELOG.md` | `## [X.Y.Z] - YYYY-MM-DD`; `[Unreleased]` empty or only future notes |
| `version_info.txt` | File/ProductVersion match if used |
| `installer/praatMaar.iss` fallback | match if present |
| `scripts/build-windows.ps1` default `-Version` | match if present |
| Docs examples | release-windows / release-macos / STATUS |

Mark each: **ok** / **mismatch** / **n/a**.

### 3. Automated tests and CI

- Run `pytest -q` (or project’s documented test command) on the release ref
- Check GitHub Actions on the release PR / `main` (`gh pr checks` / `gh run list`)
- Note flaky or skipped tests — flaky ≠ green

### 4. Code and product review gates

- `/code-review` vs previous `v*` tag (or `origin/main` if first) — blockers?
- Open product ACs for this release (STATUS / specs) — unmet must-haves?
- Whisper/model default changes → `/whisper-evaluation` evidence if applicable

### 5. Documentation

- `/update-documentation` surfaces current: help.nl/en/de, locales, README,
  STATUS, module docstrings for shipped behaviour
- CHANGELOG describes user-visible changes and **known limitations**
- Privacy-impacting changes disclosed

### 6. Windows packaging (when in scope)

Evidence needed (run or cite recent successful run):

- [ ] PyInstaller build succeeds (`praatMaar.spec` / `scripts/build-windows.ps1`)
- [ ] Setup exe and/or portable zip produced with correct version in name
- [ ] Fresh install launches (no console flash unless intended)
- [ ] Portable launch works
- [ ] Upgrade from previous published version (if one exists)
- [ ] Uninstall does not delete unrelated user files; app data policy documented
- [ ] Dictation smoke: hotkey → record → paste
- [ ] Signing: project ships **without** Authenticode by policy — SmartScreen
      warning documented, not treated as a blocker unless policy changed
- [ ] New native deps (e.g. WASAPI / PyAudioWPatch) included in spec/hiddenimports

See `docs/release-windows.md`.

### 7. macOS packaging (when in scope)

- [ ] `.app` builds on Apple Silicon (or documented arch)
- [ ] Bundle launches under Gatekeeper expectations for the distribution channel
- [ ] Signing / notarization / staple: **required for external distribution**;
      optional for local-only — state which channel this release uses
- [ ] TCC paths documented (`docs/macos-permissions.md`)
- [ ] Zip/DMG naming matches version
- [ ] Smoke: menu bar / hotkey / paste / permissions denial path

See `docs/release-macos.md`. If macOS is claimed in CHANGELOG but untested →
**blocker** or explicit “macOS unsupported this tag” limitation.

### 8. Upgrade and migration

- Config migrations for this version tested or N/A
- Recovery audio / transcript paths remain understandable
- Model cache behaviour on first run after upgrade documented

### 9. Privacy and security

- No new cloud/telemetry without accepted ADR + disclosure
- `privacy-security` review for sensitive changes this release — prefer
  `/privacy-security-review` (or N/A with reason)
- Dependency/supply-chain notes for new packages in the ship set
- Signing/notarization posture matches docs (Windows unsigned by design today)

### 10. Known limitations

List limitations that will ship. Each needs an explicit **accept** (product) or
becomes a blocker. Examples: SmartScreen, macOS unsigned dev builds, Linux not
supported, model download on first run.

### 11. Decision

Use one recommendation:

| Decision | Meaning |
|----------|---------|
| **Ready to tag** | Gates green for in-scope platforms |
| **Ready with waivers** | Listed limitations explicitly accepted |
| **Not ready** | Blockers remain |
| **Insufficient evidence** | Missing builds/tests/reviews |

Do not say “ready” if Windows build/install evidence is absent when Windows is
in scope.

## Report template

```markdown
# Release readiness — vX.Y.Z

## Ref assessed
## Platforms in scope
## Decision

## Version consistency
| Location | Status | Notes |

## Tests / CI
## Code review
## Documentation
## Windows packaging
## macOS packaging
## Upgrade / migration
## Privacy / security
## Known limitations (accepted)
## Blockers
## Non-blocking follow-ups
## Evidence
## Next step
`/prepare-release` tag | fix blockers | gather evidence | waive limitation
```

## Relationship to other skills

| Skill | Role |
|-------|------|
| `/prepare-release` | Executes docs review, version cut, tag after OK |
| `/release-readiness` | Go/no-go assessment with evidence matrix |
| `/code-review` | Diff quality before merge/tag |
| `/update-documentation` | Doc surfaces |
| `/whisper-evaluation` | Model/default speech changes |
| `quality-release` agent | May own or co-run this assessment |

Suggested order before publish: docs audit → code-review → **release-readiness**
→ user confirms → tag via `/prepare-release`.

## Behavioural boundaries

- Do not push tags or change `pyproject.toml` under this skill.
- Do not weaken acceptance criteria to force a green gate.
- Do not treat developer-machine source runs as install proof.
- Do not claim macOS or Linux support without matrix evidence.
- Signing: respect current project policy (Windows unsigned); do not invent a
  certificate requirement unless product policy changed.

## Done when

- Decision is explicit
- Every in-scope platform section is filled (ok / gap / n/a)
- Blockers and accepted limitations are listed
- Next step is clear
