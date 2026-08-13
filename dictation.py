"""Thin entry + tijdelijke re-exports (ADR-0007 composition-root strangler)."""

from __future__ import annotations

import signal
import sys
import threading
from pathlib import Path
from typing import Any

import app_logging
import config
import destinations
import host
import hotkeys
import i18n
import recovery
import win_identity
from app.bootstrap import build_runtime, build_session
from app.clipboard import copy_to_clipboard
from app.hotkey_router import HotkeyRouter, default_signal_processing_busy
from app.recent_transcripts import recent_transcript_menu_entries
from app.recovery_actions import retranscribe_recovery_wav as retranscribe_recovery_wav_impl
from app.recovery_actions import save_transcript_routed
from app.settings_service import (
    active_destination_path,
    user_config_dict,
)
from app.settings_service import (
    apply_settings as apply_settings_svc,
)
from app.settings_service import (
    current_settings as current_settings_svc,
)
from chunk_transcription import normalize_chunk_mode
from indicator import RecordingIndicator
from modules import (
    CapabilityRegistry,
    CycleEvent,
    ModuleBus,
    SharedWhisper,
    load_enabled_modules,
    noop_ui_dispatch,
    sanitize_modules_config,
    tray_action_entries,
    tray_root_action_entries,
)
from opnamesessie import Opnamesessie
from splash import Splash
from ui.app import ensure_app

# Intentional re-exports for app.run / monkeypatch targets.
_ = (
    signal,
    app_logging,
    win_identity,
    Splash,
    ensure_app,
    tray_action_entries,
    tray_root_action_entries,
)

# Zware libraries: pas in splash/startup.
np = None  # numpy
sd = None  # sounddevice
pyperclip = None
keyboard = None  # pynput.keyboard
write_wav = None  # scipy.io.wavfile.write
WhisperModel = None  # faster_whisper.WhisperModel
TrayIcon = None  # tray.TrayIcon

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


# =========================================================
# INSTELLINGEN (defaults + user config)
# =========================================================

MODEL_NAME = "small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
LANGUAGE = "nl"
SAMPLE_RATE = 16000
CHANNELS = 1
MICROPHONE_DEVICE: int | None = None
AUTO_PASTE = True
WARM_MICROPHONE = False
WHISPER_BEAM_SIZE = config.DEFAULT_WHISPER_BEAM_SIZE
WHISPER_VAD_FILTER = config.DEFAULT_WHISPER_VAD_FILTER
WHISPER_VAD_MIN_SILENCE_MS = config.DEFAULT_WHISPER_VAD_MIN_SILENCE_MS
WHISPER_CONDITION_ON_PREVIOUS_TEXT = config.DEFAULT_WHISPER_CONDITION_ON_PREVIOUS_TEXT
WHISPER_NO_SPEECH_THRESHOLD = config.DEFAULT_WHISPER_NO_SPEECH_THRESHOLD
WHISPER_INITIAL_PROMPT = config.DEFAULT_WHISPER_INITIAL_PROMPT
WHISPER_HOTWORDS = config.DEFAULT_WHISPER_HOTWORDS
PASTE_DELAY_SECONDS = 0.30
MINIMUM_RECORDING_SECONDS = 0.30
DELETE_TEMP_AUDIO = True
INDICATOR_POSITION = "boven-midden"
INDICATOR_XY: tuple[int, int] | None = None
MODE = "toggle"
HOTKEY_TOKENS: set[str] = set(hotkeys.DEFAULT_HOTKEY)

_user_config = config.load_config()
if "model" in _user_config:
    MODEL_NAME = config.normalize_model_name(_user_config["model"])
if "microphone_device" in _user_config:
    MICROPHONE_DEVICE = _user_config["microphone_device"]
if "auto_paste" in _user_config:
    AUTO_PASTE = bool(_user_config["auto_paste"])
if "warm_microphone" in _user_config:
    WARM_MICROPHONE = bool(_user_config["warm_microphone"])
_whisper_cfg = config.whisper_settings_from_config(_user_config)
WHISPER_BEAM_SIZE = _whisper_cfg["whisper_beam_size"]
WHISPER_VAD_FILTER = _whisper_cfg["whisper_vad_filter"]
WHISPER_VAD_MIN_SILENCE_MS = _whisper_cfg["whisper_vad_min_silence_ms"]
WHISPER_CONDITION_ON_PREVIOUS_TEXT = _whisper_cfg["whisper_condition_on_previous_text"]
WHISPER_NO_SPEECH_THRESHOLD = _whisper_cfg["whisper_no_speech_threshold"]
WHISPER_INITIAL_PROMPT = _whisper_cfg["whisper_initial_prompt"]
WHISPER_HOTWORDS = _whisper_cfg["whisper_hotwords"]
DICTATION_PRESET = config.match_dictation_preset(_user_config)
if "indicator_position" in _user_config:
    from indicator._contract import normalize_indicator_position, sanitize_indicator_xy

    INDICATOR_POSITION = normalize_indicator_position(_user_config["indicator_position"])
    INDICATOR_XY = sanitize_indicator_xy(_user_config.get("indicator_xy"))
    if INDICATOR_POSITION == "laatst-geplaatst" and INDICATOR_XY is None:
        INDICATOR_POSITION = "boven-midden"
if _user_config.get("mode") in ("toggle", "ptt"):
    MODE = str(_user_config["mode"])
if isinstance(_user_config.get("hotkey"), list) and _user_config["hotkey"]:
    HOTKEY_TOKENS = {str(token) for token in _user_config["hotkey"]}
if "speech_language" in _user_config:
    LANGUAGE = i18n.normalize_language(
        _user_config["speech_language"],
        allowed=i18n.SUPPORTED_SPEECH_LANGUAGES,
    )
_ui = i18n.normalize_language(
    _user_config.get("ui_language"),
    allowed=i18n.SUPPORTED_UI_LANGUAGES,
)
i18n.set_ui_language(_ui)

DESTINATIONS = destinations.sanitize_destinations(_user_config.get("destinations"))
_active_raw = _user_config.get("active_destination")
if _active_raw is None:
    ACTIVE_DESTINATION: str | None = None
else:
    _active_name = str(_active_raw).strip() or None
    if _active_name and any(d["name"] == _active_name for d in DESTINATIONS):
        ACTIVE_DESTINATION = _active_name
    else:
        ACTIVE_DESTINATION = None

MODULES_CONFIG = sanitize_modules_config(_user_config.get("modules"))
INCREMENTAL_TRANSCRIPTION = bool(_user_config.get("incremental_transcription", False))
INCREMENTAL_CHUNK_MODE = normalize_chunk_mode(_user_config.get("incremental_chunk_mode", "hybrid"))
try:
    INCREMENTAL_VAD_MS = max(0, int(_user_config.get("incremental_vad_ms", 2000)))
except (TypeError, ValueError):
    INCREMENTAL_VAD_MS = 2000
try:
    INCREMENTAL_CHUNK_SECONDS = float(_user_config.get("incremental_chunk_seconds", 30.0))
except (TypeError, ValueError):
    INCREMENTAL_CHUNK_SECONDS = 30.0
if INCREMENTAL_CHUNK_SECONDS <= 0:
    INCREMENTAL_CHUNK_SECONDS = 30.0

# Bus/registry bij import (compat); modules laden pas in run/_reload_modules.
shared_whisper = SharedWhisper()
capability_registry = CapabilityRegistry()
module_bus = ModuleBus(capabilities=capability_registry)

_ui_dispatch = noop_ui_dispatch
_tray = None
_indicator: RecordingIndicator | None = None
model: Any | None = None

state_lock = threading.RLock()
pressed_tokens: set[str] = set()
toggle_latched = False
capturing = False
_capture_cb: Any | None = None

_runtime = build_runtime(
    host_obj=host.default,
    shared_whisper=shared_whisper,
    capability_registry=capability_registry,
    module_bus=module_bus,
    modules_config=MODULES_CONFIG,
    model_name=MODEL_NAME,
    device=DEVICE,
    compute_type=COMPUTE_TYPE,
    language=LANGUAGE,
    sample_rate=SAMPLE_RATE,
    channels=CHANNELS,
    microphone_device=MICROPHONE_DEVICE,
    auto_paste=AUTO_PASTE,
    warm_microphone=WARM_MICROPHONE,
    whisper_beam_size=WHISPER_BEAM_SIZE,
    whisper_vad_filter=WHISPER_VAD_FILTER,
    whisper_vad_min_silence_ms=WHISPER_VAD_MIN_SILENCE_MS,
    whisper_condition_on_previous_text=WHISPER_CONDITION_ON_PREVIOUS_TEXT,
    whisper_no_speech_threshold=WHISPER_NO_SPEECH_THRESHOLD,
    whisper_initial_prompt=WHISPER_INITIAL_PROMPT,
    whisper_hotwords=WHISPER_HOTWORDS,
    dictation_preset=DICTATION_PRESET,
    paste_delay_seconds=PASTE_DELAY_SECONDS,
    minimum_recording_seconds=MINIMUM_RECORDING_SECONDS,
    delete_temp_audio=DELETE_TEMP_AUDIO,
    indicator_position=INDICATOR_POSITION,
    indicator_xy=INDICATOR_XY,
    mode=MODE,
    hotkey_tokens=set(HOTKEY_TOKENS),
    destinations=list(DESTINATIONS),
    active_destination=ACTIVE_DESTINATION,
    incremental_transcription=INCREMENTAL_TRANSCRIPTION,
    incremental_chunk_mode=INCREMENTAL_CHUNK_MODE,
    incremental_vad_ms=INCREMENTAL_VAD_MS,
    incremental_chunk_seconds=INCREMENTAL_CHUNK_SECONDS,
)

_hotkey_router: HotkeyRouter | None = None
_session: Opnamesessie | None = None


def _emit_cycle_event(event: CycleEvent) -> None:
    module_bus.emit(event)


def _reload_modules() -> None:
    """Herlaadt enabled modules na splash of instellingenwijziging."""

    module_bus.shutdown()
    module_bus.set_modules(
        load_enabled_modules(
            MODULES_CONFIG,
            ui_dispatch=_ui_dispatch,
            whisper=shared_whisper,
            capabilities=capability_registry,
        )
    )
    if _tray is not None:
        _tray.refresh_modules_menu()


def _sync_runtime_from_globals() -> None:
    assert _runtime is not None
    _runtime.model_name = MODEL_NAME
    _runtime.language = LANGUAGE
    _runtime.microphone_device = MICROPHONE_DEVICE
    _runtime.auto_paste = AUTO_PASTE
    _runtime.warm_microphone = WARM_MICROPHONE
    _runtime.whisper_beam_size = WHISPER_BEAM_SIZE
    _runtime.whisper_vad_filter = WHISPER_VAD_FILTER
    _runtime.whisper_vad_min_silence_ms = WHISPER_VAD_MIN_SILENCE_MS
    _runtime.whisper_condition_on_previous_text = WHISPER_CONDITION_ON_PREVIOUS_TEXT
    _runtime.whisper_no_speech_threshold = WHISPER_NO_SPEECH_THRESHOLD
    _runtime.whisper_initial_prompt = WHISPER_INITIAL_PROMPT
    _runtime.whisper_hotwords = WHISPER_HOTWORDS
    _runtime.dictation_preset = DICTATION_PRESET
    _runtime.indicator_position = INDICATOR_POSITION
    _runtime.indicator_xy = INDICATOR_XY
    _runtime.mode = MODE
    _runtime.hotkey_tokens = set(HOTKEY_TOKENS)
    _runtime.destinations = list(DESTINATIONS)
    _runtime.active_destination = ACTIVE_DESTINATION
    _runtime.modules_config = MODULES_CONFIG
    _runtime.incremental_transcription = INCREMENTAL_TRANSCRIPTION
    _runtime.incremental_chunk_mode = INCREMENTAL_CHUNK_MODE
    _runtime.incremental_vad_ms = INCREMENTAL_VAD_MS
    _runtime.incremental_chunk_seconds = INCREMENTAL_CHUNK_SECONDS


def _modules_hold_audio_streams() -> bool:
    return any(getattr(module, "is_session_active", False) for module in module_bus.modules)


def _set_mic_attention(needed: bool) -> None:
    tray = _tray
    if tray is None:
        return
    tray.set_attention_needed(needed)


def _refresh_mic_attention() -> None:
    _set_mic_attention(not get_session().probe_microphone())


def _report_user_error(message: str) -> None:
    _ = message
    _set_mic_attention(True)


def _signal_processing_busy() -> None:
    default_signal_processing_busy(MODE, _tray)


def _handle_destination_command(kind: str, name: str | None) -> None:
    global ACTIVE_DESTINATION

    if kind == "set":
        ACTIVE_DESTINATION = name
    elif kind == "reset":
        ACTIVE_DESTINATION = None

    config.save_config(user_config_dict(sys.modules[__name__]))

    indicator = _indicator
    if indicator is not None:
        active = ACTIVE_DESTINATION
        active_path = active_destination_path(sys.modules[__name__])
        indicator.call_on_main(lambda: indicator.set_destination(active, active_path))


def _active_destination_path() -> str | None:
    return active_destination_path(sys.modules[__name__])


def _copy_to_clipboard(text: str) -> None:
    copy_to_clipboard(text, pyperclip_mod=pyperclip, ui_dispatch=_ui_dispatch)


def _save_transcript_routed(text: str) -> Path:
    return save_transcript_routed(
        text,
        active_destination=ACTIVE_DESTINATION,
        destinations_list=DESTINATIONS,
    )


def _user_config_dict() -> dict[str, Any]:
    return user_config_dict(sys.modules[__name__])


def _build_session() -> Opnamesessie:
    """Bouwt de Opnamesessie met de huidige config (geen mic/model side effects)."""

    _sync_runtime_from_globals()
    assert _runtime is not None
    return build_session(
        _runtime,
        emit_event=_emit_cycle_event,
        wait_until_modifiers_clear=wait_until_modifier_keys_released,
        on_ready=print_ready_message,
        copy_text=_copy_to_clipboard,
        save_transcript=_save_transcript_routed,
        preserve_audio=recovery.preserve_audio,
        on_destination_command=_handle_destination_command,
        get_destinations=lambda: DESTINATIONS,
        get_active_destination=lambda: ACTIVE_DESTINATION,
        on_user_error=_report_user_error,
        on_mic_ready=lambda: _set_mic_attention(False),
        has_external_streams=_modules_hold_audio_streams,
    )


def ensure_session() -> Opnamesessie:
    """Lazy Opnamesessie — niet bij module-import."""

    global _session
    if _session is None:
        _session = _build_session()
    return _session


def get_session() -> Any:
    """Session voor runtime: respecteer monkeypatch op module-attribuut."""

    mod = sys.modules[__name__]
    if "session" in mod.__dict__:
        return mod.__dict__["session"]
    return ensure_session()


def get_hotkey_router() -> HotkeyRouter:
    global _hotkey_router
    if _hotkey_router is None:
        _hotkey_router = HotkeyRouter(
            get_session=get_session,
            get_mode=lambda: MODE,
            get_hotkey_tokens=lambda: HOTKEY_TOKENS,
            keys_physically_down=lambda tokens: host.keys_physically_down(tokens),
            signal_processing_busy=_signal_processing_busy,
            state_lock=state_lock,
            pressed_tokens=pressed_tokens,
        )
    return _hotkey_router


def __getattr__(name: str) -> Any:
    if name == "session":
        return ensure_session()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def hotkey_is_pressed() -> bool:
    return get_hotkey_router().hotkey_is_pressed()


def wait_until_modifier_keys_released(timeout: float = 3.0) -> None:
    get_hotkey_router().wait_until_modifier_keys_released(timeout)


def print_ready_message() -> None:
    print()
    print(i18n.t("ready", hotkey=hotkeys.format_hotkey(HOTKEY_TOKENS)))


def set_capture(callback: Any | None) -> None:
    get_hotkey_router().set_capture(callback)
    global _capture_cb, capturing, toggle_latched
    _capture_cb = callback
    capturing = callback is not None
    # Router houdt pressed_tokens; mirror toggle_latched voor tests.
    toggle_latched = get_hotkey_router().toggle_latched


def on_press(key: Any) -> None:
    get_hotkey_router().on_press(key)
    global toggle_latched
    toggle_latched = get_hotkey_router().toggle_latched


def on_release(key: Any) -> None:
    get_hotkey_router().on_release(key)
    global toggle_latched
    toggle_latched = get_hotkey_router().toggle_latched


def current_settings() -> dict[str, Any]:
    return current_settings_svc(sys.modules[__name__])


def apply_settings(
    new_settings: dict[str, Any],
    indicator: RecordingIndicator,
) -> None:
    apply_settings_svc(
        sys.modules[__name__],
        new_settings,
        indicator,
        session=get_session(),
        reload_modules=_reload_modules,
        refresh_mic_attention=_refresh_mic_attention,
        tray=_tray,
    )
    _sync_runtime_from_globals()


def retranscribe_recovery_wav(path: Path) -> str:
    return retranscribe_recovery_wav_impl(
        path,
        session=get_session(),
        shared_whisper=shared_whisper,
        module_bus=module_bus,
        language=LANGUAGE,
        mode=MODE,
        active_destination=ACTIVE_DESTINATION,
        destinations_list=DESTINATIONS,
        auto_paste=AUTO_PASTE,
        paste_delay_seconds=PASTE_DELAY_SECONDS,
        host_obj=host,
        copy_text=_copy_to_clipboard,
        wait_until_modifiers_clear=wait_until_modifier_keys_released,
    )


def _recent_transcript_menu_entries() -> list[tuple]:
    return recent_transcript_menu_entries(
        DESTINATIONS,
        pyperclip_mod=pyperclip,
        ui_dispatch=_ui_dispatch,
    )


# Compat re-exports used by tests / older call sites.
_load_dependencies = None  # set via startup path
load_model = None


def main() -> None:
    from app.run import main as app_main

    app_main()


if __name__ == "__main__":
    main()
