"""Meeting Buddy session binding and transcript-to-state orchestration."""

from __future__ import annotations

import time
from pathlib import Path
from threading import RLock

from modules.capabilities.continuous_capture import CaptureStatus
from modules.capabilities.registry import CapabilityRegistry, CapabilityUnavailableError
from modules.capabilities.speech_to_text import TranscriptDeltaReceived, TranscriptionStatus

from .binding import MeetingSessionBinding
from .config import load_meeting_buddy_config
from .hint_coordinator import HintCoordinator
from .observability import EventObserver
from .session_controller import CapabilitySessionController
from .state import MeetingState
from .transcript_processor import TranscriptProcessor
from .ui_presenter import MeetingUiPresenter, UiUpdate

__all__ = ["MeetingOrchestrator", "MeetingSessionBinding", "UiUpdate"]


class MeetingOrchestrator:
    """Owns a Meeting Buddy session and coordinates capability + state updates."""

    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry,
        app_dir: Path,
        observer: EventObserver | None = None,
        on_ui_update: UiUpdate | None = None,
    ) -> None:
        self._app_dir = app_dir
        self._config = load_meeting_buddy_config(app_dir)
        self._observer = observer
        self._lock = RLock()
        self._sessions = CapabilitySessionController(
            capabilities=capabilities,
            config=self._config,
            observer=observer,
        )
        self._transcripts = TranscriptProcessor()
        self._hints = HintCoordinator()
        self._ui = MeetingUiPresenter(on_ui_update)
        self._agenda_text = ""
        self._state: MeetingState | None = None
        self._started_at: float | None = None

    @property
    def binding(self) -> MeetingSessionBinding | None:
        return self._sessions.binding

    @property
    def state(self) -> MeetingState:
        with self._lock:
            if self._state is None:
                raise RuntimeError("Meeting Buddy is niet gestart")
            return self._state

    @property
    def agenda_text(self) -> str:
        return self._agenda_text

    @property
    def capture_status(self) -> CaptureStatus:
        return self._sessions.capture_status

    @property
    def transcription_status(self) -> TranscriptionStatus:
        return self._sessions.transcription_status

    @property
    def loopback_active(self) -> bool | None:
        return self._sessions.loopback_active

    @property
    def loopback_requested(self) -> bool:
        return self._config.enable_loopback

    @property
    def loopback_device(self) -> int | None:
        return self._config.loopback_device

    def reload_config(self) -> None:
        """Reload user preferences (e.g. after saving loopback device)."""

        with self._lock:
            self._config = load_meeting_buddy_config(self._app_dir)
            self._sessions.update_config(self._config)

    def elapsed_seconds(self) -> float:
        return self._elapsed_s()

    def set_agenda(self, text: str) -> None:
        self._agenda_text = text

    def start(self, agenda_text: str | None = None) -> None:
        with self._lock:
            if self._sessions.binding is not None:
                raise RuntimeError("Meeting Buddy is al gestart")
            if agenda_text is not None:
                self.set_agenda(agenda_text)

            self._sessions.update_config(self._config)
            try:
                binding = self._sessions.start()
                self._started_at = time.monotonic()
                self._state = MeetingState.empty(binding.meeting_session_id)
                self._sessions.subscribe(
                    on_capture_status=self.on_capture_status,
                    on_stt_event=self.on_stt_event,
                )
                self._state = self._transcripts.apply_agenda(self._state, self._agenda_text)
                self._sessions.log_started()
                self._ui.notify(self._state, force=True)
            except CapabilityUnavailableError:
                self._clear_running_state()
                raise
            except Exception as exc:
                if self._sessions.binding is not None:
                    self._sessions.abort_sessions()
                    self._sessions.clear()
                self._clear_running_state()
                message = str(exc)
                if isinstance(exc, RuntimeError) and (
                    "starten mislukt" in message or "al gestart" in message
                ):
                    raise
                raise RuntimeError(f"Meeting Buddy starten mislukt: {exc}") from exc

    def reconnect_capture(self) -> None:
        with self._lock:
            if self._sessions.binding is None:
                raise RuntimeError("Meeting Buddy is niet gestart")

            self._sessions.reconnect()
            self._ui.notify(self._state, force=True)
            try:
                self._sessions.finish_reconnect()
                self._sessions.subscribe(
                    on_capture_status=self.on_capture_status,
                    on_stt_event=self.on_stt_event,
                )
            except Exception:
                self._ui.notify(self._state, force=True)
                raise
            self._ui.notify(self._state, force=True)

    def stop(self) -> None:
        with self._lock:
            if self._sessions.binding is None:
                return
            duration_ms = int(self._elapsed_s() * 1000)
            try:
                self._sessions.stop(duration_ms=duration_ms)
            except Exception:
                pass
            try:
                self._ui.notify(self._state, force=True)
            except Exception:
                pass
            finally:
                self._sessions.clear()
                self._clear_running_state()

    def on_stt_event(self, event: object) -> None:
        with self._lock:
            binding = self._sessions.binding
            if binding is None or self._state is None:
                return

            if self._sessions.handle_stt_status_event(event):
                self._ui.notify(self._state, force=True)
                return
            if not isinstance(event, TranscriptDeltaReceived):
                return

            version_before = self._state.version
            hints_before = self._state.emitted_hints
            now_s = self._elapsed_s()
            self._state = self._transcripts.process_delta(
                event,
                binding=binding,
                state=self._state,
                config=self._config,
                elapsed_s=now_s,
                observer=self._observer,
            )
            self._state = self._hints.update_hints(
                self._state,
                self._config,
                now_s,
                observer=self._observer,
            )
            state_changed = self._state.version != version_before
            hints_changed = self._state.emitted_hints != hints_before
            self._ui.notify(self._state, force=state_changed or hints_changed)

    def on_capture_status(self, event: object) -> None:
        with self._lock:
            if self._sessions.binding is None or self._state is None:
                return
            if self._sessions.handle_capture_event(event):
                self._ui.notify(self._state, force=True)

    def dismiss_hint(self, hint_id: str) -> None:
        with self._lock:
            self._state = self._hints.dismiss_hint(
                self.state,
                hint_id,
                elapsed_s=self._elapsed_s(),
                observer=self._observer,
            )
            self._ui.notify(self._state, force=True)

    def confirm_hint(self, hint_id: str) -> None:
        with self._lock:
            self._state = self._hints.confirm_hint(
                self.state,
                hint_id,
                elapsed_s=self._elapsed_s(),
                observer=self._observer,
            )
            self._ui.notify(self._state, force=True)

    def _capture_config(self) -> dict[str, object]:
        return self._sessions.capture_config()

    def _clear_running_state(self) -> None:
        self._started_at = None
        self._state = None

    def _elapsed_s(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.monotonic() - self._started_at
