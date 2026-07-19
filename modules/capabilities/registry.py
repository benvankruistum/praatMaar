"""Capability registry — modules bieden services aan via stabiele ID's."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Any

log = logging.getLogger("praatmaar.capabilities")


class CapabilityUnavailableError(RuntimeError):
    """Opgevraagde capability ontbreekt of voldoet niet aan de contractversie."""


@dataclass(frozen=True)
class CapabilityRegistration:
    capability_id: str
    owner_module_id: str
    provider: Any
    contract_version: int = 1


class CapabilityRegistry:
    """Thread-safe registry: één provider per capability-ID (v1)."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._registrations: dict[str, CapabilityRegistration] = {}

    def register(
        self,
        capability_id: str,
        provider: object,
        owner_module_id: str,
        contract_version: int = 1,
    ) -> None:
        if not capability_id:
            raise ValueError("capability_id mag niet leeg zijn")
        if not owner_module_id:
            raise ValueError("owner_module_id mag niet leeg zijn")
        if provider is None:
            raise ValueError("provider mag niet None zijn")

        registration = CapabilityRegistration(
            capability_id=capability_id,
            owner_module_id=owner_module_id,
            provider=provider,
            contract_version=contract_version,
        )

        with self._lock:
            if capability_id in self._registrations:
                current = self._registrations[capability_id]
                log.warning(
                    "Capability %s already registered by %s (rejected for %s)",
                    capability_id,
                    current.owner_module_id,
                    owner_module_id,
                )
                raise ValueError(
                    f"Capability '{capability_id}' is al geregistreerd "
                    f"door module '{current.owner_module_id}'"
                )

            self._registrations[capability_id] = registration
            log.info(
                "Capability %s registered by %s (contract_version=%s)",
                capability_id,
                owner_module_id,
                contract_version,
            )

    def get(
        self,
        capability_id: str,
        minimum_contract_version: int | None = None,
    ) -> object | None:
        with self._lock:
            registration = self._registrations.get(capability_id)

        if registration is None:
            return None

        if (
            minimum_contract_version is not None
            and registration.contract_version < minimum_contract_version
        ):
            log.info(
                "Capability %s contract_version %s < required %s",
                capability_id,
                registration.contract_version,
                minimum_contract_version,
            )
            return None

        return registration.provider

    def require(
        self,
        capability_id: str,
        minimum_contract_version: int | None = None,
    ) -> object:
        provider = self.get(
            capability_id,
            minimum_contract_version=minimum_contract_version,
        )
        if provider is None:
            log.warning("Capability %s unavailable (require)", capability_id)
            raise CapabilityUnavailableError(f"Capability '{capability_id}' is niet beschikbaar")
        return provider

    def unregister(self, capability_id: str, owner_module_id: str) -> None:
        with self._lock:
            registration = self._registrations.get(capability_id)
            if registration is None:
                return
            if registration.owner_module_id != owner_module_id:
                raise ValueError(
                    f"Module '{owner_module_id}' is niet de eigenaar van "
                    f"capability '{capability_id}'"
                )
            del self._registrations[capability_id]
            log.info(
                "Capability %s removed with owner %s",
                capability_id,
                owner_module_id,
            )

    def unregister_owner(self, owner_module_id: str) -> None:
        with self._lock:
            owned = [
                capability_id
                for capability_id, registration in self._registrations.items()
                if registration.owner_module_id == owner_module_id
            ]
            for capability_id in owned:
                del self._registrations[capability_id]
                log.info(
                    "Capability %s removed with owner %s",
                    capability_id,
                    owner_module_id,
                )

    def list_available(self) -> list[CapabilityRegistration]:
        with self._lock:
            return list(self._registrations.values())
