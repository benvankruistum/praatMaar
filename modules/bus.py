"""
ModuleBus — verdeelt dicteercyclus-events naar modules en het event-journal.
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from modules._contract import CycleEvent
from modules.journal import EventJournal

if TYPE_CHECKING:
    from modules._contract import PraatMaarModule


class ModuleBus:
    """Centrale emitter: journal altijd; enabled modules best-effort."""

    def __init__(
        self,
        *,
        journal: EventJournal | None = None,
        modules: list[PraatMaarModule] | None = None,
    ) -> None:
        self._journal = journal or EventJournal()
        self._modules: list[PraatMaarModule] = list(modules or [])

    def set_modules(self, modules: list[PraatMaarModule]) -> None:
        self._modules = list(modules)

    def emit(self, event: CycleEvent) -> None:
        try:
            self._journal.write(event)
        except OSError as exc:
            print(f"Event-journal schrijffout: {exc}")

        for module in self._modules:
            try:
                module.on_event(event)
            except Exception:
                print(f"Module {module.id} faalde op {event.type}:")
                traceback.print_exc()
