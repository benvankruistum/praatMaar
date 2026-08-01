# Design — Meeting Buddy dual source waveforms

**Date:** 2026-08-01  
**Status:** approved (approach A)  
**Branch:** `feat/mb-dual-source-waveforms`

## Problem

During a Meeting Buddy session, mic and WASAPI loopback are mixed before STT.
The dicteer-pill waveform shows only the **mixed** RMS. The overlay only shows
boolean loopback status text. Users cannot tell whether silence is “no meeting
audio arriving” vs “audio arrives but transcription is weak.”

## Decision

Show **two short scrolling bar-waveforms** in the Meeting Buddy overlay only
(not on the dicteer-pill), labeled Mic and Meeting.

| Choice | Decision |
|--------|----------|
| Visual | Hybrid: one compact waveform row per source (~12–18 bars) |
| Placement | Overlay only (under status / near recording banner) |
| Loopback off / unavailable | Meeting row stays visible, flat, plus existing unavailable warning copy |
| Level feed | Approach A: dual RMS ringbuffers filled **before** mix in continuous capture |

## Data feed

In `modules/_builtin/audio_capture.py`:

1. On each mic/loopback stream callback append → push RMS to `push_mic_level` /
   `push_loopback_level` **immediately** (independent of mix flush)
2. On mix flush → keep `push_level(mixed)` for the dicteer-pill only
3. Reset dual buffers when a continuous-capture session starts

This way the Meeting row moves as soon as WASAPI delivers frames, even if the
mic side has not yet aligned for mixing. Logs showing
`loopback levert geen data (starved)` mean the chosen output is not rendering
into that loopback stream — meters stay flat and the unavailable warning shows.

Mid-meeting device changes call `reload_config()` + `reconnect_capture()` so the
new loopback device is actually opened.

## Overlay UI

- Two rows: label + bar strip (Mic / Meeting), compact height
- Poll ~50 ms (or overlay timer ≤100 ms) via `snapshot_mic_levels` /
  `snapshot_loopback_levels` on the Qt thread
- When `loopback_requested` and `loopback_active is False`: Meeting bars flat;
  show the same unavailable warning string family already used in the banner
  (`recording.mic_only_unavailable` or a short dedicated line)
- When loopback not requested (mic-only mode): Meeting row flat + mic-only
  wording (no false “unavailable” if user chose mic-only)
- Non-activating HUD flags unchanged; no focus steal
- No position persistence for meters; no transcript UI

## Out of scope

- Dual waveforms on the dicteer-pill or mini-pill
- Changing mix gains / STT mix behaviour
- Persisting meter history to disk
- Capability-level level events (approach B)

## Success

With loopback on and Teams/speakers playing, Meeting bars move independently of
Mic. With wrong device / no render, Meeting stays flat while Mic still moves,
and the warning remains visible.
