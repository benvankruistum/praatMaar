"""
Instellingen-persistentie voor praatMaar.

Door de gebruiker gewijzigde instellingen worden als `config.json` bewaard in
`%APPDATA%\\praatMaar\\`. De INSTELLINGEN-constanten in `dictation.py`
blijven de defaults; deze config overschrijft ze bij het opstarten.

Bewust puur stdlib (`json`): geen extra dependency voor de configlaag. De
OS-conforme datamap komt van de platform-seam (`host.app_dir()`); deze module
weet dus niet meer van `%APPDATA%` af.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import host

# Saves kunnen van meerdere threads komen (main-thread bij instellingen/pill
# slepen; transcriptie-thread bij stembestemmingscommando's). Eén tmp-pad +
# replace is alleen atomisch als er niet parallel geschreven wordt.
_save_lock = threading.Lock()


KNOWN_MODELS = ("base", "small", "medium")
DEFAULT_MODEL = "small"

# Named snelheid/kwaliteit-presets (Instellingen → Geavanceerd). Alleen model +
# veilige beam/VAD-defaults; geen GPU/device, geen prompt/hotwords.
DICTATION_PRESET_IDS = ("fast", "balanced", "accurate")
DICTATION_PRESETS: dict[str, dict[str, Any]] = {
    "fast": {
        "model": "base",
        "whisper_beam_size": 1,
        "whisper_vad_filter": True,
        "whisper_vad_min_silence_ms": 300,
    },
    "balanced": {
        "model": "small",
        "whisper_beam_size": 5,
        "whisper_vad_filter": True,
        "whisper_vad_min_silence_ms": 300,
    },
    "accurate": {
        "model": "medium",
        "whisper_beam_size": 5,
        "whisper_vad_filter": True,
        "whisper_vad_min_silence_ms": 300,
    },
}

# Faster-Whisper transcribe-defaults (gelijk aan eerdere hardcodes in Opnamesessie).
DEFAULT_WHISPER_BEAM_SIZE = 5
DEFAULT_WHISPER_VAD_FILTER = True
DEFAULT_WHISPER_VAD_MIN_SILENCE_MS = 300
DEFAULT_WHISPER_CONDITION_ON_PREVIOUS_TEXT = False
DEFAULT_WHISPER_NO_SPEECH_THRESHOLD = 0.6
DEFAULT_WHISPER_INITIAL_PROMPT = ""
DEFAULT_WHISPER_HOTWORDS = ""

_WHISPER_BEAM_MIN = 1
_WHISPER_BEAM_MAX = 10
_WHISPER_SILENCE_MIN_MS = 100
_WHISPER_SILENCE_MAX_MS = 5000
_WHISPER_PROMPT_MAX_CHARS = 2000
_WHISPER_HOTWORDS_MAX_CHARS = 500


def normalize_model_name(value: Any) -> str:
    """Valideert de modelnaam uit config; onbekend → ``DEFAULT_MODEL``.

    Zonder deze check probeerde Faster-Whisper een typefout (``"smal"``) als
    HuggingFace-repo-id te downloaden; de app startte dan niet.
    """

    if value is None:
        return DEFAULT_MODEL
    name = str(value).strip().lower()
    return name if name in KNOWN_MODELS else DEFAULT_MODEL


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _clamp_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(minimum, min(maximum, number))


def normalize_whisper_beam_size(value: Any) -> int:
    return _clamp_int(
        value,
        default=DEFAULT_WHISPER_BEAM_SIZE,
        minimum=_WHISPER_BEAM_MIN,
        maximum=_WHISPER_BEAM_MAX,
    )


def normalize_whisper_vad_min_silence_ms(value: Any) -> int:
    return _clamp_int(
        value,
        default=DEFAULT_WHISPER_VAD_MIN_SILENCE_MS,
        minimum=_WHISPER_SILENCE_MIN_MS,
        maximum=_WHISPER_SILENCE_MAX_MS,
    )


def normalize_whisper_no_speech_threshold(value: Any) -> float:
    return _clamp_float(
        value,
        default=DEFAULT_WHISPER_NO_SPEECH_THRESHOLD,
        minimum=0.0,
        maximum=1.0,
    )


def normalize_whisper_text(
    value: Any, *, default: str = "", max_chars: int = _WHISPER_PROMPT_MAX_CHARS
) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def whisper_settings_from_config(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """Genormaliseerde Whisper-transcribe-instellingen uit config (of defaults)."""

    data = raw if isinstance(raw, dict) else {}
    return {
        "whisper_beam_size": normalize_whisper_beam_size(
            data.get("whisper_beam_size", DEFAULT_WHISPER_BEAM_SIZE)
        ),
        "whisper_vad_filter": bool(data.get("whisper_vad_filter", DEFAULT_WHISPER_VAD_FILTER)),
        "whisper_vad_min_silence_ms": normalize_whisper_vad_min_silence_ms(
            data.get("whisper_vad_min_silence_ms", DEFAULT_WHISPER_VAD_MIN_SILENCE_MS)
        ),
        "whisper_condition_on_previous_text": bool(
            data.get(
                "whisper_condition_on_previous_text",
                DEFAULT_WHISPER_CONDITION_ON_PREVIOUS_TEXT,
            )
        ),
        "whisper_no_speech_threshold": normalize_whisper_no_speech_threshold(
            data.get("whisper_no_speech_threshold", DEFAULT_WHISPER_NO_SPEECH_THRESHOLD)
        ),
        "whisper_initial_prompt": normalize_whisper_text(
            data.get("whisper_initial_prompt", DEFAULT_WHISPER_INITIAL_PROMPT),
            default=DEFAULT_WHISPER_INITIAL_PROMPT,
            max_chars=_WHISPER_PROMPT_MAX_CHARS,
        ),
        "whisper_hotwords": normalize_whisper_text(
            data.get("whisper_hotwords", DEFAULT_WHISPER_HOTWORDS),
            default=DEFAULT_WHISPER_HOTWORDS,
            max_chars=_WHISPER_HOTWORDS_MAX_CHARS,
        ),
    }


def normalize_dictation_preset(value: Any) -> str | None:
    """Geeft een bekende preset-id terug, of ``None`` bij onbekend/leeg."""

    if value is None:
        return None
    name = str(value).strip().lower()
    return name if name in DICTATION_PRESET_IDS else None


def dictation_preset_values(preset_id: str) -> dict[str, Any] | None:
    """Kopie van de presetwaarden, of ``None`` bij onbekende id."""

    normalized = normalize_dictation_preset(preset_id)
    if normalized is None:
        return None
    return dict(DICTATION_PRESETS[normalized])


def match_dictation_preset(settings: dict[str, Any] | None = None) -> str | None:
    """Match model + beam/VAD tegen een named preset; anders ``None`` (aangepast)."""

    data = settings if isinstance(settings, dict) else {}
    model = normalize_model_name(data.get("model", DEFAULT_MODEL))
    whisper = whisper_settings_from_config(data)
    for preset_id, values in DICTATION_PRESETS.items():
        if (
            model == values["model"]
            and whisper["whisper_beam_size"] == values["whisper_beam_size"]
            and bool(whisper["whisper_vad_filter"]) == bool(values["whisper_vad_filter"])
            and whisper["whisper_vad_min_silence_ms"] == values["whisper_vad_min_silence_ms"]
        ):
            return preset_id
    return None


def config_dir() -> Path:
    """De map voor gebruikersinstellingen (OS-conform, via de platform-seam)."""

    return host.app_dir()


def config_path() -> Path:
    return config_dir() / "config.json"


# Standaard submappen onder de app-datamap (documentatie + externe tools).
_APP_DATA_SUBDIRS = ("transcripts", "recovery", "events", "inbox")


def ensure_app_data_dirs() -> Path:
    """
    Maakt de app-datamap en standaard submappen aan.

    Idempotent; veilig bij elke start aan te roepen vóór modules of dicteren
    iets wegschrijven.
    """

    base = config_dir()
    base.mkdir(parents=True, exist_ok=True)
    for name in _APP_DATA_SUBDIRS:
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def load_config() -> dict[str, Any]:
    """Leest de config; geeft een leeg dict terug als die er niet is of stuk is."""

    path = config_path()
    try:
        # utf-8-sig: tolereert een BOM (bijv. na bewerken in Notepad/PowerShell).
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save_config(settings: dict[str, Any]) -> None:
    """Schrijft de config atomisch weg (tmp-bestand + replace)."""

    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)

    target = config_path()
    tmp = target.with_name(target.name + ".tmp")

    with _save_lock:
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, ensure_ascii=False)

        tmp.replace(target)
