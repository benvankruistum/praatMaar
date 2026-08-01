# Project skills (praatMaar)

| Skill | Invoke |
|-------|--------|
| `update-documentation` | `/update-documentation` |
| `prepare-release` | `/prepare-release` |
| `feature-specification` | `/feature-specification` |
| `repository-orientation` | `/repository-orientation` |
| `agent-handoff` | `/agent-handoff` |
| `change-impact-analysis` | `/change-impact-analysis` |
| `architecture-decision` | `/architecture-decision` |
| `implementation-plan` | `/implementation-plan` |
| `code-review` | `/code-review` |
| `whisper-evaluation` | `/whisper-evaluation` |
| `release-readiness` | `/release-readiness` |
| `privacy-security-review` | `/privacy-security-review` |
| `ux-state-review` | `/ux-state-review` |

`/update-documentation` dekt **alle** doc-oppervlakken: markdown, help.nl/en/de,
`locales/*`, module-/Protocol-docstrings en overige inline API-docs.

`/code-review` in deze repo is de **praatMaar**-review (seams, lifecycle, focus,
audio, privacy, …). De persoonlijke Matt Pocock Standards+Spec skill in
`~/.cursor/skills/code-review` wordt hierdoor voor dit project overschreven.

Matt Pocock skills (overige) blijven persoonlijk in `~/.cursor/skills/`.
`prepare-release` roept project `/update-documentation` + `/code-review` aan.

Specialist **subagents**: `.cursor/agents/` — zie [AGENTS.md](../../AGENTS.md).
