"""Registratie-smoketest voor de ingebouwde audio-capturemodule."""

from __future__ import annotations

from pathlib import Path

from modules._builtin.audio_capture import AudioCaptureModule
from modules._contract import ModuleContext
from modules.capabilities.continuous_capture import CAPABILITY_ID
from modules.capabilities.registry import CapabilityRegistry


def test_module_registers_capability() -> None:
    capabilities = CapabilityRegistry()
    module = AudioCaptureModule()
    context = ModuleContext(
        app_dir=Path("."),
        ui_dispatch=lambda function: function(),
        capabilities=capabilities,
    )

    module.on_app_start(context)

    assert capabilities.get(CAPABILITY_ID) is not None
