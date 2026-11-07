"""Start een systeemspeler en keer meteen terug. Een mislukking blijft stil."""

from __future__ import annotations

import subprocess


def play_command(command: list[str] | None) -> None:
    """Speelt ``command`` af zonder te wachten en zonder fouten naar buiten."""

    if not command:
        return
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return
