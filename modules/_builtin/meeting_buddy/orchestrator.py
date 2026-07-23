"""Meeting Buddy session binding and transcript-to-state orchestration."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from threading import RLock

from modules.capabilities.continuous_capture import CaptureStatus
from modules.capabilities.registry import CapabilityRegistry, CapabilityUnavailableError
from modules.capabilities.speaker_detection import (
    CAPABILITY_ID as SPEAKER_DETECTION_ID,
)
from modules.capabilities.speaker_detection import (
    AudioSource,
    SpeakerRole,
    TranscriptSegment,
)
from modules.capabilities.speech_to_text import TranscriptDeltaReceived, TranscriptionStatus

from .agenda_review import AgendaReviewCoordinator, AgendaReviewSettings, LabeledFinal
from .binding import MeetingSessionBinding
from .config import load_live_summary_prefs, load_meeting_buddy_config, load_transcripts_directory
from .hint_coordinator import HintCoordinator
from .live_summary import LiveSummaryCoordinator, LiveSummarySettings
from .observability import EventObserver
from .prep import parse_agenda
from .session_controller import CapabilitySessionController
from .state import MeetingState
from .transcript_journal import TranscriptJournal, transcripts_dir
from .transcript_processor import TranscriptProcessor
from .ui_presenter import MeetingUiPresenter, UiUpdate

__all__ = ["MeetingOrchestrator", "MeetingSessionBinding", "UiUpdate"]

log = logging.getLogger(__name__)


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
        self._journal_title: str | None = None
        self._journal: TranscriptJournal | None = None
        self._last_transcript_path: Path | None = None
        self._state: MeetingState | None = None
        self._started_at: float | None = None
        self._live_summary = LiveSummaryCoordinator(
            capabilities=capabilities,
            settings=self._live_summary_settings(),
            on_summary=self._on_live_summary,
        )
        self._agenda_review = AgendaReviewCoordinator(
            capabilities=capabilities,
            settings=self._agenda_review_settings(),
            on_review=self._on_agenda_review,
        )
        self._capabilities = capabilities

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
    def last_transcript_path(self) -> Path | None:
        return self._last_transcript_path

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
            self._live_summary.update_settings(self._live_summary_settings())
            self._agenda_review.update_settings(self._agenda_review_settings())

    def elapsed_seconds(self) -> float:
        return self._elapsed_s()

    def set_agenda(self, text: str) -> None:
        self._agenda_text = text

    def set_journal_title(self, title: str | None) -> None:
        self._journal_title = title.strip() if title else None

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
                self._open_transcript_journal()
                self._live_summary.reset()
                self._agenda_review.reset()
                summary_settings = self._live_summary_settings()
                self._live_summary.update_settings(summary_settings)
                self._agenda_review.update_settings(self._agenda_review_settings())
                self._state = replace(
                    self._state,
                    live_summary_enabled=bool(summary_settings.enabled),
                )
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

    def stop(self) -> Path | None:
        with self._lock:
            if self._sessions.binding is None:
                return self._last_transcript_path
            duration_ms = int(self._elapsed_s() * 1000)
            try:
                self._sessions.stop(duration_ms=duration_ms)
            except Exception:
                pass
            try:
                self._ui.notify(self._state, force=True)
            except Exception:
                pass
            path = self._finalize_transcript_journal()
            try:
                self._sessions.clear()
            finally:
                self._live_summary.reset()
                self._agenda_review.reset()
                self._clear_running_state()
            return path

    def on_stt_event(self, event: object) -> None:
        final_text: str | None = None
        labeled: LabeledFinal | None = None
        review_state: MeetingState | None = None
        notify_state: MeetingState | None = None
        notify_force = False
        with self._lock:
            binding = self._sessions.binding
            if binding is None or self._state is None:
                return

            if self._sessions.handle_stt_status_event(event):
                notify_state = self._state
                notify_force = True
            elif isinstance(event, TranscriptDeltaReceived):
                if event.delta.is_final:
                    if self._journal is not None:
                        self._journal.append_final(event.delta.text)
                    final_text = event.delta.text
                    labeled = self._label_final(event.delta.text, binding.meeting_session_id)

                version_before = self._state.version
                hints_before = self._state.emitted_hints
                now_s = self._elapsed_s()
                use_topic_heuristics = not self._agenda_review.provider_is_ready()
                self._state = self._transcripts.process_delta(
                    event,
                    binding=binding,
                    state=self._state,
                    config=self._config,
                    elapsed_s=now_s,
                    observer=self._observer,
                    use_topic_heuristics=use_topic_heuristics,
                )
                self._state = self._hints.update_hints(
                    self._state,
                    self._config,
                    now_s,
                    observer=self._observer,
                )
                if labeled is not None:
                    review_state = self._state
                state_changed = self._state.version != version_before
                hints_changed = self._state.emitted_hints != hints_before
                if state_changed or hints_changed:
                    notify_state = self._state
                    notify_force = True

        if notify_state is not None:
            self._ui.notify(notify_state, force=notify_force)
        if final_text is not None:
            self._live_summary.on_final_text(final_text)
        if labeled is not None and review_state is not None:
            self._agenda_review.on_final(labeled, state=review_state)

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

    def _open_transcript_journal(self) -> None:
        titles = parse_agenda(self._agenda_text)
        title = self._journal_title or (titles[0] if titles else "Meeting")
        override = load_transcripts_directory(self._app_dir)
        directory = transcripts_dir(self._app_dir, override=override)
        try:
            self._journal = TranscriptJournal.create(
                self._app_dir,
                title=title,
                agenda_titles=titles,
                started_at=datetime.now(),
                directory=directory,
            )
            self._last_transcript_path = self._journal.path
            log.info("Meeting transcript opened path=%s", self._journal.path)
        except OSError as exc:
            self._journal = None
            log.warning("Meeting transcript create failed error=%s", exc)

    def _finalize_transcript_journal(self) -> Path | None:
        if self._journal is None:
            return self._last_transcript_path
        topics = self._state.topics if self._state is not None else None
        try:
            path = self._journal.finalize(topics=topics, ended_at=datetime.now())
            self._last_transcript_path = path
            log.info("Meeting transcript finalized path=%s", path)
            return path
        except OSError as exc:
            log.warning("Meeting transcript finalize failed error=%s", exc)
            return self._last_transcript_path
        finally:
            self._journal = None

    def _capture_config(self) -> dict[str, object]:
        return self._sessions.capture_config()

    def _clear_running_state(self) -> None:
        self._started_at = None
        self._state = None
        self._journal = None

    def _elapsed_s(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.monotonic() - self._started_at

    def _live_summary_settings(self) -> LiveSummarySettings:
        prefs = load_live_summary_prefs(self._app_dir)
        return LiveSummarySettings(
            enabled=bool(prefs["live_summary_enabled"]),
            interval_s=float(prefs["llm_chunk_interval_s"]),
            min_new_chars=int(prefs["llm_chunk_min_new_chars"]),
            language="nl",
        )

    def _agenda_review_settings(self) -> AgendaReviewSettings:
        prefs = load_live_summary_prefs(self._app_dir)
        return AgendaReviewSettings(
            enabled=bool(prefs["live_summary_enabled"]),
            interval_s=float(prefs["llm_chunk_interval_s"]),
            min_new_chars=int(prefs["llm_chunk_min_new_chars"]),
            language="nl",
        )

    def _label_final(self, text: str, meeting_session_id: str) -> LabeledFinal:
        provider = self._capabilities.get(SPEAKER_DETECTION_ID)
        if provider is None:
            return LabeledFinal(text=text, speaker_role=SpeakerRole.UNKNOWN)
        source = AudioSource.UNKNOWN
        if self.loopback_active is False:
            source = AudioSource.MICROPHONE
        try:
            assignment = provider.assign_speaker(
                TranscriptSegment(
                    text=text,
                    session_id=meeting_session_id,
                    source=source,
                )
            )
            return LabeledFinal(text=text, speaker_role=assignment.role)
        except Exception:
            log.exception("Speaker label failed")
            return LabeledFinal(text=text, speaker_role=SpeakerRole.UNKNOWN)

    def _on_live_summary(self, text: str) -> None:
        with self._lock:
            if self._state is None:
                return
            self._state = replace(
                self._state,
                live_summary=text,
                version=self._state.version + 1,
            )
            state = self._state
        # UI buiten de lock: anders blokkeert de LLM-thread de STT-callback.
        self._ui.notify(state, force=True)

    def _on_agenda_review(self, reviewed: MeetingState) -> None:
        with self._lock:
            if self._state is None:
                return
            if reviewed.meeting_session_id != self._state.meeting_session_id:
                return
            self._state = replace(
                reviewed,
                live_summary=self._state.live_summary,
                live_summary_enabled=self._state.live_summary_enabled,
                version=max(self._state.version, reviewed.version) + 1,
            )
            state = self._state
        self._ui.notify(state, force=True)
