"""Meeting Buddy lifecycle and tray-led actions (including on macOS)."""

from __future__ import annotations

from modules._contract import CycleEvent, ModuleAction, ModuleContext

from .orchestrator import MeetingOrchestrator
from .overlay import MeetingBuddyOverlay
from .state import MeetingState


class MeetingBuddyModule:
    id = "meeting-buddy"

    def __init__(self) -> None:
        self._orchestrator: MeetingOrchestrator | None = None
        self._ui_dispatch = None
        self._overlay: MeetingBuddyOverlay | None = None

    @property
    def orchestrator(self) -> MeetingOrchestrator | None:
        return self._orchestrator

    def display_name_key(self) -> str:
        return "modules.meeting_buddy.name"

    def description_key(self) -> str:
        return "modules.meeting_buddy.description"

    def default_enabled(self) -> bool:
        return False

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._ui_dispatch = ctx.ui_dispatch
        self._orchestrator = MeetingOrchestrator(
            capabilities=ctx.capabilities,
            app_dir=ctx.app_dir,
            on_ui_update=self._on_ui_update,
        )

    def on_event(self, event: CycleEvent) -> None:
        del event

    def actions(self) -> list[ModuleAction]:
        return [
            ModuleAction(
                id="start_meeting",
                label_key="modules.meeting_buddy.actions.start",
                handler=self.start_meeting,
                in_tray=True,
            ),
            ModuleAction(
                id="stop_meeting",
                label_key="modules.meeting_buddy.actions.stop",
                handler=self.stop_meeting,
                in_tray=True,
            ),
            ModuleAction(
                id="prepare_agenda",
                label_key="modules.meeting_buddy.actions.prepare_agenda",
                handler=self.prepare_agenda,
                in_tray=True,
            ),
        ]

    def set_agenda(self, text: str) -> None:
        self._require_orchestrator().set_agenda(text)

    def start_meeting(self) -> None:
        self._require_orchestrator().start()

    def stop_meeting(self) -> None:
        self._require_orchestrator().stop()
        if self._ui_dispatch is not None:
            self._ui_dispatch(self._close_overlay)

    def prepare_agenda(self) -> None:
        if self._ui_dispatch is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        self._ui_dispatch(self._show_agenda_dialog)

    def on_app_shutdown(self) -> None:
        if self._orchestrator is not None:
            self._orchestrator.stop()
        self._close_overlay()
        self._orchestrator = None
        self._ui_dispatch = None

    def _show_agenda_dialog(self) -> None:
        from tkinter import simpledialog

        orchestrator = self._require_orchestrator()
        draft = simpledialog.askstring(
            "Meeting Buddy",
            "Agenda (één onderwerp per regel):",
            initialvalue=orchestrator.agenda_text,
        )
        if draft is not None:
            orchestrator.set_agenda(draft)

    def _on_ui_update(self, state: MeetingState) -> None:
        if self._ui_dispatch is None:
            return
        orchestrator = self._require_orchestrator()
        capture_status = orchestrator.capture_status
        transcription_status = orchestrator.transcription_status
        self._ui_dispatch(
            lambda: self._show_overlay_update(
                state,
                capture_status=capture_status,
                transcription_status=transcription_status,
            )
        )

    def _show_overlay_update(
        self,
        state: MeetingState,
        *,
        capture_status: object,
        transcription_status: object,
    ) -> None:
        if self._overlay is None:
            orchestrator = self._require_orchestrator()
            self._overlay = MeetingBuddyOverlay(
                elapsed_seconds=orchestrator.elapsed_seconds,
                on_dismiss=orchestrator.dismiss_hint,
                on_confirm=orchestrator.confirm_hint,
                on_reconnect=orchestrator.reconnect_capture,
            )
        self._overlay.update(
            state,
            capture_status=capture_status,
            transcription_status=transcription_status,
        )

    def _close_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.close()
            self._overlay = None

    def _require_orchestrator(self) -> MeetingOrchestrator:
        if self._orchestrator is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        return self._orchestrator
