"""Tests voor CapabilityRegistry."""

from __future__ import annotations

import threading

import pytest

from modules.capabilities.registry import (
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityUnavailableError,
)


def test_register_and_get() -> None:
    registry = CapabilityRegistry()
    provider = object()
    registry.register(
        "audio.speaker_detection",
        provider,
        owner_module_id="speaker-detection",
    )
    assert registry.get("audio.speaker_detection") is provider


def test_missing_returns_none() -> None:
    assert CapabilityRegistry().get("audio.speaker_detection") is None


def test_require_raises_when_missing() -> None:
    with pytest.raises(CapabilityUnavailableError, match="audio.speaker_detection"):
        CapabilityRegistry().require("audio.speaker_detection")


def test_require_returns_provider() -> None:
    registry = CapabilityRegistry()
    provider = object()
    registry.register("audio.x", provider, owner_module_id="m")
    assert registry.require("audio.x") is provider


def test_duplicate_registration_rejected() -> None:
    registry = CapabilityRegistry()
    registry.register("audio.x", object(), owner_module_id="a")
    with pytest.raises(ValueError, match="al geregistreerd"):
        registry.register("audio.x", object(), owner_module_id="b")


def test_unregister_wrong_owner_rejected() -> None:
    registry = CapabilityRegistry()
    registry.register("audio.x", object(), owner_module_id="a")
    with pytest.raises(ValueError, match="niet de eigenaar"):
        registry.unregister("audio.x", owner_module_id="b")


def test_unregister_owner_removes_only_owned() -> None:
    registry = CapabilityRegistry()
    a = object()
    b = object()
    registry.register("cap.a1", a, owner_module_id="mod-a")
    registry.register("cap.a2", a, owner_module_id="mod-a")
    registry.register("cap.b1", b, owner_module_id="mod-b")

    registry.unregister_owner("mod-a")

    assert registry.get("cap.a1") is None
    assert registry.get("cap.a2") is None
    assert registry.get("cap.b1") is b


def test_unregister_idempotent_when_missing() -> None:
    CapabilityRegistry().unregister("missing", owner_module_id="x")


def test_contract_version_filter() -> None:
    registry = CapabilityRegistry()
    provider = object()
    registry.register(
        "audio.x",
        provider,
        owner_module_id="m",
        contract_version=1,
    )
    assert registry.get("audio.x", minimum_contract_version=1) is provider
    assert registry.get("audio.x", minimum_contract_version=2) is None
    with pytest.raises(CapabilityUnavailableError):
        registry.require("audio.x", minimum_contract_version=2)


def test_list_available() -> None:
    registry = CapabilityRegistry()
    registry.register("a", object(), owner_module_id="m", contract_version=3)
    items = registry.list_available()
    assert len(items) == 1
    assert isinstance(items[0], CapabilityRegistration)
    assert items[0].capability_id == "a"
    assert items[0].contract_version == 3


def test_validation_rejects_empty_ids_and_none_provider() -> None:
    registry = CapabilityRegistry()
    with pytest.raises(ValueError):
        registry.register("", object(), owner_module_id="m")
    with pytest.raises(ValueError):
        registry.register("x", object(), owner_module_id="")
    with pytest.raises(ValueError):
        registry.register("x", None, owner_module_id="m")  # type: ignore[arg-type]


def test_concurrent_register_get_unregister() -> None:
    registry = CapabilityRegistry()
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            for i in range(50):
                cid = f"cap.{i % 5}"
                try:
                    registry.register(cid, object(), owner_module_id="w")
                except ValueError:
                    pass
                registry.unregister_owner("w")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(100):
                registry.get("cap.0")
                registry.list_available()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(4)] + [
        threading.Thread(target=reader) for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert errors == []
