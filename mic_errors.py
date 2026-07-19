"""
Gebruikersvriendelijke microfoonfouten voor praatMaar.

PortAudio/sounddevice-fouten zijn kort en technisch. Deze module zet ze om
naar een duidelijke uitleg + checklist, geschikt voor een dialoog of log.

Ook: PortAudio-herenumeratie na hotplug (Bluetooth) en keuze van een
concreet input-apparaat als de Windows-default (`-1`) ontbreekt.
"""

from __future__ import annotations

import sys
from typing import Any

import i18n


def classify_mic_error(exc: BaseException) -> str:
    """Kiest een i18n-reden-key op basis van de exception-tekst."""

    text = f"{type(exc).__name__} {exc}".lower()
    if any(
        needle in text
        for needle in (
            "no default input",
            "no input device",
            "device unavailable",
            "host error",
        )
    ):
        return "rec.mic_none"
    # Default-index -1: vaak stale na Bluetooth aan/uit, niet per se "geen mic".
    if "querying device -1" in text or "error querying device" in text:
        return "rec.mic_default_unavailable"
    if "invalid device" in text or "-9996" in text:
        return "rec.mic_invalid"
    if any(needle in text for needle in ("permission", "access denied", "not authorized")):
        return "rec.mic_permission"
    if "no device" in text:
        return "rec.mic_none"
    return "rec.mic_generic"


def format_recording_start_error(exc: BaseException) -> str:
    """Volledige gebruikersboodschap: intro, reden, checklist, technische detail."""

    privacy_key = "rec.check_privacy_win" if sys.platform == "win32" else "rec.check_privacy_mac"
    parts = [
        i18n.t("rec.start_failed_intro"),
        "",
        i18n.t(classify_mic_error(exc)),
        "",
        i18n.t("rec.check_header"),
        i18n.t(privacy_key),
        i18n.t("rec.check_default"),
        i18n.t("rec.check_settings"),
        i18n.t("rec.check_cable"),
        i18n.t("rec.check_restart"),
        "",
        i18n.t("rec.error_detail", error=exc),
    ]
    return "\n".join(parts)


def has_input_device(sounddevice_mod: Any) -> bool:
    """True als er minstens één apparaat met invoerkanalen is."""

    return first_input_device_index(sounddevice_mod) is not None


def first_input_device_index(sounddevice_mod: Any) -> int | None:
    """Eerste PortAudio-index met minstens één invoerkanaal, of None."""

    try:
        devices = sounddevice_mod.query_devices()
    except Exception:
        return None
    for index, device in enumerate(devices):
        try:
            if int(device.get("max_input_channels", 0) or 0) > 0:
                return index
        except (TypeError, ValueError):
            continue
    return None


def refresh_portaudio(sounddevice_mod: Any) -> None:
    """
    Herstart PortAudio zodat hotplug (Bluetooth) zichtbaar wordt.

    Alleen aanroepen als er geen actieve InputStream is.
    """

    try:
        while int(getattr(sounddevice_mod, "_initialized", 0) or 0) > 0:
            sounddevice_mod._terminate()
        sounddevice_mod._initialize()
    except Exception:
        # Best-effort: bij falen blijft de oude device-lijst bruikbaar.
        pass
