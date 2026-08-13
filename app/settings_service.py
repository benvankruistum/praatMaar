"""Settings snapshot / apply / save (ADR-0006 mic lazy rebind behouden)."""

from __future__ import annotations

from typing import Any

import config
import destinations
import host
import hotkeys
import i18n
from chunk_transcription import normalize_chunk_mode
from indicator import RecordingIndicator
from modules import modules_config_for_settings, sanitize_modules_config


def user_config_dict(state: Any) -> dict[str, Any]:
    """Snapshot van alle persistente gebruikersinstellingen."""

    xy = getattr(state, "INDICATOR_XY", None)
    if xy is None:
        xy = getattr(state, "indicator_xy", None)
    return {
        "model": _get(state, "MODEL_NAME", "model_name"),
        "microphone_device": _get(state, "MICROPHONE_DEVICE", "microphone_device"),
        "auto_paste": _get(state, "AUTO_PASTE", "auto_paste"),
        "warm_microphone": _get(state, "WARM_MICROPHONE", "warm_microphone"),
        "whisper_beam_size": _get(state, "WHISPER_BEAM_SIZE", "whisper_beam_size"),
        "whisper_vad_filter": _get(state, "WHISPER_VAD_FILTER", "whisper_vad_filter"),
        "whisper_vad_min_silence_ms": _get(
            state, "WHISPER_VAD_MIN_SILENCE_MS", "whisper_vad_min_silence_ms"
        ),
        "whisper_condition_on_previous_text": _get(
            state,
            "WHISPER_CONDITION_ON_PREVIOUS_TEXT",
            "whisper_condition_on_previous_text",
        ),
        "whisper_no_speech_threshold": _get(
            state, "WHISPER_NO_SPEECH_THRESHOLD", "whisper_no_speech_threshold"
        ),
        "whisper_initial_prompt": _get(state, "WHISPER_INITIAL_PROMPT", "whisper_initial_prompt"),
        "whisper_hotwords": _get(state, "WHISPER_HOTWORDS", "whisper_hotwords"),
        "indicator_position": _get(state, "INDICATOR_POSITION", "indicator_position"),
        "indicator_xy": list(xy) if xy is not None else None,
        "mode": _get(state, "MODE", "mode"),
        "hotkey": hotkeys.normalize(_get(state, "HOTKEY_TOKENS", "hotkey_tokens")),
        "speech_language": _get(state, "LANGUAGE", "language"),
        "ui_language": i18n.ui_language(),
        "destinations": _get(state, "DESTINATIONS", "destinations"),
        "active_destination": _get(state, "ACTIVE_DESTINATION", "active_destination"),
        "incremental_transcription": _get(
            state, "INCREMENTAL_TRANSCRIPTION", "incremental_transcription"
        ),
        "incremental_chunk_mode": _get(state, "INCREMENTAL_CHUNK_MODE", "incremental_chunk_mode"),
        "incremental_vad_ms": _get(state, "INCREMENTAL_VAD_MS", "incremental_vad_ms"),
        "incremental_chunk_seconds": _get(
            state, "INCREMENTAL_CHUNK_SECONDS", "incremental_chunk_seconds"
        ),
        "modules": modules_config_for_settings(_get(state, "MODULES_CONFIG", "modules_config")),
    }


def current_settings(state: Any) -> dict[str, Any]:
    """Huidige waarden voor het instellingen-dialoog."""

    data = user_config_dict(state)
    data["autostart"] = host.is_autostart_enabled()
    data["destinations"] = list(data["destinations"])
    return data


def active_destination_path(state: Any) -> str | None:
    active = _get(state, "ACTIVE_DESTINATION", "active_destination")
    dests = _get(state, "DESTINATIONS", "destinations")
    item = destinations.find_destination(active, dests)
    if item is None:
        return None
    path = str(item.get("path") or "").strip()
    return path or None


def apply_settings(
    state: Any,
    new_settings: dict[str, Any],
    indicator: RecordingIndicator,
    *,
    session: Any,
    reload_modules: Any | None = None,
    refresh_mic_attention: Any | None = None,
    tray: Any | None = None,
) -> None:
    """Bewaart en past gewijzigde instellingen toe (ADR-0006 lazy rebind)."""

    from indicator._contract import (
        POSITION_LAST,
        normalize_indicator_position,
        sanitize_indicator_xy,
    )

    model_name = _get(state, "MODEL_NAME", "model_name")
    indicator_position = _get(state, "INDICATOR_POSITION", "indicator_position")
    indicator_xy = _get(state, "INDICATOR_XY", "indicator_xy")
    microphone_device = _get(state, "MICROPHONE_DEVICE", "microphone_device")
    auto_paste = _get(state, "AUTO_PASTE", "auto_paste")
    warm_microphone = _get(state, "WARM_MICROPHONE", "warm_microphone")
    mode = _get(state, "MODE", "mode")
    language = _get(state, "LANGUAGE", "language")
    destinations_list = _get(state, "DESTINATIONS", "destinations")
    active_destination = _get(state, "ACTIVE_DESTINATION", "active_destination")
    incremental_transcription = _get(
        state, "INCREMENTAL_TRANSCRIPTION", "incremental_transcription"
    )
    incremental_chunk_mode = _get(state, "INCREMENTAL_CHUNK_MODE", "incremental_chunk_mode")
    incremental_vad_ms = _get(state, "INCREMENTAL_VAD_MS", "incremental_vad_ms")
    incremental_chunk_seconds = _get(
        state, "INCREMENTAL_CHUNK_SECONDS", "incremental_chunk_seconds"
    )
    modules_config = _get(state, "MODULES_CONFIG", "modules_config")
    hotkey_tokens = _get(state, "HOTKEY_TOKENS", "hotkey_tokens")
    whisper_beam_size = _get(state, "WHISPER_BEAM_SIZE", "whisper_beam_size")
    whisper_vad_filter = _get(state, "WHISPER_VAD_FILTER", "whisper_vad_filter")
    whisper_vad_min_silence_ms = _get(
        state, "WHISPER_VAD_MIN_SILENCE_MS", "whisper_vad_min_silence_ms"
    )
    whisper_condition_on_previous_text = _get(
        state, "WHISPER_CONDITION_ON_PREVIOUS_TEXT", "whisper_condition_on_previous_text"
    )
    whisper_no_speech_threshold = _get(
        state, "WHISPER_NO_SPEECH_THRESHOLD", "whisper_no_speech_threshold"
    )
    whisper_initial_prompt = _get(state, "WHISPER_INITIAL_PROMPT", "whisper_initial_prompt")
    whisper_hotwords = _get(state, "WHISPER_HOTWORDS", "whisper_hotwords")

    new_model = str(new_settings.get("model", model_name))
    model_changed = new_model != model_name
    new_position = normalize_indicator_position(
        new_settings.get("indicator_position", indicator_position)
    )
    new_xy = sanitize_indicator_xy(new_settings.get("indicator_xy", indicator_xy))
    if new_position == POSITION_LAST and new_xy is None:
        new_xy = indicator_xy
    if new_position == POSITION_LAST and new_xy is None:
        new_position = "boven-midden"
    position_changed = new_position != indicator_position or new_xy != indicator_xy

    model_name = new_model
    microphone_device = new_settings.get("microphone_device", microphone_device)
    auto_paste = bool(new_settings.get("auto_paste", auto_paste))
    warm_microphone = bool(new_settings.get("warm_microphone", warm_microphone))
    _whisper = config.whisper_settings_from_config(
        {
            "whisper_beam_size": new_settings.get("whisper_beam_size", whisper_beam_size),
            "whisper_vad_filter": new_settings.get("whisper_vad_filter", whisper_vad_filter),
            "whisper_vad_min_silence_ms": new_settings.get(
                "whisper_vad_min_silence_ms", whisper_vad_min_silence_ms
            ),
            "whisper_condition_on_previous_text": new_settings.get(
                "whisper_condition_on_previous_text", whisper_condition_on_previous_text
            ),
            "whisper_no_speech_threshold": new_settings.get(
                "whisper_no_speech_threshold", whisper_no_speech_threshold
            ),
            "whisper_initial_prompt": new_settings.get(
                "whisper_initial_prompt", whisper_initial_prompt
            ),
            "whisper_hotwords": new_settings.get("whisper_hotwords", whisper_hotwords),
        }
    )
    whisper_beam_size = _whisper["whisper_beam_size"]
    whisper_vad_filter = _whisper["whisper_vad_filter"]
    whisper_vad_min_silence_ms = _whisper["whisper_vad_min_silence_ms"]
    whisper_condition_on_previous_text = _whisper["whisper_condition_on_previous_text"]
    whisper_no_speech_threshold = _whisper["whisper_no_speech_threshold"]
    whisper_initial_prompt = _whisper["whisper_initial_prompt"]
    whisper_hotwords = _whisper["whisper_hotwords"]
    indicator_position = new_position
    indicator_xy = new_xy

    if new_settings.get("mode") in ("toggle", "ptt"):
        mode = str(new_settings["mode"])

    new_hotkey = new_settings.get("hotkey")
    if isinstance(new_hotkey, list) and new_hotkey:
        hotkey_tokens = {str(token) for token in new_hotkey}

    language = i18n.normalize_language(
        new_settings.get("speech_language", language),
        allowed=i18n.SUPPORTED_SPEECH_LANGUAGES,
    )
    i18n.set_ui_language(
        i18n.normalize_language(
            new_settings.get("ui_language"),
            allowed=i18n.SUPPORTED_UI_LANGUAGES,
        )
    )

    if "destinations" in new_settings:
        destinations_list = destinations.sanitize_destinations(new_settings["destinations"])
        if "active_destination" not in new_settings and active_destination is not None:
            if not any(d["name"] == active_destination for d in destinations_list):
                active_destination = None
    if "active_destination" in new_settings:
        raw_active = new_settings["active_destination"]
        if raw_active is None:
            active_destination = None
        else:
            candidate = str(raw_active).strip() or None
            if candidate and any(d["name"] == candidate for d in destinations_list):
                active_destination = candidate
            else:
                active_destination = None

    if "incremental_transcription" in new_settings:
        incremental_transcription = bool(new_settings["incremental_transcription"])
    if "incremental_chunk_mode" in new_settings:
        incremental_chunk_mode = normalize_chunk_mode(new_settings["incremental_chunk_mode"])
    if "incremental_vad_ms" in new_settings:
        try:
            incremental_vad_ms = max(0, int(new_settings["incremental_vad_ms"]))
        except (TypeError, ValueError):
            pass
    if "incremental_chunk_seconds" in new_settings:
        try:
            value = float(new_settings["incremental_chunk_seconds"])
            if value > 0:
                incremental_chunk_seconds = value
        except (TypeError, ValueError):
            pass
    modules_changed = False
    if "modules" in new_settings:
        modules_config = sanitize_modules_config(new_settings["modules"])
        modules_changed = True

    _set(state, "MODEL_NAME", "model_name", model_name)
    _set(state, "MICROPHONE_DEVICE", "microphone_device", microphone_device)
    _set(state, "AUTO_PASTE", "auto_paste", auto_paste)
    _set(state, "WARM_MICROPHONE", "warm_microphone", warm_microphone)
    _set(state, "WHISPER_BEAM_SIZE", "whisper_beam_size", whisper_beam_size)
    _set(state, "WHISPER_VAD_FILTER", "whisper_vad_filter", whisper_vad_filter)
    _set(
        state,
        "WHISPER_VAD_MIN_SILENCE_MS",
        "whisper_vad_min_silence_ms",
        whisper_vad_min_silence_ms,
    )
    _set(
        state,
        "WHISPER_CONDITION_ON_PREVIOUS_TEXT",
        "whisper_condition_on_previous_text",
        whisper_condition_on_previous_text,
    )
    _set(
        state,
        "WHISPER_NO_SPEECH_THRESHOLD",
        "whisper_no_speech_threshold",
        whisper_no_speech_threshold,
    )
    _set(state, "WHISPER_INITIAL_PROMPT", "whisper_initial_prompt", whisper_initial_prompt)
    _set(state, "WHISPER_HOTWORDS", "whisper_hotwords", whisper_hotwords)
    _set(state, "INDICATOR_POSITION", "indicator_position", indicator_position)
    _set(state, "INDICATOR_XY", "indicator_xy", indicator_xy)
    _set(state, "MODE", "mode", mode)
    _set(state, "HOTKEY_TOKENS", "hotkey_tokens", hotkey_tokens)
    _set(state, "LANGUAGE", "language", language)
    _set(state, "DESTINATIONS", "destinations", destinations_list)
    _set(state, "ACTIVE_DESTINATION", "active_destination", active_destination)
    _set(state, "INCREMENTAL_TRANSCRIPTION", "incremental_transcription", incremental_transcription)
    _set(state, "INCREMENTAL_CHUNK_MODE", "incremental_chunk_mode", incremental_chunk_mode)
    _set(state, "INCREMENTAL_VAD_MS", "incremental_vad_ms", incremental_vad_ms)
    _set(state, "INCREMENTAL_CHUNK_SECONDS", "incremental_chunk_seconds", incremental_chunk_seconds)
    _set(state, "MODULES_CONFIG", "modules_config", modules_config)

    if modules_changed and reload_modules is not None:
        reload_modules()

    old_mic = session.microphone_device
    old_warm = session.warm_microphone
    session.microphone_device = microphone_device
    session.auto_paste = auto_paste
    session.mode = mode
    session.language = language
    session.warm_microphone = warm_microphone
    session.whisper_beam_size = whisper_beam_size
    session.whisper_vad_filter = whisper_vad_filter
    session.whisper_vad_min_silence_ms = whisper_vad_min_silence_ms
    session.whisper_condition_on_previous_text = whisper_condition_on_previous_text
    session.whisper_no_speech_threshold = whisper_no_speech_threshold
    session.whisper_initial_prompt = whisper_initial_prompt
    session.whisper_hotwords = whisper_hotwords
    session.incremental_transcription = incremental_transcription
    session.incremental_chunk_mode = incremental_chunk_mode
    session.incremental_vad_ms = incremental_vad_ms
    session._incremental_chunk_seconds = incremental_chunk_seconds
    if old_mic != microphone_device:
        session.refresh_input_device()
    elif old_warm and not warm_microphone:
        session.stop_audio_stream()
    elif (not old_warm) and warm_microphone:
        session.warmup_microphone()

    if refresh_mic_attention is not None:
        refresh_mic_attention()

    config.save_config(user_config_dict(state))

    if "autostart" in new_settings:
        host.set_autostart(bool(new_settings["autostart"]))

    if position_changed:
        indicator.set_position(new_position, xy=indicator_xy)

    indicator.set_destination(active_destination, active_destination_path(state))

    tray_ref = tray if tray is not None else getattr(state, "_tray", None)
    if tray_ref is not None:
        tray_ref.refresh_language()

    print()
    print(i18n.t("settings.saved"))
    if model_changed:
        print(i18n.t("settings.model_restart_note"))


def _get(state: Any, upper: str, lower: str) -> Any:
    if hasattr(state, upper):
        return getattr(state, upper)
    return getattr(state, lower)


def _set(state: Any, upper: str, lower: str, value: Any) -> None:
    if hasattr(state, upper):
        setattr(state, upper, value)
    if hasattr(state, lower):
        setattr(state, lower, value)
