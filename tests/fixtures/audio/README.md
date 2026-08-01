# Audio fixtures for Whisper evaluation

Privacy-safe, reproducible clips for `/whisper-evaluation`.

## Rules

- No real user dictation or meeting recordings.
- Prefer synthetic speech or explicitly consented non-sensitive prompts.
- Document license/consent per file below when adding binaries.
- Prefer 16 kHz mono PCM WAV.

## Manifest

| File | Language | Duration | Expected text | Notes |
|------|----------|----------|---------------|-------|
| _(none yet)_ | | | | Add fixtures when first eval runs |

## How to add a fixture

1. Create the WAV under this directory (or document an external path + checksum).
2. Add a row to the manifest with expected transcript.
3. Keep filenames descriptive: `nl_short_clean.wav`, `nl_silence_padded.wav`, …
