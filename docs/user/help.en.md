# praatMaar — Help

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

**Back to default:** say only the word **standaard** (one take, exact). The active
destination is cleared. (The reset word is always *standaard*, even when the UI is
in English or German.)

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
**incremental transcription**. With incremental transcription, Whisper runs in the
background while you record; modules and external tools can receive interim text
before you stop.

**Event journal:** every dictation cycle is appended as JSON lines to
`%APPDATA%\praatMaar\events\events.jsonl` (macOS: Application Support). External
programs can watch that file without modifying praatMaar. Each event has a
`session_id`, `type` (e.g. `transcript.saved`), and metadata.

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
