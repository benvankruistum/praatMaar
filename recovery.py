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


def save_transcript(text: str, directory: Path | None = None) -> Path:
    """
    Schrijft het transcript atomisch weg (tmp-bestand + replace) en ruimt
    daarna oude transcripts op in de standaardmap. Geeft het pad van het
    bewaarde bestand terug.

    Bij een custom `directory` wordt alleen daar weggeschreven; prune draait
    dan niet (alleen voor de default `%APPDATA%\\praatMaar\\transcripts\\`).
    """

    default = transcripts_dir()
    target_dir = directory if directory is not None else default
    target_dir.mkdir(parents=True, exist_ok=True)

    target = _unique_path(target_dir, _timestamp(), ".txt")
    tmp = target.with_name(target.name + ".tmp")

    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)

    tmp.replace(target)

    if target_dir.resolve() == default.resolve():
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


def list_recovery_wavs() -> list[Path]:
    """WAV’s in de recovery-map, nieuwste eerst. Ontbrekende map → []."""

    directory = recovery_dir()
    if not directory.is_dir():
        return []
    try:
        files = [path for path in directory.glob("*.wav") if path.is_file()]
    except OSError:
        return []
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files


def delete_recovery_file(path: Path) -> None:
    """
    Verwijdert één recovery-WAV. Weigert paden buiten `recovery_dir()`.
    """

    directory = recovery_dir().resolve()
    resolved = path.resolve()
    if resolved.parent != directory or resolved.suffix.lower() != ".wav":
        raise ValueError(f"Geen recovery-bestand: {path}")
    resolved.unlink()


def delete_all_recovery_files() -> int:
    """Verwijdert alle recovery-WAV’s. Geeft het aantal verwijderde bestanden."""

    removed = 0
    for path in list_recovery_wavs():
        try:
            delete_recovery_file(path)
            removed += 1
        except OSError:
            pass
    return removed


def format_size(num_bytes: int) -> str:
    """Menselijke bestandsgrootte voor UI-labels."""

    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def recovery_list_label(path: Path) -> str:
    """Weergavetekst: bestandsnaam + grootte."""

    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return f"{path.name}  ({format_size(size)})"
