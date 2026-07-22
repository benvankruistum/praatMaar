"""praatMaar module-systeem — in-process hooks + event-journal voor externe tools."""

from modules._contract import (
    SCHEMA_VERSION,
    CycleEvent,
    CycleEventType,
    ModuleAction,
    ModuleContext,
    ModuleWithActions,
    ModuleWithShutdown,
    PraatMaarModule,
    UiDispatch,
    module_actions,
    module_tray_actions,
    module_tray_root_actions,
    noop_ui_dispatch,
)
from modules.bus import ModuleBus
from modules.capabilities.registry import (
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityUnavailableError,
)
from modules.journal import EventJournal, events_dir, events_journal_path
from modules.registry import (
    all_builtin_modules,
    load_enabled_modules,
    module_enabled,
    modules_config_for_settings,
    run_module_action,
    sanitize_modules_config,
    shutdown_modules,
    tray_action_entries,
    tray_root_action_entries,
)
from modules.settings_store import config_path, load_config, module_dir, save_config
from modules.whisper import SharedWhisper

__all__ = [
    "CapabilityRegistration",
    "CapabilityRegistry",
    "CapabilityUnavailableError",
    "CycleEvent",
    "CycleEventType",
    "EventJournal",
    "ModuleAction",
    "ModuleBus",
    "ModuleContext",
    "ModuleWithActions",
    "ModuleWithShutdown",
    "PraatMaarModule",
    "SCHEMA_VERSION",
    "SharedWhisper",
    "UiDispatch",
    "all_builtin_modules",
    "config_path",
    "events_dir",
    "events_journal_path",
    "load_config",
    "load_enabled_modules",
    "module_actions",
    "module_dir",
    "module_enabled",
    "module_tray_actions",
    "module_tray_root_actions",
    "modules_config_for_settings",
    "noop_ui_dispatch",
    "run_module_action",
    "sanitize_modules_config",
    "save_config",
    "shutdown_modules",
    "tray_action_entries",
    "tray_root_action_entries",
]
