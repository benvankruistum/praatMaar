"""Gedeelde capability-contracten (geen concrete module-implementaties)."""

from modules.capabilities.registry import (
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityUnavailableError,
)

__all__ = [
    "CapabilityRegistration",
    "CapabilityRegistry",
    "CapabilityUnavailableError",
]
