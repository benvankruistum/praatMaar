"""Windows output devices for WASAPI loopback capture."""

from __future__ import annotations

import sys
from typing import Any

import i18n


def list_loopback_output_devices(
    sounddevice_module: Any | None = None,
) -> list[tuple[str, int | None]]:
    """Return ``(label, portaudio_index)`` pairs; ``None`` = Windows default output."""

    default_label = i18n.t("modules.meeting_buddy.settings.loopback_default")
    if sys.platform != "win32":
        return [(default_label, None)]

    try:
        if sounddevice_module is None:
            import sounddevice as sounddevice_module
        if not hasattr(sounddevice_module, "WasapiSettings"):
            return [(default_label, None)]
        options: list[tuple[str, int | None]] = [(default_label, None)]
        for index, device in enumerate(sounddevice_module.query_devices()):
            if int(device.get("max_output_channels", 0) or 0) > 0:
                options.append((f"{index}: {device['name']}", index))
        return options
    except Exception:
        return [(default_label, None)]
