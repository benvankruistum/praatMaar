"""Bootstrap: wiring zonder import-time Opnamesessie of module-start side effects."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import host
from app.runtime import AppRuntime
from modules import (
    CapabilityRegistry,
    ModuleBus,
    SharedWhisper,
    sanitize_modules_config,
)
from opnamesessie import Opnamesessie


def build_runtime(
    *,
    host_obj: Any | None = None,
    shared_whisper: SharedWhisper | None = None,
    capability_registry: CapabilityRegistry | None = None,
    module_bus: ModuleBus | None = None,
    modules_config: dict[str, Any] | None = None,
    **settings: Any,
) -> AppRuntime:
    """Bouwt AppRuntime zonder Opnamesessie en zonder load_enabled_modules."""

    caps = capability_registry if capability_registry is not None else CapabilityRegistry()
    whisper = shared_whisper if shared_whisper is not None else SharedWhisper()
    bus = module_bus if module_bus is not None else ModuleBus(capabilities=caps)
    runtime = AppRuntime(
        host=host_obj if host_obj is not None else host.default,
        shared_whisper=whisper,
        capability_registry=caps,
        module_bus=bus,
        modules_config=sanitize_modules_config(modules_config or {}),
    )
    for key, value in settings.items():
        if hasattr(runtime, key):
            setattr(runtime, key, value)
    return runtime


def build_session(
    runtime: AppRuntime,
    *,
    emit_event: Callable[..., None] | None = None,
    wait_until_modifiers_clear: Callable[[], None] | None = None,
    on_ready: Callable[[], None] | None = None,
    copy_text: Callable[[str], None] | None = None,
    save_transcript: Callable[[str], Path] | None = None,
    preserve_audio: Callable[[Path], Path] | None = None,
    on_destination_command: Callable[[str, str | None], None] | None = None,
    get_destinations: Callable[[], list[dict[str, Any]]] | None = None,
    get_active_destination: Callable[[], str | None] | None = None,
    on_user_error: Callable[[str], None] | None = None,
    on_mic_ready: Callable[[], None] | None = None,
    has_external_streams: Callable[[], bool] | None = None,
) -> Opnamesessie:
    """Construeert Opnamesessie en hangt die aan runtime (geen mic/model side effects)."""

    session = Opnamesessie(
        host=runtime.host,
        sample_rate=runtime.sample_rate,
        channels=runtime.channels,
        microphone_device=runtime.microphone_device,
        minimum_recording_seconds=runtime.minimum_recording_seconds,
        auto_paste=runtime.auto_paste,
        paste_delay_seconds=runtime.paste_delay_seconds,
        language=runtime.language,
        delete_temp_audio=runtime.delete_temp_audio,
        mode=runtime.mode,
        warm_microphone=runtime.warm_microphone,
        whisper_beam_size=runtime.whisper_beam_size,
        whisper_vad_filter=runtime.whisper_vad_filter,
        whisper_vad_min_silence_ms=runtime.whisper_vad_min_silence_ms,
        whisper_condition_on_previous_text=runtime.whisper_condition_on_previous_text,
        whisper_no_speech_threshold=runtime.whisper_no_speech_threshold,
        whisper_initial_prompt=runtime.whisper_initial_prompt,
        whisper_hotwords=runtime.whisper_hotwords,
        incremental_transcription=runtime.incremental_transcription,
        incremental_chunk_mode=runtime.incremental_chunk_mode,
        incremental_vad_ms=runtime.incremental_vad_ms,
        incremental_chunk_seconds=runtime.incremental_chunk_seconds,
        emit_event=emit_event,
        wait_until_modifiers_clear=wait_until_modifiers_clear,
        on_ready=on_ready,
        copy_text=copy_text,
        save_transcript=save_transcript,
        preserve_audio=preserve_audio,
        on_destination_command=on_destination_command,
        get_destinations=get_destinations or (lambda: list(runtime.destinations)),
        get_active_destination=get_active_destination
        or (lambda: runtime.active_destination),
        on_user_error=on_user_error,
        on_mic_ready=on_mic_ready,
        has_external_streams=has_external_streams,
        shared_whisper=runtime.shared_whisper,
    )
    runtime.session = session
    return session
