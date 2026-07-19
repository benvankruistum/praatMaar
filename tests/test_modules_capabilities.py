"""Tests voor module capabilities — acties, shutdown, settings store."""

from __future__ import annotations

from pathlib import Path

from modules._contract import (
    ModuleAction,
    ModuleContext,
    ModuleWithActions,
    ModuleWithShutdown,
    module_actions,
    module_tray_actions,
    noop_ui_dispatch,
)
from modules.bus import ModuleBus
from modules.registry import (
    load_enabled_modules,
    run_module_action,
    shutdown_modules,
    tray_action_entries,
)
from modules.settings_store import load_config, save_config
from modules.whisper import SharedWhisper


class ActionModule:
    id = "demo-actions"

    def __init__(self) -> None:
        self.ran: list[str] = []
        self.started = False
        self.shutdown = False

    def display_name_key(self) -> str:
        return "modules.demo.name"

    def description_key(self) -> str:
        return "modules.demo.description"

    def default_enabled(self) -> bool:
        return True

    def on_app_start(self, ctx: ModuleContext) -> None:
        self.started = True
        self.ctx = ctx

    def on_event(self, event) -> None:
        pass

    def actions(self) -> list[ModuleAction]:
        return [
            ModuleAction(
                id="open",
                label_key="modules.demo.open",
                handler=lambda: self.ran.append("open"),
            ),
            ModuleAction(
                id="tray-only",
                label_key="modules.demo.tray",
                handler=lambda: self.ran.append("tray"),
                in_tray=True,
            ),
        ]

    def on_app_shutdown(self) -> None:
        self.shutdown = True


def test_module_context_ui_dispatch(tmp_path: Path) -> None:
    ran: list[str] = []

    def dispatch(fn) -> None:
        ran.append("queued")
        fn()

    ctx = ModuleContext(app_dir=tmp_path, ui_dispatch=dispatch)
    ctx.ui_dispatch(lambda: ran.append("work"))
    assert ran == ["queued", "work"]
    assert ctx.module_dir("demo-actions") == tmp_path / "demo-actions"


def test_module_actions_and_tray_filter() -> None:
    module = ActionModule()
    assert len(module_actions(module)) == 2
    assert len(module_tray_actions(module)) == 1
    assert module_tray_actions(module)[0].id == "tray-only"
    assert isinstance(module, ModuleWithActions)
    assert isinstance(module, ModuleWithShutdown)


def test_run_module_action_and_shutdown() -> None:
    module = ActionModule()
    assert run_module_action([module], "demo-actions", "open") is True
    assert module.ran == ["open"]
    assert run_module_action([module], "demo-actions", "missing") is False

    shutdown_modules([module])
    assert module.shutdown is True


def test_tray_action_entries() -> None:
    module = ActionModule()
    entries = tray_action_entries([module])
    assert len(entries) == 1
    assert entries[0][1].id == "tray-only"


def test_module_bus_shutdown_and_run_action() -> None:
    module = ActionModule()
    bus = ModuleBus(modules=[module])
    assert bus.run_action("demo-actions", "open") is True
    assert module.ran == ["open"]
    bus.shutdown()
    assert module.shutdown is True


def test_settings_store_roundtrip(tmp_path: Path) -> None:
    save_config(tmp_path, "meeting-buddy", {"mic": "default", "keep": True})
    assert load_config(tmp_path, "meeting-buddy") == {"mic": "default", "keep": True}
    assert load_config(tmp_path, "missing", default={"x": 1}) == {"x": 1}


def test_load_enabled_modules_passes_shared_whisper(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("host.app_dir", lambda: tmp_path)
    whisper = SharedWhisper()
    whisper.set_model(object())

    captured: list[ModuleContext] = []

    class Probe:
        id = "inbox-mirror"

        def display_name_key(self) -> str:
            return "modules.inbox_mirror.name"

        def description_key(self) -> str:
            return "modules.inbox_mirror.description"

        def default_enabled(self) -> bool:
            return True

        def on_app_start(self, ctx: ModuleContext) -> None:
            captured.append(ctx)

        def on_event(self, event) -> None:
            pass

    monkeypatch.setattr(
        "modules.registry.all_builtin_modules",
        lambda: [Probe()],
    )
    modules = load_enabled_modules(
        {"inbox-mirror": {"enabled": True}},
        ui_dispatch=noop_ui_dispatch,
        whisper=whisper,
    )
    assert len(modules) == 1
    assert captured[0].whisper is whisper
    assert captured[0].whisper.is_ready
