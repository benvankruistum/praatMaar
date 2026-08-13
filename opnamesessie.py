"""Compatibility façade: Opnamesessie leeft in `dicteercyclus`."""

from __future__ import annotations

import sys
import time

from dicteercyclus import CycleTiming, Opnamesessie, format_cycle_timing
from mic_errors import refresh_portaudio
from modules._contract import CycleEventType

__all__ = [
    "CycleEventType",
    "CycleTiming",
    "Opnamesessie",
    "format_cycle_timing",
    "refresh_portaudio",
    "sys",
    "time",
]
