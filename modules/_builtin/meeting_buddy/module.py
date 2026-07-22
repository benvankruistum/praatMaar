"""Meeting Buddy lifecycle and tray-led actions (including on macOS)."""

from __future__ import annotations

from pathlib import Path

import i18n
from indicator import RecordingState, notify_state, reset_levels
from modules._contract import CycleEvent, ModuleAction, ModuleContext
from modules.capabilities.continuous_capture import CaptureStatus

from .agenda_dialog import can_start_meeting, show_agenda_dialog
from .agenda_store import touch_recent
from .config import save_meeting_buddy_preferences
from .orchestrator import MeetingOrchestrator
from .overlay import MeetingBuddyOverlay
from .properties_dialog import show_properties_dialog
from .state import MeetingState


class MeetingBuddyModule:
    id = "meeting-buddy"

    def __init__(self) -> None:
        self._orchestrator: MeetingOrchestrator | None = None
        self._ui_dispatch = None
        self._overlay: MeetingBuddyOverlay | None = None
        self._pill_capture_status: CaptureStatus | None = None
        self._app_dir: Path | None = None
        self._agenda_path: Path | None = None

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
        self._app_dir = ctx.app_dir
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
                id="start_meeting_quick",
                label_key="modules.meeting_buddy.actions.start_quick",
                handler=self.start_meeting_quick,
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
            ModuleAction(
                id="properties",
                label_key="modules.meeting_buddy.actions.properties",
                handler=self.open_properties,
                in_tray=True,
            ),
        ]

    def set_agenda(self, text: str) -> None:
        self._require_orchestrator().set_agenda(text)

    def start_meeting(self) -> None:
        if self._ui_dispatch is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        self._ui_dispatch(self._start_meeting_flow)

    def start_meeting_quick(self) -> None:
        if self._ui_dispatch is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        self._ui_dispatch(self._start_meeting_quick_flow)

    def stop_meeting(self) -> None:
        self._require_orchestrator().stop()
        self._release_recording_pill()
        if self._ui_dispatch is not None:
            self._ui_dispatch(self._close_overlay)

    def prepare_agenda(self) -> None:
        if self._ui_dispatch is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        self._ui_dispatch(lambda: self._show_agenda_dialog(mode="edit"))

    def open_properties(self) -> None:
        if self._ui_dispatch is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        self._ui_dispatch(self._show_properties_dialog)

    def on_app_shutdown(self) -> None:
        if self._orchestrator is not None:
            self._orchestrator.stop()
        self._release_recording_pill()
        self._close_overlay()
        self._orchestrator = None
        self._ui_dispatch = None
        self._agenda_path = None

    def _meeting_already_running(self) -> bool:
        from tkinter import messagebox

        if self._require_orchestrator().binding is None:
            return False
        messagebox.showinfo(
            i18n.t("modules.meeting_buddy.dialog.title"),
            i18n.t("modules.meeting_buddy.dialog.already_running"),
        )
        return True

    def _start_meeting_flow(self) -> None:
        if self._meeting_already_running():
            return
        self._show_agenda_dialog(mode="start")

    def _start_meeting_quick_flow(self) -> None:
        from tkinter import messagebox

        if self._meeting_already_running():
            return
        orchestrator = self._require_orchestrator()
        if not can_start_meeting(orchestrator.agenda_text):
            messagebox.showinfo(
                i18n.t("modules.meeting_buddy.dialog.title"),
                i18n.t("modules.meeting_buddy.dialog.empty_agenda"),
            )
            self._show_agenda_dialog(mode="start")
            return
        self._begin_meeting()

    def _show_agenda_dialog(self, *, mode: str) -> None:
        from tkinter import messagebox

        orchestrator = self._require_orchestrator()
        app_dir = self._require_app_dir()
        result = show_agenda_dialog(
            agenda_text=orchestrator.agenda_text,
            path=self._agenda_path,
            app_dir=app_dir,
            mode=mode,  # type: ignore[arg-type]
        )
        if result is None:
            return

        orchestrator.set_agenda(result.agenda_text)
        self._agenda_path = result.path
        if result.path is not None:
            touch_recent(app_dir, result.path)

        if not result.start:
            return
        if not can_start_meeting(result.agenda_text):
            messagebox.showinfo(
                i18n.t("modules.meeting_buddy.dialog.title"),
                i18n.t("modules.meeting_buddy.dialog.empty_agenda"),
            )
            return
        self._begin_meeting()

    def _show_properties_dialog(self) -> None:
        orchestrator = self._require_orchestrator()
        app_dir = self._require_app_dir()
        result = show_properties_dialog(
            enable_loopback=orchestrator.loopback_requested,
            loopback_device=orchestrator.loopback_device,
        )
        if result is None:
            return
        save_meeting_buddy_preferences(
            app_dir,
            enable_loopback=result.enable_loopback,
            loopback_device=result.loopback_device,
        )
        orchestrator.reload_config()

    def _begin_meeting(self) -> None:
        from tkinter import messagebox

        orchestrator = self._require_orchestrator()
        app_dir = self._require_app_dir()
        if self._agenda_path is not None:
            touch_recent(app_dir, self._agenda_path)
        try:
            orchestrator.start()
        except RuntimeError as exc:
            messagebox.showerror(i18n.t("modules.meeting_buddy.dialog.title"), str(exc))

    def _on_ui_update(self, state: MeetingState) -> None:
        if self._ui_dispatch is None:
            return
        orchestrator = self._require_orchestrator()
        capture_status = orchestrator.capture_status
        transcription_status = orchestrator.transcription_status
        loopback_active = orchestrator.loopback_active
        loopback_requested = orchestrator.loopback_requested
        self._sync_recording_pill(capture_status)
        self._ui_dispatch(
            lambda: self._show_overlay_update(
                state,
                capture_status=capture_status,
                transcription_status=transcription_status,
                loopback_active=loopback_active,
                loopback_requested=loopback_requested,
            )
        )

    def _show_overlay_update(
        self,
        state: MeetingState,
        *,
        capture_status: object,
        transcription_status: object,
        loopback_active: bool | None = None,
        loopback_requested: bool = True,
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
            loopback_active=loopback_active,
            loopback_requested=loopback_requested,
        )

    def _close_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.close()
            self._overlay = None

    def _sync_recording_pill(self, capture_status: CaptureStatus) -> None:
        """Toon de opname-pill zolang Meeting Buddy microfooncapture actief is."""

        if capture_status == self._pill_capture_status:
            return

        previous = self._pill_capture_status
        self._pill_capture_status = capture_status
        recording_states = {
            CaptureStatus.ACTIVE,
            CaptureStatus.STARTING,
            CaptureStatus.RECONNECTING,
        }
        if capture_status in recording_states:
            if previous not in recording_states:
                reset_levels()
            notify_state(RecordingState.RECORDING, "meeting")
            return
        if capture_status == CaptureStatus.ERROR:
            notify_state(RecordingState.ERROR, "meeting")
            return
        if capture_status in {CaptureStatus.IDLE, CaptureStatus.STOPPED}:
            self._release_recording_pill()

    def _release_recording_pill(self) -> None:
        if self._pill_capture_status is None:
            return
        self._pill_capture_status = None
        notify_state(RecordingState.IDLE, "meeting")

    def _require_orchestrator(self) -> MeetingOrchestrator:
        if self._orchestrator is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        return self._orchestrator

    def _require_app_dir(self) -> Path:
        if self._app_dir is None:
            raise RuntimeError("Meeting Buddy module is niet gestart")
        return self._app_dir
