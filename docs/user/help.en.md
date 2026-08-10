# praatMaar — Help

## Getting started

1. Start praatMaar (a tray icon appears after the model loads).
2. Place the cursor in a text field.
3. Start/stop dictation with the hotkey (default `Ctrl+Shift+Alt+Space`; see
   Settings).
4. Text is transcribed locally and — depending on your settings — pasted or
   only saved.

**Windows installers** are not code-signed. If Windows shows “Windows protected
your PC”: **More info** → **Run anyway**.

**macOS (Apple Silicon):** GitHub Releases include an unsigned
`praatMaar-*-macos-arm64.zip`. If Gatekeeper blocks it: right-click → **Open**,
or run `xattr -cr praatMaar.app`.

**Privacy (short):** speech-to-text runs locally. Sensitive files live under
`%APPDATA%\praatMaar\` (transcripts, recovery, inbox, logs). See also Privacy in
the README.

**Status & errors:** after loading you briefly see a ready pill with your hotkey.
Microphone failures do not open a blocking dialog: the status pill and tray icon
show what went wrong; the checklist lives in Settings.

**Switching microphones:** praatMaar rebinds the input device at the **start of a
dictation cycle** and when you save a different mic in Settings (useful after a
Bluetooth headset connects). It does not auto-switch while idle — start dictation
or save Settings.

**Whisper:** under Settings → **Whisper** you can tune quality (beam), the
silence filter (VAD), prompt/hotwords, and related thresholds. The Whisper
**model** (base/small/medium) stays under Advanced and still needs a restart.

## What are destinations?

A **destination** is a name linked to a folder on your computer. When you dictate,
the transcript is saved in the active destination's folder.

**Sticky:** the active destination stays selected until you switch or reset to default.
You do not need to say the name again every time.

**Auto-paste:** per destination you can allow clipboard + paste. Default is **off**
(save to the folder only). With no active destination, the global Settings option
applies.

**Pill:** the small on-screen indicator shows the active destination name (visible
even when you are not recording). No label means: default folder.

## Switching by voice

Record one short take where you say **only** the exact destination name — no extra
words before or after. praatMaar compares the entire take to your saved names
(exact match after normalization).

- **Match:** the destination becomes active and the pill updates. Nothing is pasted
  and the name itself is not saved as a transcript.
- **No match:** normal dictation flow — paste text and save in the current folder.

**Back to default:** say only **default**, **standard**, or **standaard**
(one take, exact). The active destination is cleared. All three words work,
regardless of speech or interface language.

## Where do your files go?

| Situation | Folder |
|-----------|--------|
| No active destination (default) | `%APPDATA%\praatMaar\transcripts\` |
| Active destination | The folder you linked to that name |

In the default folder, praatMaar automatically keeps only the newest transcripts
(retention). Destination folders are not pruned.

Recovery audio files (from failed recordings) always stay in
`%APPDATA%\praatMaar\recovery\`, regardless of the active destination. In
**Settings** → **Recovery audio** you can list, delete, or re-transcribe them.

## Managing via the system tray

Right-click the praatMaar icon in the system tray:

- **Settings** — microphone, hotkey, languages, recovery audio
- **Destinations** — dialog to add, edit, or remove names and folders, and set or
  clear the active destination. In that dialog you also find buttons to open the
  transcript folder or the active folder.
- **Modules** — enable or disable extensions and incremental transcription
- **Help** — this user guide
- **Quit**

## Modules and external tools

From **Modules** in the system tray you can turn extensions on or off and enable
**incremental transcription**. Whisper then runs during recording only on **new
audio chunks** (fixed time, silence/VAD, or hybrid). On stop those texts are
joined plus the unfinished tail — without re-transcribing the whole recording.

At **chunk boundaries** words can sometimes duplicate or be cut off; a short
overlap mitigates this, but not always completely. On the status pill, two LEDs
show whether a cut came from silence or from the time window.

**Event journal:** every dictation cycle is appended as JSON lines to
`%APPDATA%\praatMaar\events\events.jsonl` (macOS: Application Support). External
programs can watch that file without modifying praatMaar. Each event has a
`session_id`, `type` (e.g. `transcript.saved`), and metadata. The journal does
**not** store full transcript text — it records length (`transcript_chars`) and
other metadata. Transcript files themselves live under `transcripts\` or your
destination folder.

**Inbox mirror** (on by default): copies each saved transcript to
`%APPDATA%\praatMaar\inbox\` — a fixed drop zone for scripts.

Recovery re-transcription (Settings → Recovery audio) emits the same kind of
events with `source: "recovery"`.

## Risks and tips

**Whisper mishears the name**
If the transcript does not exactly match a destination name, nothing extra happens:
you stay on the current destination and the text is processed normally. Safe, but you
will not switch.

**Short or generic names**
Names like "notes" or "work" are more likely to appear accidentally in normal dictation.
Choose short but unique names, e.g. "shopping-list" or "project-alpha".

**Unencrypted files**
Transcripts are stored as plain text files on disk, without encryption. Do not use
destinations in shared or unsecured folders if you dictate sensitive content.

## Meeting Buddy and Microsoft Teams (Windows)

Enable **Meeting Buddy** via tray → **Modules**. After **Save**, that window stays
open and shows buttons for start, quick start, stop, agenda, and properties. The
tray also has **Meeting Buddy ▸** with the same actions.

- **Start meeting…** opens the agenda (library with Recent + all `.md` agendas).
- **Start meeting (quick)** starts with the current agenda without a dialog.
- **Edit agenda** to save/load agendas without starting.
- **Properties** for meeting audio (Windows loopback), output device, and
  optionally a different transcript folder.

During a meeting the transcript grows as a `.md` file under
`%APPDATA%\praatMaar\meeting-buddy\transcripts\` (final text only; changeable
in Properties). On stop you get a notification with the path; the last audio
buffer and pending transcription chunks are flushed first.

### Local LLM, live summary, and agenda review

Optional (off by default): enable **Local LLM** under **Modules**. It uses
[Ollama](https://ollama.com/). Under **Properties** choose:

- **Default (local Ollama):** `http://127.0.0.1:11434` + model `qwen2.5:7b`
- **Custom Ollama server:** same Ollama API, different base URL (host + port) and
  model name — useful for a heavier model on this machine or on the LAN

Module actions let you check status, open install help, and download the model
(local `ollama pull`). Without a ready Local LLM, Meeting Buddy stays on
heuristic hints.

With Local LLM ready, turn on live summary and agenda review in Meeting Buddy
**Properties** (off by default):

- **Live summary** in the overlay (time / new-text thresholds).
- **Agenda review**: status ladder per agenda item and “questions from others”
  (experimental; depends on speaker detection).

Enable the **Speaker Detection** module (Modules) for **single-microphone**
group conversations: praatMaar locally labels anonymous speakers (`spk_1`,
`spk_2`, …) without identifying who you are.

On Windows, Meeting Buddy can also capture **meeting audio** from the chosen
Windows output device via **WASAPI loopback** (not Stereo Mix), mixed with your
microphone. Pick the same device Teams/Zoom is playing through. Bluetooth often
has no loopback endpoint — prefer speakers or an HDMI/monitor output.

For Teams calls:

1. Set Windows **sound output** to the device Teams plays through (often your headset).
2. Set Teams **speaker** to the same device.
3. Use a **headset** to reduce echo (your mic should not pick up speakers).

The Meeting Buddy overlay shows whether meeting audio is active. If loopback is
unavailable, only your microphone is captured and the overlay warns you.
