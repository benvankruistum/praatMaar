"""Registratie-smoketest voor de ingebouwde audio-capturemodule."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

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


def test_shutdown_unregisters_capability_when_engine_shutdown_fails() -> None:
    module = AudioCaptureModule()
    engine = Mock()
    engine.shutdown.side_effect = RuntimeError("stream stop failed")
    capabilities = Mock()
    module._engine = engine
    module._capabilities = capabilities

    with pytest.raises(RuntimeError, match="stream stop failed"):
        module.on_app_shutdown()

    capabilities.unregister_owner.assert_called_once_with(module.id)
    assert module._engine is None
    assert module._capabilities is None
