"""AppRuntime — composition-root container (ADR-0007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules import CapabilityRegistry, ModuleBus, SharedWhisper, noop_ui_dispatch


@dataclass
class AppRuntime:
    """Houdt seams en optionele sessie bij zonder import-time side effects."""

    host: Any
    shared_whisper: SharedWhisper
    capability_registry: CapabilityRegistry
    module_bus: ModuleBus
    session: Any | None = None
    tray: Any | None = None
    indicator: Any | None = None
    ui_dispatch: Any = field(default=noop_ui_dispatch)
    model: Any | None = None

    # Settings snapshot (gesynchroniseerd met dictation-globals tijdens strangler).
    model_name: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "nl"
    sample_rate: int = 16000
    channels: int = 1
    microphone_device: int | None = None
    auto_paste: bool = True
    warm_microphone: bool = False
    whisper_beam_size: int = 5
    whisper_vad_filter: bool = True
    whisper_vad_min_silence_ms: int = 300
    whisper_condition_on_previous_text: bool = False
    whisper_no_speech_threshold: float = 0.6
    whisper_initial_prompt: str = ""
    whisper_hotwords: str = ""
    paste_delay_seconds: float = 0.30
    minimum_recording_seconds: float = 0.30
    delete_temp_audio: bool = True
    indicator_position: str = "boven-midden"
    indicator_xy: tuple[int, int] | None = None
    mode: str = "toggle"
    hotkey_tokens: set[str] = field(default_factory=set)
    destinations: list[dict[str, Any]] = field(default_factory=list)
    active_destination: str | None = None
    modules_config: dict[str, Any] = field(default_factory=dict)
    incremental_transcription: bool = False
    incremental_chunk_mode: str = "hybrid"
    incremental_vad_ms: int = 2000
    incremental_chunk_seconds: float = 30.0
