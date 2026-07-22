"""
Gedeeld contract voor praatMaar-modules en dicteercyclus-events.

Platform-neutraal: geen GUI, geen OS-API. Modules en het event-journal
delen dezelfde `CycleEvent`-payload.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from modules.capabilities.registry import CapabilityRegistry
from modules.whisper import SharedWhisper

SCHEMA_VERSION = 1

UiDispatch = Callable[[Callable[[], None]], None]
"""Plan een callable op de UI-thread (tkinter / Cocoa main)."""


class CycleEventType(StrEnum):
    """Lifecycle-events van één dicteercyclus (of herstel-transcriptie)."""

    CYCLE_STARTED = "cycle.started"
    CYCLE_CANCELLED = "cycle.cancelled"
    CYCLE_TRANSCRIBING = "cycle.transcribing"
    TRANSCRIPT_PARTIAL = "transcript.partial"
    CYCLE_COMPLETED = "cycle.completed"
    TRANSCRIPT_SAVED = "transcript.saved"
    CYCLE_ERROR = "cycle.error"
    CYCLE_IDLE = "cycle.idle"
    DESTINATION_COMMAND = "destination.command"
    RECOVERY_RETRANSCRIBED = "recovery.retranscribed"


@dataclass(frozen=True)
class CycleEvent:
    """Één event in de dicteercyclus — zelfde vorm voor bus, journal en modules."""

    type: CycleEventType
    session_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    transcript: str | None = None
    path: str | None = None
    destination: str | None = None
    language: str | None = None
    mode: str | None = None
    error: str | None = None
    recovery_path: str | None = None
    destination_command: str | None = None
    destination_name: str | None = None
    source: str = "live"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "type": str(self.type),
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "source": self.source,
        }
        if self.transcript is not None:
            payload["transcript"] = self.transcript
        if self.path is not None:
            payload["path"] = self.path
        if self.destination is not None:
            payload["destination"] = self.destination
        if self.language is not None:
            payload["language"] = self.language
        if self.mode is not None:
            payload["mode"] = self.mode
        if self.error is not None:
            payload["error"] = self.error
        if self.recovery_path is not None:
            payload["recovery_path"] = self.recovery_path
        if self.destination_command is not None:
            payload["destination_command"] = self.destination_command
        if self.destination_name is not None:
            payload["destination_name"] = self.destination_name
        return payload


@dataclass(frozen=True)
class ModuleContext:
    """Context die modules bij opstarten krijgen."""

    app_dir: Path
    ui_dispatch: UiDispatch
    whisper: SharedWhisper = field(default_factory=SharedWhisper)
    """Gedeeld Faster-Whisper-model (+ lock) met de dicteercyclus."""
    capabilities: CapabilityRegistry = field(default_factory=CapabilityRegistry)
    """Gedeelde capability-registry (zelfde instantie voor alle modules)."""

    def module_dir(self, module_id: str) -> Path:
        """Datamap voor één module (mapnaam = kebab-case id)."""

        from modules.settings_store import module_dir as _module_dir

        return _module_dir(self.app_dir, module_id)


@dataclass(frozen=True)
class ModuleAction:
    """Eén gebruikersactie die een module aanbiedt."""

    id: str
    label_key: str
    handler: Callable[[], None]
    in_tray: bool = False
    """True → ook onder tray → Modules (submenu)."""
    in_tray_root: bool = False
    """True → direct in het tray-contextmenu (topniveau)."""


class PraatMaarModule(Protocol):
    """In-process module: reageert op dicteercyclus-events."""

    @property
    def id(self) -> str: ...

    def display_name_key(self) -> str: ...

    def description_key(self) -> str: ...

    def default_enabled(self) -> bool: ...

    def on_app_start(self, ctx: ModuleContext) -> None: ...

    def on_event(self, event: CycleEvent) -> None: ...


@runtime_checkable
class ModuleWithActions(Protocol):
    """Optioneel: module biedt acties aan (Modules-dialoog, optioneel tray)."""

    def actions(self) -> list[ModuleAction]: ...


@runtime_checkable
class ModuleWithShutdown(Protocol):
    """Optioneel: module ruimt op bij afsluiten praatMaar."""

    def on_app_shutdown(self) -> None: ...


def module_actions(module: PraatMaarModule) -> list[ModuleAction]:
    """Acties van een module, of lege lijst als niet ondersteund."""

    if not isinstance(module, ModuleWithActions):
        return []
    return list(module.actions())


def module_tray_actions(module: PraatMaarModule) -> list[ModuleAction]:
    """Acties die in het tray → Modules-submenu mogen verschijnen."""

    return [action for action in module_actions(module) if action.in_tray]


def module_tray_root_actions(module: PraatMaarModule) -> list[ModuleAction]:
    """Acties die direct in het tray-contextmenu mogen verschijnen."""

    return [action for action in module_actions(module) if action.in_tray_root]


def noop_ui_dispatch(fn: Callable[[], None]) -> None:
    """Fallback: voer direct uit (tests, vóór indicator beschikbaar is)."""

    fn()
