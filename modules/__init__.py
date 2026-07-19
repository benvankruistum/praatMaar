"""praatMaar module-systeem — in-process hooks + event-journal voor externe tools."""

from modules._contract import (
    SCHEMA_VERSION,
    CycleEvent,
    CycleEventType,
    ModuleContext,
    PraatMaarModule,
)
from modules.bus import ModuleBus
from modules.journal import EventJournal, events_dir, events_journal_path
from modules.registry import (
    all_builtin_modules,
    load_enabled_modules,
    module_enabled,
    modules_config_for_settings,
    sanitize_modules_config,
)

__all__ = [
    "CycleEvent",
    "CycleEventType",
    "EventJournal",
    "ModuleBus",
    "ModuleContext",
    "PraatMaarModule",
    "SCHEMA_VERSION",
    "all_builtin_modules",
    "events_dir",
    "events_journal_path",
    "load_enabled_modules",
    "module_enabled",
    "modules_config_for_settings",
    "sanitize_modules_config",
]
