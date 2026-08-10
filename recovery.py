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

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import config_dir

# Hoeveel transcripts we maximaal bewaren. Oudere worden opgeruimd.
MAX_TRANSCRIPTS = 50

# Hoeveel recente transcripts in het tray/pill-menu.
RECENT_TRANSCRIPT_LIMIT = 5

# Stem van `save_transcript`: `YYYY-MM-DD_HHMMSS` of `…_N` bij botsing.
_TIMESTAMP_STEM_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{6})(?:_(\d+))?$")


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


def append_transcript(text: str, path: Path) -> Path:
    """Voegt transcript toe aan een bestaand bestand, voorafgegaan door datum/tijd."""

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = f"{stamp}\n\n{text.strip()}\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "\n\n" if path.exists() and path.stat().st_size > 0 else ""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{prefix}{block}")
    return path


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


@dataclass(frozen=True)
class RecentTranscript:
    """Één discrete timestamp-transcript voor het tray-menu."""

    path: Path
    recorded_at: datetime
    collision_index: int | None
    mtime: float


def parse_transcript_stem(stem: str) -> tuple[datetime, int | None] | None:
    """Parse `YYYY-MM-DD_HHMMSS` / `…_N`; anders ``None``."""

    match = _TIMESTAMP_STEM_RE.match(stem)
    if match is None:
        return None
    recorded_at = datetime.strptime(f"{match.group(1)}_{match.group(2)}", "%Y-%m-%d_%H%M%S")
    collision = int(match.group(3)) if match.group(3) is not None else None
    return recorded_at, collision


def format_recent_transcript_label(item: RecentTranscript, ui_language: str = "en") -> str:
    """Datum/tijd-label voor het menu (geen transcripttekst)."""

    recorded = item.recorded_at
    if ui_language == "nl":
        text = recorded.strftime("%d-%m-%Y %H:%M:%S")
    elif ui_language == "de":
        text = recorded.strftime("%d.%m.%Y %H:%M:%S")
    else:
        text = recorded.strftime("%Y-%m-%d %H:%M:%S")
    if item.collision_index is not None:
        text = f"{text} (#{item.collision_index})"
    return text


def list_recent_transcripts(
    directories: list[Path],
    *,
    limit: int = RECENT_TRANSCRIPT_LIMIT,
) -> list[RecentTranscript]:
    """
    Nieuwste discrete timestamp-``.txt``-bestanden over de gegeven mappen.

    Slaat ontoegankelijke mappen en niet-passende namen over. Geen recursie.
    """

    if limit <= 0:
        return []

    found: list[RecentTranscript] = []
    for directory in directories:
        try:
            if not directory.is_dir():
                continue
            files = [path for path in directory.glob("*.txt") if path.is_file()]
        except OSError:
            continue
        for path in files:
            parsed = parse_transcript_stem(path.stem)
            if parsed is None:
                continue
            recorded_at, collision_index = parsed
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            found.append(
                RecentTranscript(
                    path=path,
                    recorded_at=recorded_at,
                    collision_index=collision_index,
                    mtime=mtime,
                )
            )

    found.sort(key=lambda item: (item.mtime, item.path.name), reverse=True)
    return found[:limit]


def read_transcript_text(path: Path) -> str:
    """Leest een transcriptbestand als UTF-8-tekst."""

    return Path(path).read_text(encoding="utf-8")
