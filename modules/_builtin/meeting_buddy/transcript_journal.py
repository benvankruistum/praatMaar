"""Streaming Markdown transcript journal for Meeting Buddy sessions."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from modules.settings_store import module_dir

from .state import Topic
from .topic_ladder import is_journal_checked

log = logging.getLogger(__name__)

_MODULE_ID = "meeting-buddy"
_TRANSCRIPT_MARKER = "## Transcript\n"
_AGENDA_MARKER = "## Agenda\n"


def transcripts_dir(app_dir: Path, *, override: str | Path | None = None) -> Path:
    """Default or user-configured directory for meeting transcript ``.md`` files."""

    if override is not None:
        text = str(override).strip()
        if text:
            return Path(text).expanduser()
    return module_dir(app_dir, _MODULE_ID) / "transcripts"


def safe_stem(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]', "", title).strip().rstrip(".")
    cleaned = re.sub(r"\s+", "-", cleaned)
    return (cleaned[:60] or "meeting").strip("-") or "meeting"


def _format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _format_filename_stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d_%H%M")


def _agenda_lines(titles: Sequence[str], *, checked: set[str] | None = None) -> str:
    done = checked or set()
    if not titles:
        return ""
    lines = []
    for title in titles:
        mark = "x" if title in done else " "
        lines.append(f"- [{mark}] {title}")
    return "\n".join(lines) + "\n"


def _build_initial_markdown(
    *,
    title: str,
    agenda_titles: Sequence[str],
    started_at: datetime,
) -> str:
    agenda = _agenda_lines(agenda_titles)
    return (
        f"# {title}\n"
        f"\n"
        f"- Gestart: {_format_dt(started_at)}\n"
        f"- Status: lopend\n"
        f"\n"
        f"{_AGENDA_MARKER}"
        f"\n"
        f"{agenda}"
        f"\n"
        f"{_TRANSCRIPT_MARKER}"
    )


@dataclass
class TranscriptJournal:
    path: Path
    _agenda_titles: tuple[str, ...] = field(default_factory=tuple)
    _wrote_transcript: bool = False

    @classmethod
    def create(
        cls,
        app_dir: Path,
        *,
        title: str,
        agenda_titles: Sequence[str],
        started_at: datetime | None = None,
        directory: Path | None = None,
    ) -> TranscriptJournal:
        started = started_at or datetime.now()
        display = title.strip() or "Meeting"
        target_dir = directory if directory is not None else transcripts_dir(app_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{_format_filename_stamp(started)}_{safe_stem(display)}.md"
        path = target_dir / filename
        path.write_text(
            _build_initial_markdown(
                title=display,
                agenda_titles=agenda_titles,
                started_at=started,
            ),
            encoding="utf-8",
        )
        return cls(path=path, _agenda_titles=tuple(agenda_titles))

    def append_final(self, text: str) -> None:
        chunk = text.strip()
        if not chunk:
            return
        try:
            with self.path.open("a", encoding="utf-8", newline="") as handle:
                if self._wrote_transcript:
                    handle.write(" ")
                handle.write(chunk)
                handle.flush()
                try:
                    import os

                    os.fsync(handle.fileno())
                except OSError:
                    pass
            self._wrote_transcript = True
        except OSError as exc:
            log.warning("Meeting transcript append failed path=%s error=%s", self.path, exc)

    def finalize(
        self,
        *,
        topics: Sequence[Topic] | None,
        ended_at: datetime | None = None,
    ) -> Path:
        ended = ended_at or datetime.now()
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("Meeting transcript finalize read failed path=%s error=%s", self.path, exc)
            return self.path

        checked: set[str] = set()
        titles = list(self._agenda_titles)
        if topics:
            titles = [topic.title for topic in topics] or titles
            checked = {topic.title for topic in topics if is_journal_checked(topic.status)}

        # Replace status line and inject Gestopt after Gestart if missing.
        lines = raw.splitlines(keepends=True)
        out: list[str] = []
        saw_gestopt = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("- Status:"):
                out.append("- Status: gestopt\n")
                i += 1
                continue
            if line.startswith("- Gestopt:"):
                saw_gestopt = True
            if line.startswith("- Gestart:") and not saw_gestopt:
                out.append(line)
                # Peek: insert Gestopt after Gestart block lines handled next loop
                out.append(f"- Gestopt: {_format_dt(ended)}\n")
                saw_gestopt = True
                i += 1
                continue
            if line == _AGENDA_MARKER or line.rstrip("\n") == "## Agenda":
                out.append(_AGENDA_MARKER if line.endswith("\n") else "## Agenda\n")
                i += 1
                # Skip blank + old checklist until next ## heading
                while i < len(lines) and lines[i].startswith("\n"):
                    out.append(lines[i])
                    i += 1
                    break
                while i < len(lines) and (lines[i].startswith("- [") or lines[i].strip() == ""):
                    if lines[i].startswith("##"):
                        break
                    if lines[i].startswith("- ["):
                        i += 1
                        continue
                    # blank line after agenda items: keep one then stop skipping
                    if lines[i].strip() == "":
                        i += 1
                        break
                    i += 1
                agenda_body = _agenda_lines(titles, checked=checked)
                if agenda_body:
                    out.append(agenda_body)
                if i < len(lines) and lines[i].strip() == "":
                    pass
                elif agenda_body and (i >= len(lines) or not lines[i].startswith("##")):
                    out.append("\n")
                continue
            out.append(line)
            i += 1

        text = "".join(out)
        if not saw_gestopt:
            text = text.replace(
                "- Status: gestopt\n",
                f"- Status: gestopt\n- Gestopt: {_format_dt(ended)}\n",
                1,
            )

        try:
            self.path.write_text(text, encoding="utf-8")
        except OSError as exc:
            log.warning("Meeting transcript finalize write failed path=%s error=%s", self.path, exc)
        return self.path
