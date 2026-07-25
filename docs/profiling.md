# Profileren — praatMaar

Hoe je pijnpunten in de **dicteercyclus** (opname → Faster-Whisper → plakken)
vindt. Drie lagen: ingebouwde cycle-timings, sampling (py-spy), CPU/geheugen
(Scalene).

## 1. Cycle-timings (standaard aan)

Elke geslaagde of mislukte transcriptie-stop schrijft één regel naar stdout én
`praatMaar.log` (via `app_logging`):

```text
cycle.timing id=a1b2c3d4 path=full record=2.341s stop_join=0.012s wav=0.008s whisper=1.234s deliver=0.351s total_after_stop=1.605s
```

| Veld | Betekenis |
|------|-----------|
| `id` | Eerste 8 tekens van `session_id` |
| `path` | Altijd `full` bij stop (finale Whisper over de hele buffer). Historisch kon `partial` voorkomen toen stop de laatste interim-tekst hergebruikte. |
| `record` | Opnameduur (hotkey start → stop) |
| `stop_join` | Stop tot worker-thread start (incl. join van incremental-worker) |
| `wav` | WAV schrijven uit audiobuffer |
| `whisper` | Faster-Whisper `transcribe` + segment-iteratie |
| `deliver` | Bestemming / opslaan / klembord / plakken (`_apply_transcript`) |
| `total_after_stop` | Stop tot timingregel (eind van de worker) |

Logpad:

- Windows: `%APPDATA%\praatMaar\praatMaar.log`
- macOS: `~/Library/Application Support/praatMaar/praatMaar.log`

Filter:

```powershell
Select-String -Path "$env:APPDATA\praatMaar\praatMaar.log" -Pattern "cycle.timing"
```

**Interpretatie:** als `whisper` het grootste deel van `total_after_stop` is,
optimaliseer model/compute; als `deliver` hoog is, kijk naar paste-delay of
I/O; als `stop_join` hoog is met incremental aan, wacht je op een in-flight
partial vóór de finale run.

Implementatie: `CycleTiming` / `format_cycle_timing` in `opnamesessie.py`.

## 2. py-spy (sampling tijdens echt gebruik)

Werkt op een **draaiend** proces, ook met native CTranslate2/Whisper. Geen
herstart van de app met speciale flags nodig.

```powershell
pip install py-spy

# Terminal 1 — app met console
.\.venv\Scripts\python.exe dictation.py

# Terminal 2 — PID opzoeken (Task Manager of:)
Get-Process python* | Select-Object Id, ProcessName, Path

# Live top
py-spy top --pid <PID>

# Flamegraph (~60 s); tijdens die tijd een paar dicteercycli doen
py-spy record -o profile.svg --pid <PID> --duration 60
```

Open `profile.svg` in een browser. Zoek stacks rond `opnamesessie`,
`faster_whisper`, `ctranslate2`, Qt (`PySide6`).

Op Windows kan py-spy admin-rechten nodig hebben voor sommige processen; start
de app vanuit bron (`dictation.py`), niet alleen de gebundelde `.exe`, voor de
beste symbolen.

## 3. Scalene (CPU + geheugen)

Geschikt als je vermoedt dat geheugen of Python-CPU (niet alleen native Whisper)
een rol speelt. Start de app **onder** Scalene:

```powershell
pip install scalene
.\.venv\Scripts\scalene.exe --cpu --memory --html --outfile scalene-report.html dictation.py
```

Na afsluiten: open `scalene-report.html`. Focus op regels in `opnamesessie.py`,
`dictation.py`, `indicator/`, niet op site-packages tenzij Whisper zelf piekt.

Scalene voegt overhead toe; gebruik het voor gerichte sessies, niet als
dagelijkse start.

## Aanbevolen volgorde

1. Een paar dicteercycli → `cycle.timing` in de log → **welke fase**.
2. `py-spy record` tijdens dezelfde workflow → **welke functies**.
3. Alleen bij geheugen-/allocatievragen: Scalene.

Optimaliseer pas wat beide metingen aanwijzen (vaak modelgrootte / compute type,
incrementele transcriptie, of paste-delay).

## Niet in requirements

`py-spy` en `scalene` horen niet in `requirements-dev.txt` (platform/native
binaries, optioneel). Installeer lokaal wanneer je profileert.
