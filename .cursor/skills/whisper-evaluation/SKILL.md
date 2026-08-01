---
name: whisper-evaluation
description: Evaluate Faster-Whisper changes in praatMaar using reproducible audio fixtures and measurements for accuracy, latency, startup time, CPU, memory, model choice, language settings, and VAD behaviour.
---

# Whisper evaluation (praatMaar)

Measure the impact of Faster-Whisper / transcription-pipeline changes with
**reproducible fixtures** and recorded metrics. Do not claim quality or
performance wins from a single live microphone take.

Local Faster-Whisper only — never describe this as the OpenAI cloud Whisper API
unless the code under test explicitly calls that service.

Owner: `audio-speech`. Consult `privacy-security` before adding fixture audio
that could contain real speech, and `quality-release` when results gate a merge.

## When to use

- Model size, `compute_type`, device (CPU/CUDA), language, `beam_size`, or VAD
  settings change
- Incremental / chunk transcription, segmentation, or stop-path changes
- Suspected regressions in accuracy, latency, startup, CPU, or memory
- Comparing alternatives before accepting a default

Skip for pure refactors that cannot change decode settings or audio→text paths
(still run unit tests; no eval suite required).

## Privacy rules

- Prefer **synthetic** or **consented, non-sensitive** fixtures.
- Do not commit real user dictation, meeting audio, or recovery WAVs.
- Do not paste fixture transcripts that contain secrets into logs or PRs.
- Store large binary fixtures outside git if needed; document how to obtain them.
- Default fixture home (create when missing): `tests/fixtures/audio/` with a
  `README.md` describing format, license/consent, and expected text.

## What to compare

Always record **baseline vs candidate** (same machine, same fixtures):

| Dimension | What to measure |
|-----------|-----------------|
| Accuracy | Exact match / WER-like word error vs expected text; note NL/EN/DE |
| Latency | Wall time audio→final text (exclude UI paste); per-chunk if incremental |
| Startup | Model load / first-inference warm-up time |
| CPU | Avg/peak during load and during decode (Task Manager / `psutil` OK) |
| Memory | RSS (and VRAM if CUDA) before load, after load, after N runs |
| Model choice | name/size + why candidate is acceptable for product defaults |
| Language | fixed `nl` / auto / other — mismatch symptoms |
| VAD | `vad_filter` / silence thresholds — clipping of speech vs false triggers |

Separate:

- model warm-up
- capture latency (out of scope unless the change touches capture)
- transcription latency
- insertion/paste latency (usually out of scope for this skill)

## Environment card (required in every report)

```markdown
## Environment
- OS / arch:
- CPU / RAM / GPU:
- Python:
- faster-whisper / ctranslate2 versions:
- Model:
- compute_type / device:
- Language setting:
- beam_size / VAD / chunk settings:
- Commit / branch:
- Fixture set + hash or path:
```

Without an environment card, do not claim a regression or improvement.

## Fixture requirements

Each fixture needs:

| Field | Example |
|-------|---------|
| Audio path | `tests/fixtures/audio/nl_short_silence_pad.wav` |
| Sample rate / channels / format | 16 kHz mono PCM WAV preferred |
| Language | `nl` |
| Expected text | canonical transcript |
| Duration | seconds |
| Notes | accents, numbers, proper nouns, trailing silence |

Minimum useful set for a change:

1. Short clean Dutch utterance
2. Longer utterance (stress latency / chunking)
3. Leading/trailing silence (VAD)
4. Optional: English or mixed if language detection is in scope

If fixtures do not exist, **create a fixture plan** first (synthetic generation
or documented recording steps). Do not block forever — say what is missing and
run whatever reproducible subset exists, marking gaps.

## Process

### 1. Orient

- `/repository-orientation` on the transcription path
- Diff the change: `opnamesessie.py`, `chunk_transcription.py`, `dictation.py`
  model load, `modules/whisper.py`, Meeting Buddy STT if touched
- Note current defaults (model, `compute_type`, `beam_size`, `vad_filter`,
  language)

### 2. Define hypothesis

One sentence: what should improve or stay within budget, and what must not
regress.

### 3. Freeze baseline

On the pre-change commit (or main merge-base), run the fixture suite once.
Save raw timings and transcripts.

### 4. Run candidate

Same commands, same fixtures, same machine. Prefer scripted invocation over
GUI dictation for repeatability (direct `WhisperModel.transcribe` or internal
helpers). If only GUI is possible, document hotkey path and why.

Suggested measurement discipline:

- Warm-up: discard first run or report it separately as startup
- Repeat: ≥3 timed runs for latency; report median + min/max
- Keep batch size / beam / VAD identical unless that is the variable under test
- One variable at a time when comparing settings

### 5. Score accuracy

For each fixture:

- normalized compare (case/punctuation policy stated)
- list substitutions / deletions / insertions for failures
- flag hallucinations on silence-only regions when VAD is involved

### 6. Interpret

- Improvement on one fixture with regression on another → not a blanket win
- Larger models: require explicit product justification (RAM, startup, laptop)
- VAD tighter: check clipped first/last words
- Chunk pipeline: measure stop-time and partial stability, not only final WER

### 7. Report

Use the template below. Recommendation must be one of:

- **Accept candidate**
- **Accept with follow-up**
- **Keep baseline**
- **Inconclusive** (missing fixtures / unstable machine / mixed results)

## Report template

```markdown
# Whisper evaluation — [change]

## Hypothesis
## Environment
## Fixtures
## Baseline config
## Candidate config

## Results
| Fixture | Metric | Baseline | Candidate | Delta |

## Accuracy notes
## Latency / startup notes
## CPU / memory notes
## VAD / language notes

## Risks
## Recommendation
## Evidence paths
(commands, log snippets, branch SHAs)
## Follow-up
```

## Implementation hooks (optional)

When adding lasting eval support (only if the user asks to build it):

- Prefer pure functions + pytest marks (e.g. `@pytest.mark.whisper_eval`) so
  default CI stays fast
- Gate heavy eval behind opt-in env var or manual target
- Keep fixtures documented in `tests/fixtures/audio/README.md`
- Owner remains `audio-speech`; packaging size impact → `windows-platform` /
  `quality-release` if defaults change shipped model

## Behavioural boundaries

- Do not ship a heavier default model without product + measured cost.
- Do not treat unit tests with fake models as quality evidence.
- Do not use cloud STT to “verify” local Whisper output.
- Do not commit sensitive audio.
- Do not claim cross-machine performance without re-running there.

## Done when

- Baseline and candidate measured on the same fixtures/environment
- Accuracy, latency, startup, and resource axes addressed (or marked n/a with
  reason)
- Clear recommendation with evidence
- Gaps (missing fixtures) explicitly listed
