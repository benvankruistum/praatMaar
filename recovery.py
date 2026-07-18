"""
Herstel-opslag voor praatMaar.

Beschermt tegen dataverlies bij een lange dicteersessie: het transcript wordt
altijd naar schijf weggeschreven (voor klembord en plakken), en bij een
mislukte transcriptie wordt de opgenomen audio bewaard i.p.v. verwijderd, zodat
later opnieuw getranscribeerd kan worden.

Alles onder `%APPDATA%\\praatMaar\\`:
- `transcripts\\` : elk geslaagd transcript, met retentie (nieuwste N).
- `recovery\\`    : audio van mislukte transcripties (niet automatisch opgeschoond).

Bewust puur stdlib, net als `config.py`: geen extra dependency voor deze laag.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from config import config_dir

# Hoeveel transcripts we maximaal bewaren. Oudere worden opgeruimd.
MAX_TRANSCRIPTS = 50


def transcripts_dir() -> Path:
    """Map met bewaarde transcripts (`%APPDATA%\\praatMaar\\transcripts\\`)."""

    return config_dir() / "transcripts"


def recovery_dir() -> Path:
    """Map met audio van mislukte transcripties (`...\\recovery\\`)."""

    return config_dir() / "recovery"


def _timestamp() -> str:
    """Sorteerbare tijdstempel voor bestandsnamen, bijv. `2026-07-15_143005`."""

    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """
    Geeft een nog niet bestaand pad terug. Bij een botsing binnen dezelfde
    seconde wordt een teller toegevoegd (`..._2`, `..._3`, ...).
    """

    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def save_transcript(text: str) -> Path:
    """
    Schrijft het transcript atomisch weg (tmp-bestand + replace) en ruimt
    daarna oude transcripts op. Geeft het pad van het bewaarde bestand terug.
    """

    directory = transcripts_dir()
    directory.mkdir(parents=True, exist_ok=True)

    target = _unique_path(directory, _timestamp(), ".txt")
    tmp = target.with_name(target.name + ".tmp")

    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)

    tmp.replace(target)

    prune_transcripts()

    return target


def prune_transcripts(max_files: int | None = None) -> None:
    """Houdt alleen de nieuwste `max_files` transcripts; verwijdert de rest."""

    if max_files is None:
        max_files = MAX_TRANSCRIPTS

    directory = transcripts_dir()

    try:
        files = [path for path in directory.glob("*.txt") if path.is_file()]
    except OSError:
        return

    if len(files) <= max_files:
        return

    files.sort(key=lambda path: path.stat().st_mtime)

    for path in files[:-max_files]:
        try:
            path.unlink()
        except OSError:
            # Opruimen is best-effort; een enkel achtergebleven bestand
            # mag de werking niet blokkeren.
            pass


def preserve_audio(wav_path: Path) -> Path:
    """
    Verplaatst de opgenomen WAV naar de recovery-map, zodat de audio na een
    mislukte transcriptie niet verloren gaat. Geeft het nieuwe pad terug.
    """

    directory = recovery_dir()
    directory.mkdir(parents=True, exist_ok=True)

    target = _unique_path(directory, _timestamp(), ".wav")

    # shutil.move i.p.v. os.replace: de tijdelijke map kan op een andere schijf
    # staan dan %APPDATA%, en dan werkt een simpele rename niet.
    shutil.move(str(wav_path), str(target))

    return target
