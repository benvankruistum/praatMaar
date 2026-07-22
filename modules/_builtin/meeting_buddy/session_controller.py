"""Capture and STT capability session lifecycle."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from modules.capabilities.continuous_capture import (
    CAPABILITY_ID as CAP_CAPTURE,
)
from modules.capabilities.continuous_capture import (
    CONTRACT_VERSION as CAPTURE_CONTRACT_VERSION,
)
from modules.capabilities.continuous_capture import (
    CaptureGap,
    CaptureStatus,
    CaptureStatusChanged,
)
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID as CAP_STT,
)
from modules.capabilities.speech_to_text import (
    CONTRACT_VERSION as STT_CONTRACT_VERSION,
)
from modules.capabilities.speech_to_text import (
    TranscriptGap,
    TranscriptionStatus,
    TranscriptionStatusChanged,
)

from .binding import MeetingSessionBinding
from .config import MeetingBuddyConfig
from .observability import EventObserver, log_event


class CapabilitySessionController:
    """Start, stop, reconnect, and observe capture/STT capability sessions."""

    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry,
        config: MeetingBuddyConfig,
        observer: EventObserver | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._config = config
        self._observer = observer
        self._capture: Any = None
        self._stt: Any = None
        self._binding: MeetingSessionBinding | None = None
        self._capture_status = CaptureStatus.IDLE
        self._transcription_status = TranscriptionStatus.IDLE
        self._loopback_active: bool | None = None
        self._on_capture_status: object | None = None
        self._on_stt_event: object | None = None

    @property
    def binding(self) -> MeetingSessionBinding | None:
        return self._binding

    @property
    def capture_status(self) -> CaptureStatus:
        return self._capture_status

    @property
    def transcription_status(self) -> TranscriptionStatus:
        return self._transcription_status

    @property
    def loopback_active(self) -> bool | None:
        return self._loopback_active

    def update_config(self, config: MeetingBuddyConfig) -> None:
        self._config = config

    def start(self) -> MeetingSessionBinding:
        if self._binding is not None:
            raise RuntimeError("Meeting Buddy is al gestart")

        capture = self._capabilities.require(
            CAP_CAPTURE,
            minimum_contract_version=CAPTURE_CONTRACT_VERSION,
        )
        stt = self._capabilities.require(
            CAP_STT,
            minimum_contract_version=STT_CONTRACT_VERSION,
        )

        capture_session = capture.start_session(self.capture_config())
        try:
            transcription_session = stt.start_session(
                capture_session_id=capture_session.session_id,
                capture=capture,
                config={
                    "max_whisper_queue_duration_s": self._config.max_whisper_queue_duration_s,
                },
            )
        except Exception as exc:
            try:
                capture.stop_session(capture_session.session_id)
            except Exception:
                pass
            raise RuntimeError(f"Meeting Buddy starten mislukt: {exc}") from exc

        meeting_session_id = str(uuid4())
        binding = MeetingSessionBinding(
            meeting_session_id=meeting_session_id,
            capture_session_id=capture_session.session_id,
            transcription_session_id=transcription_session.session_id,
        )
        self._capture = capture
        self._stt = stt
        self._binding = binding
        self._capture_status = capture.get_status(capture_session.session_id)
        self._transcription_status = stt.get_status(transcription_session.session_id)
        return binding

    def subscribe(
        self,
        *,
        on_capture_status: object,
        on_stt_event: object,
    ) -> None:
        binding = self._require_binding()
        self._on_capture_status = on_capture_status
        self._on_stt_event = on_stt_event
        self._capture.subscribe(binding.capture_session_id, on_capture_status)
        self._stt.subscribe(binding.transcription_session_id, on_stt_event)

    def log_started(self) -> None:
        binding = self._require_binding()
        capture_config = self.capture_config()
        log_event(
            self._observer,
            "meeting_started",
            meeting_session_id=binding.meeting_session_id,
            capture_session_id=binding.capture_session_id,
            transcription_session_id=binding.transcription_session_id,
        )
        log_event(
            self._observer,
            "capture_sources",
            meeting_session_id=binding.meeting_session_id,
            capture_session_id=binding.capture_session_id,
            mic_device=capture_config.get("device"),
            loopback_device=capture_config.get("loopback_device"),
            loopback_requested=self._config.enable_loopback,
            loopback_active=self._loopback_active,
        )

    def reconnect(self) -> None:
        binding = self._require_binding()
        log_event(
            self._observer,
            "capture_restart",
            meeting_session_id=binding.meeting_session_id,
            capture_session_id=binding.capture_session_id,
        )
        self._capture_status = CaptureStatus.RECONNECTING

    def finish_reconnect(self) -> None:
        binding = self._require_binding()
        self._cleanup_sessions(binding)

        capture_session = None
        try:
            capture_session = self._capture.start_session(self.capture_config())
            transcription_session = self._stt.start_session(
                capture_session_id=capture_session.session_id,
                capture=self._capture,
                config={
                    "max_whisper_queue_duration_s": self._config.max_whisper_queue_duration_s,
                },
            )
            self._binding = MeetingSessionBinding(
                meeting_session_id=binding.meeting_session_id,
                capture_session_id=capture_session.session_id,
                transcription_session_id=transcription_session.session_id,
            )
            self._capture_status = self._capture.get_status(capture_session.session_id)
            self._transcription_status = self._stt.get_status(transcription_session.session_id)
        except Exception as exc:
            if capture_session is not None:
                try:
                    self._capture.stop_session(capture_session.session_id)
                except Exception:
                    pass
            self._capture_status = CaptureStatus.ERROR
            self._transcription_status = TranscriptionStatus.ERROR
            raise RuntimeError(f"Microfoon herverbinden mislukt: {exc}") from exc

    def stop(self, *, duration_ms: int) -> None:
        binding = self._binding
        if binding is None:
            return
        self._cleanup_sessions(binding)
        log_event(
            self._observer,
            "meeting_stopped",
            meeting_session_id=binding.meeting_session_id,
            duration_ms=duration_ms,
        )

    def abort_sessions(self) -> None:
        binding = self._binding
        if binding is None:
            return
        self._cleanup_sessions(binding)

    def clear(self) -> None:
        self._binding = None
        self._capture = None
        self._stt = None
        self._capture_status = CaptureStatus.IDLE
        self._transcription_status = TranscriptionStatus.IDLE
        self._loopback_active = None

    def handle_capture_event(self, event: object) -> bool:
        """Return ``True`` when the overlay should refresh."""

        binding = self._binding
        if binding is None:
            return False
        if isinstance(event, CaptureStatusChanged):
            if event.session_id != binding.capture_session_id:
                return False
            previous_loopback = self._loopback_active
            self._capture_status = event.status
            if event.loopback_active is not None:
                self._loopback_active = event.loopback_active
            if (
                self._config.enable_loopback
                and event.status == CaptureStatus.ACTIVE
                and event.loopback_active is False
                and previous_loopback is not False
            ):
                log_event(
                    self._observer,
                    "loopback_unavailable",
                    meeting_session_id=binding.meeting_session_id,
                    capture_session_id=event.session_id,
                    reason=event.message or "loopback inactive",
                )
            if event.status == CaptureStatus.RECONNECTING:
                log_event(
                    self._observer,
                    "loopback_reconnecting",
                    meeting_session_id=binding.meeting_session_id,
                    capture_session_id=event.session_id,
                    reason=event.message,
                )
            return True
        if isinstance(event, CaptureGap):
            log_event(
                self._observer,
                "transcript_gap",
                meeting_session_id=binding.meeting_session_id,
                capture_session_id=event.session_id,
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                reason=event.reason,
            )
            return True
        return False

    def handle_stt_status_event(self, event: object) -> bool:
        """Return ``True`` when the overlay should refresh."""

        binding = self._binding
        if binding is None:
            return False
        if isinstance(event, TranscriptionStatusChanged):
            if event.session_id != binding.transcription_session_id:
                return False
            self._transcription_status = event.status
            return True
        if isinstance(event, TranscriptGap):
            log_event(
                self._observer,
                "transcript_gap",
                meeting_session_id=binding.meeting_session_id,
                transcription_session_id=event.session_id,
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                reason=event.reason,
            )
            self._transcription_status = TranscriptionStatus.DELAYED
            return True
        return False

    def capture_config(self) -> dict[str, object]:
        """Build audio-capture options: app mic + Meeting Buddy loopback settings."""

        from config import load_config

        app_settings = load_config()
        microphone_device = app_settings.get("microphone_device")
        device = microphone_device if isinstance(microphone_device, int) else None
        return {
            "max_audio_buffer_duration_s": self._config.max_audio_buffer_duration_s,
            "device": device,
            "enable_loopback": self._config.enable_loopback,
            "loopback_device": self._config.loopback_device,
        }

    def _cleanup_sessions(self, binding: MeetingSessionBinding) -> None:
        if self._on_stt_event is not None:
            try:
                self._stt.unsubscribe(binding.transcription_session_id, self._on_stt_event)
            except Exception:
                pass
        if self._on_capture_status is not None:
            try:
                self._capture.unsubscribe(binding.capture_session_id, self._on_capture_status)
            except Exception:
                pass
        try:
            self._stt.stop_session(binding.transcription_session_id)
        except Exception:
            pass
        try:
            self._capture.stop_session(binding.capture_session_id)
        except Exception:
            pass

    def _require_binding(self) -> MeetingSessionBinding:
        if self._binding is None:
            raise RuntimeError("Meeting Buddy is niet gestart")
        return self._binding
