"""Meeting Buddy module lifecycle and tray actions."""

from __future__ import annotations

from modules._contract import CycleEvent, ModuleAction, ModuleContext

from .orchestrator import MeetingOrchestrator


class MeetingBuddyModule:
    id = "meeting-buddy"

    def __init__(self) -> None:
        self._orchestrator: MeetingOrchestrator | None = None
        self._ui_dispatch = None

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

    def prepare_agenda(self) -> None:
        if self._ui_dispatch is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        self._ui_dispatch(self._show_agenda_dialog)

    def on_app_shutdown(self) -> None:
        if self._orchestrator is not None:
            self._orchestrator.stop()
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

    def _require_orchestrator(self) -> MeetingOrchestrator:
        if self._orchestrator is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        return self._orchestrator
