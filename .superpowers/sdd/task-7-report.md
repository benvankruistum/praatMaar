# Task 7 report — Config, heuristics, and Hint Engine

## Status

Implemented on `feat/meeting-buddy-mvp`.

## Changes

- Added shipped YAML defaults and immutable `MeetingBuddyConfig` loading with
  nested user overrides and a dataclass `replace()` API.
- Added final-delta heuristics for topic matching, Dutch questions, and
  candidate actions without an owner.
- Added conservative hint evaluation for the three exact MVP hint types,
  including confidence filtering, wait times, cooldowns, and the visible cap.
- Pinned `PyYAML==6.0.3` in both runtime dependency declarations.
- Added 11 focused tests.

## TDD evidence

1. The new tests first failed during collection because the three production
   modules did not exist.
2. Minimal implementations made all 11 focused tests pass.
3. Self-review corrected the low-confidence test timestamp so it exercises the
   confidence threshold rather than the question suppression timeout.

## Verification

- `python -m pytest` — 189 passed, 1 skipped.
- `python -m ruff check ...` — all checks passed.
- `python -m ruff format --check ...` — 6 files already formatted.
- `git diff --check` — no whitespace errors.
- IDE diagnostics on task files — no errors.

## Self-review

- User YAML wins while omitted nested cooldown/wait values retain defaults.
- Topic matching requires both score and token/complete-phrase evidence.
- Non-final transcript revisions do not mutate state through proposals.
- Confidence below `min_hint_confidence` never produces a hint.
- Cooldown is tracked per hint type and entity; only selected visible hints
  start cooldown.

## Remaining concerns

- Topic/action age is not represented in the current state entities, so their
  minimum wait uses the meeting-relative `now_s`; questions use `created_at`.
- Cooldown memory is held by the engine instance. Persisted emitted hints can
  become a cooldown source if engine recreation during a meeting is required.

## Commit

`Add Meeting Buddy config, heuristics, and hint engine.`

## Important findings follow-up

- Open questions now transition to `possibly_answered` when a later final
  transcript delta has sufficient token overlap within the configured window.
- Candidate-action minimum wait is measured from `ActionItem.created_at`;
  heuristic and state-service proposals preserve that creation timestamp.
- Hint evaluation hard-caps visible output at three, independent of config.
- `question_open` uses `question_hint_min_wait_s` and
  `question_hint_cooldown_s` for its timing.
- Added focused regression tests for all four findings.

## Follow-up verification

- `python -m pytest` — 193 passed, 1 skipped.
- `python -m ruff check ...` — all checks passed.
- `python -m ruff format --check ...` — all changed files formatted.
