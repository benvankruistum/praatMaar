"""
ModuleRegistry — ingebouwde modules en enabled-state uit config.json.
"""

from __future__ import annotations

from typing import Any

import host
from modules._builtin.inbox_mirror import InboxMirrorModule
from modules._contract import ModuleContext, PraatMaarModule


def all_builtin_modules() -> list[PraatMaarModule]:
    """Alle ingebouwde modules (v1: expliciete lijst, geen dynamic loading)."""

    return [InboxMirrorModule()]


def module_enabled(module: PraatMaarModule, modules_config: dict[str, Any]) -> bool:
    entry = modules_config.get(module.id)
    if isinstance(entry, dict) and "enabled" in entry:
        return bool(entry["enabled"])
    return module.default_enabled()


def load_enabled_modules(modules_config: dict[str, Any] | None = None) -> list[PraatMaarModule]:
    """Geeft enabled modules terug, na `on_app_start`."""

    config = modules_config if modules_config is not None else {}
    ctx = ModuleContext(app_dir=host.app_dir())
    enabled: list[PraatMaarModule] = []

    for module in all_builtin_modules():
        if not module_enabled(module, config):
            continue
        module.on_app_start(ctx)
        enabled.append(module)

    return enabled


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
