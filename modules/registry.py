"""
ModuleRegistry — ingebouwde modules, lifecycle en enabled-state uit config.json.
"""

from __future__ import annotations

import traceback
from typing import Any

import host
from modules._builtin.audio_capture import AudioCaptureModule
from modules._builtin.inbox_mirror import InboxMirrorModule
from modules._builtin.speaker_detection import SpeakerDetectionModule
from modules._contract import (
    ModuleAction,
    ModuleContext,
    ModuleWithShutdown,
    PraatMaarModule,
    UiDispatch,
    module_actions,
    module_tray_actions,
    noop_ui_dispatch,
)
from modules.capabilities.registry import CapabilityRegistry
from modules.whisper import SharedWhisper


def all_builtin_modules() -> list[PraatMaarModule]:
    """Alle ingebouwde modules (v1: expliciete lijst, geen dynamic loading)."""

    return [InboxMirrorModule(), SpeakerDetectionModule(), AudioCaptureModule()]


def module_enabled(module: PraatMaarModule, modules_config: dict[str, Any]) -> bool:
    entry = modules_config.get(module.id)
    if isinstance(entry, dict) and "enabled" in entry:
        return bool(entry["enabled"])
    return module.default_enabled()


def load_enabled_modules(
    modules_config: dict[str, Any] | None = None,
    *,
    ui_dispatch: UiDispatch | None = None,
    whisper: SharedWhisper | None = None,
    capabilities: CapabilityRegistry | None = None,
) -> list[PraatMaarModule]:
    """Geeft enabled modules terug, na ``on_app_start``."""

    config = modules_config if modules_config is not None else {}
    dispatch = ui_dispatch if ui_dispatch is not None else noop_ui_dispatch
    shared = whisper if whisper is not None else SharedWhisper()
    caps = capabilities if capabilities is not None else CapabilityRegistry()
    ctx = ModuleContext(
        app_dir=host.app_dir(),
        ui_dispatch=dispatch,
        whisper=shared,
        capabilities=caps,
    )
    enabled: list[PraatMaarModule] = []

    for module in all_builtin_modules():
        if not module_enabled(module, config):
            continue
        module.on_app_start(ctx)
        enabled.append(module)

    return enabled


def shutdown_modules(
    modules: list[PraatMaarModule],
    *,
    capabilities: CapabilityRegistry | None = None,
) -> None:
    """Roept ``on_app_shutdown`` aan en verwijdert owned capabilities."""

    for module in modules:
        try:
            if isinstance(module, ModuleWithShutdown):
                module.on_app_shutdown()
        except Exception:
            print(f"Module {module.id} faalde bij afsluiten:")
            traceback.print_exc()
        finally:
            if capabilities is not None:
                capabilities.unregister_owner(module.id)


def run_module_action(modules: list[PraatMaarModule], module_id: str, action_id: str) -> bool:
    """Voert één module-actie uit. Retourneert True bij succes."""

    for module in modules:
        if module.id != module_id:
            continue
        for action in module_actions(module):
            if action.id == action_id:
                try:
                    action.handler()
                except Exception:
                    print(f"Module {module_id} actie {action_id} faalde:")
                    traceback.print_exc()
                return True
    return False


def tray_action_entries(
    modules: list[PraatMaarModule],
) -> list[tuple[PraatMaarModule, ModuleAction]]:
    """Alle tray-zichtbare acties van ingeschakelde modules."""

    entries: list[tuple[PraatMaarModule, ModuleAction]] = []
    for module in modules:
        for action in module_tray_actions(module):
            entries.append((module, action))
    return entries


def sanitize_modules_config(raw: Any) -> dict[str, dict[str, bool]]:
    """Normaliseert de `modules`-sectie uit config.json."""

    if not isinstance(raw, dict):
        return {}

    result: dict[str, dict[str, bool]] = {}
    known_ids = {module.id for module in all_builtin_modules()}

    for module_id, entry in raw.items():
        if module_id not in known_ids:
            continue
        if isinstance(entry, dict) and "enabled" in entry:
            result[module_id] = {"enabled": bool(entry["enabled"])}

    return result


def modules_config_for_settings(
    modules_config: dict[str, dict[str, bool]],
) -> dict[str, dict[str, bool]]:
    """Volledige modules-sectie voor UI (inclusief ontbrekende keys met defaults)."""

    result = dict(modules_config)
    for module in all_builtin_modules():
        if module.id not in result:
            result[module.id] = {"enabled": module.default_enabled()}
    return result
