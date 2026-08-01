---
name: privacy-security-review
description: Review a praatMaar feature or change for microphone, audio, transcript, clipboard, logging, storage, retention, deletion, permissions, external communication, model-download, dependency, installer, and supply-chain risks.
---

# Privacy & security review (praatMaar)

Review a feature or diff for privacy and security risk. Local-first and data
minimisation are the defaults. Prefer evidence from code and config over marketing
claims.

This skill is **read-only**. Report findings and required mitigations; do not
“fix forward” by editing production code unless the user asks.

You may delegate the same checklist to the `privacy-security` subagent; the
report format below remains required either way.

## When to use

- Feature touches microphone, loopback, transcripts, recovery audio, clipboard,
  logs, model download, network, permissions, installer, or new dependencies
- `/change-impact-analysis` flagged privacy/data-flow impact
- Before merge of Meeting Buddy / STT / packaging changes
- `/release-readiness` when this release includes sensitive changes
- User asks for privacy or security review

Skip only when the change is clearly unrelated (e.g. comment typo) — state why.

## Scope the review

1. Pin range (default merge-base with `origin/main`):

```bash
git fetch origin
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main)
git log --oneline "$BASE"..HEAD
git diff --stat "$BASE"...HEAD
git diff "$BASE"...HEAD
```

Or review a named feature/spec even if partially unimplemented (design review).

2. `/repository-orientation` on the data path if unfamiliar.
3. Read `CONTEXT.md`, ADR-0004 (local-first inference) if LLM/STT related,
   `SECURITY.md` if present, and the feature spec.

## Principles

- Local-first by default; external transmission needs explicit design + disclosure
  + `product-owner` approval
- Minimise raw audio, transcripts, metadata, and logs
- Sensitive content must not appear in logs by default
- Recovery needs bounded retention and clear deletion
- Permissions: least privilege, purpose explained
- Model downloads and artifacts need trustworthy source/integrity story
- Privacy claims must match implementation
- Fail closed when authenticity or destination is uncertain

## Checklist (mark each: ok / risk / n/a)

### Microphone and audio

- [ ] Capture start/stop is unambiguous to the user
- [ ] Loopback / system audio scope is clear (Meeting Buddy)
- [ ] No capture while idle / after cancel
- [ ] Temp audio files permissions and lifetime

### Transcripts

- [ ] Where transcripts are stored (Meeting Buddy paths, clipboard only, etc.)
- [ ] No unexpected persistence
- [ ] User can find/delete stored transcripts

### Clipboard

- [ ] Clipboard write necessary and scoped
- [ ] Restore behaviour reliable or explicitly not restored
- [ ] Paste targets the intended app (no focus steal increasing mis-paste risk)

### Logging and diagnostics

- [ ] Default logs omit transcript/audio content
- [ ] Debug flags that increase sensitivity are documented and off by default
- [ ] Crash/telemetry: none, or reviewed and disclosed

### Storage, retention, deletion

- [ ] Recovery audio retention bounds
- [ ] Cache/model directories known (`app_dir` / platform paths)
- [ ] Uninstall vs user-data policy documented
- [ ] Stale file accumulation prevented or guided

### Permissions

- [ ] Microphone / Accessibility / Input Monitoring / etc. justified
- [ ] Denial and revocation paths safe and explainable
- [ ] No repeated nagging without actionable path

### External communication

- [ ] Enumerate all network calls in the change (model download, updates, LLM, …)
- [ ] Destinations, payloads, TLS, and user visibility
- [ ] Cloud STT/LLM requires ADR + product approval (escalate)

### Model download and cache

- [ ] Source (e.g. Systran/faster-whisper) explicit
- [ ] Integrity / unexpected replacement risk considered
- [ ] Cache location and growth acceptable

### Dependencies and supply chain

- [ ] New packages justified; license OK
- [ ] Native wheels / PyInstaller hiddenimports do not pull unexpected networkers
- [ ] Pins or lock expectations noted for release

### Installer and updates

- [ ] Windows unsigned-by-design + SmartScreen disclosure still accurate
- [ ] macOS signing/notarization posture for the distribution channel
- [ ] Update mechanism (if any) authenticity story
- [ ] Installer/logs do not embed secrets or transcripts

## Threat prompts

Work through applicable items from `.cursor/agents/privacy-security.md`
(Threat-model prompts). Especially:

- local process reading temp audio/transcripts
- log leakage
- clipboard residue
- malicious/replaced model influence
- loopback capturing more than expected
- synthetic input to the wrong application

## Severity

| Level | Meaning |
|-------|---------|
| **Critical** | compromise, RCE, secret exposure, broad sensitive disclosure |
| **High** | likely sensitive exposure, insecure update/installer, permission abuse, privacy-claim violation |
| **Medium** | needs mitigation before broad release or agreed deadline |
| **Low** | defence-in-depth |
| **Informational** | observation / future hardening |

## Mandatory escalation

Require explicit `product-owner` approval + design/ADR for:

- cloud transcription
- sending audio/transcripts to an external AI provider
- telemetry/crash reports with user context
- persistent meeting recordings beyond current product policy
- account creation / remote sync
- automatic updates
- third-party plugins with data access

## Report template

```markdown
# Privacy and security review — [change]

## Decision
Approved | Approved with conditions | Changes required | Rejected | Insufficient evidence

## Range / scope
## Data flow
(capture → process → store → insert → recover → log → delete)

## Assets and trust boundaries
## External communication
## Storage and retention
## Permissions
## Dependencies and supply chain
## Checklist summary
| Area | Result |

## Findings by severity
### Critical / High / Medium / Low / Informational

## Required mitigations
## Verification required
## Residual risk
## User-facing privacy communication
## Decision rationale
```

## After the review

- Blockers → owning implementation agent via `/agent-handoff`
- Conditions → track through `/release-readiness`
- UX wording gaps → `ux-product-design`
- Product risk acceptance → `product-owner` only

## Behavioural boundaries

- Do not approve on stated intent without tracing implementation
- Do not assume local-only because README says so — verify imports and calls
- Do not put real user audio/transcripts into the report
- Do not recommend disabling OS protections for convenience
- Do not silently accept residual Critical/High risk for the Product Owner

## Done when

- Checklist areas are marked
- Findings are severity-ranked
- Decision is explicit
- Mitigations and verification are actionable
