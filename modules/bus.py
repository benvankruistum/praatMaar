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

    @property
    def modules(self) -> tuple[PraatMaarModule, ...]:
        return tuple(self._modules)

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

    def shutdown(self) -> None:
        """Ruimt alle geladen modules op (``on_app_shutdown``)."""

        from modules.registry import shutdown_modules

        shutdown_modules(self._modules)

    def run_action(self, module_id: str, action_id: str) -> bool:
        from modules.registry import run_module_action

        return run_module_action(self._modules, module_id, action_id)
