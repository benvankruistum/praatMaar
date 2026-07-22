"""Tests for Meeting Buddy properties dialog."""

from __future__ import annotations

import dataclasses

import pytest

from modules._builtin.meeting_buddy.properties_dialog import (
    PropertiesResult,
    build_properties_result,
    device_selection_maps,
    show_properties_dialog,
)


def test_properties_result_fields() -> None:
    result = PropertiesResult(enable_loopback=True, loopback_device=3)
    assert result.enable_loopback is True
    assert result.loopback_device == 3


def test_properties_result_is_frozen() -> None:
    result = PropertiesResult(enable_loopback=False, loopback_device=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.enable_loopback = True  # type: ignore[misc]


def test_module_exports_show_properties_dialog() -> None:
    assert callable(show_properties_dialog)


def test_device_selection_maps_current_device() -> None:
    devices = [("Default", None), ("1: Speakers", 1), ("2: Headphones", 2)]
    labels, value_by_label, label_by_value, current = device_selection_maps(devices, 2)
    assert labels == ["Default", "1: Speakers", "2: Headphones"]
    assert value_by_label["2: Headphones"] == 2
    assert label_by_value[2] == "2: Headphones"
    assert current == "2: Headphones"


def test_device_selection_maps_falls_back_to_first_label() -> None:
    devices = [("Default", None), ("1: Speakers", 1)]
    _, _, _, current = device_selection_maps(devices, 99)
    assert current == "Default"


def test_build_properties_result_loopback_enabled() -> None:
    mapping = {"Default": None, "1: Speakers": 1}
    result = build_properties_result(
        enable_loopback=True,
        selected_device_label="1: Speakers",
        device_value_by_label=mapping,
        fallback_device=None,
    )
    assert result == PropertiesResult(enable_loopback=True, loopback_device=1)


def test_build_properties_result_loopback_disabled_clears_device() -> None:
    mapping = {"1: Speakers": 1}
    result = build_properties_result(
        enable_loopback=False,
        selected_device_label="1: Speakers",
        device_value_by_label=mapping,
        fallback_device=1,
    )
    assert result == PropertiesResult(enable_loopback=False, loopback_device=None)


def test_show_properties_dialog_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()

    monkeypatch.setattr(
        "modules._builtin.meeting_buddy.properties_dialog.list_loopback_output_devices",
        lambda: [("Default", None)],
    )

    original_topllevel = tk.Toplevel

    def patched_topllevel(*args, **kwargs):
        dlg = original_topllevel(*args, **kwargs)
        cancel_handler = None
        original_protocol = dlg.protocol

        def protocol(name, handler):
            nonlocal cancel_handler
            if name == "WM_DELETE_WINDOW":
                cancel_handler = handler
            return original_protocol(name, handler)

        dlg.protocol = protocol

        def wait_window():
            if cancel_handler is not None:
                cancel_handler()

        dlg.wait_window = wait_window
        return dlg

    monkeypatch.setattr(tk, "Toplevel", patched_topllevel)

    try:
        result = show_properties_dialog(
            enable_loopback=True,
            loopback_device=None,
            parent=root,
        )
    finally:
        root.destroy()
    assert result is None
