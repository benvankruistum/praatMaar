# Release checklist — praatMaar

## Sync

| Location | Action |
|----------|--------|
| `pyproject.toml` → `version` | `X.Y.Z` (no `v`) |
| Git tag | `vX.Y.Z` |
| `CHANGELOG.md` | `## [X.Y.Z] - YYYY-MM-DD` |
| `docs/release-windows.md` / `docs/release-macos.md` | Example artefact names |
| `docs/STATUS.md` | Latest release note if mentioned |

`scripts/build-windows.ps1` / Release workflow take `-Version`; keep
`pyproject.toml` aligned anyway.

## Pre-tag

- [ ] Branch `release/vX.Y.Z`; not on `main`
- [ ] `/update-documentation` (delta + full-audit)
- [ ] `/code-review` vs previous tag / `main`; blockers handled
- [ ] CI / tests green
- [ ] CHANGELOG cut; `[Unreleased]` empty
- [ ] User confirmed version + tag push

## Post-tag

- [ ] GitHub Windows Release workflow OK
- [ ] Optional macOS PyInstaller build
- [ ] Smoke dictation once
