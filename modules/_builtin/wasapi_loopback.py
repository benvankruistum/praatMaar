"""
WASAPI loopback capture via PyAudioWPatch (Windows).

``sounddevice`` 0.5.x heeft geen ``WasapiSettings(loopback=True)``. Deze module
opent echte WASAPI-loopback-apparaten zodat Meeting Buddy het gekozen
*uitvoer*apparaat kan meenemen (niet alleen Stereo Mix).
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from typing import Any

import numpy as np

log = logging.getLogger("praatmaar.wasapi_loopback")

AudioCallback = Callable[[np.ndarray, int, Any, Any], None]
FinishedCallback = Callable[[], None]


def is_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import pyaudiowpatch  # noqa: F401
    except ImportError:
        return False
    return True


def _pyaudio() -> Any:
    import pyaudiowpatch as pyaudio

    return pyaudio.PyAudio()


def list_loopback_output_devices(
    *,
    default_label: str,
    pyaudio_factory: Callable[[], Any] | None = None,
) -> list[tuple[str, int | None]]:
    """
    Return ``(label, loopback_input_index)`` pairs.

    ``None`` = Windows default WASAPI loopback. Labels zijn de uitvoernaam
    zonder ``[Loopback]``-suffix.
    """

    if not is_available() and pyaudio_factory is None:
        return [(default_label, None)]

    options: list[tuple[str, int | None]] = [(default_label, None)]
    pa = (pyaudio_factory or _pyaudio)()
    try:
        seen: set[str] = set()
        for device in pa.get_loopback_device_info_generator():
            name = str(device.get("name") or "").replace(" [Loopback]", "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            options.append((name, int(device["index"])))
    except Exception as exc:
        log.warning("WASAPI loopback-apparaten opsommen mislukt: %s", exc)
        return [(default_label, None)]
    finally:
        try:
            pa.terminate()
        except Exception:
            pass
    return options


def resolve_loopback_device_info(
    loopback_device: int | None,
    *,
    pyaudio_instance: Any | None = None,
) -> dict[str, Any]:
    """Resolve configured index (or default) to a loopback device info dict."""

    owns = pyaudio_instance is None
    if owns:
        import pyaudiowpatch as pyaudio

        pa = pyaudio.PyAudio()
    else:
        pa = pyaudio_instance
    try:
        if loopback_device is None:
            return dict(pa.get_default_wasapi_loopback())

        info = dict(pa.get_device_info_by_index(int(loopback_device)))
        if info.get("isLoopbackDevice"):
            return info
        # Legacy/sounddevice-index of gewone output: zoek loopback-analoog.
        analogue = pa.get_wasapi_loopback_analogue_by_dict(info)
        if analogue is None:
            raise LookupError(f"Geen WASAPI-loopback voor device {loopback_device}")
        return dict(analogue)
    finally:
        if owns:
            try:
                pa.terminate()
            except Exception:
                pass


class WasapiLoopbackStream:
    """
    Dunne stream-wrapper met sounddevice-achtige ``start``/``stop``/``close``.

    De callback-signatuur is gelijk aan sounddevice:
    ``callback(indata, frames, time_info, status)`` met ``indata`` shape
    ``(frames, channels)`` float32.
    """

    def __init__(
        self,
        *,
        device_info: dict[str, Any],
        callback: AudioCallback,
        finished_callback: FinishedCallback | None = None,
        frames_per_buffer: int = 512,
        pyaudio_factory: Callable[[], Any] | None = None,
    ) -> None:
        import pyaudiowpatch as pyaudio

        self._pyaudio_mod = pyaudio
        self._callback = callback
        self._finished_callback = finished_callback
        self._frames_per_buffer = frames_per_buffer
        self._device_info = device_info
        self._channels = max(1, int(device_info.get("maxInputChannels") or 2))
        self.sample_rate = int(device_info.get("defaultSampleRate") or 48000)
        self._pa = (pyaudio_factory or (lambda: pyaudio.PyAudio()))()
        self._stream: Any | None = None
        self._closed = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("WASAPI loopback stream is gesloten")
            if self._stream is not None:
                if not self._stream.is_active():
                    self._stream.start_stream()
                return

            pyaudio = self._pyaudio_mod

            def _pa_callback(in_data: bytes, frame_count: int, time_info: Any, status: Any):
                try:
                    audio = np.frombuffer(in_data, dtype=np.float32)
                    if audio.size != frame_count * self._channels:
                        audio = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
                    indata = audio.reshape(frame_count, self._channels)
                    self._callback(indata, frame_count, time_info, status)
                except Exception:
                    log.exception("WASAPI loopback callback faalde")
                    if self._finished_callback is not None:
                        try:
                            self._finished_callback()
                        except Exception:
                            pass
                    return (None, pyaudio.paAbort)
                return (None, pyaudio.paContinue)

            self._stream = self._pa.open(
                format=pyaudio.paFloat32,
                channels=self._channels,
                rate=self.sample_rate,
                frames_per_buffer=self._frames_per_buffer,
                input=True,
                input_device_index=int(self._device_info["index"]),
                stream_callback=_pa_callback,
            )
            self._stream.start_stream()

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            if stream is None:
                return
            try:
                if stream.is_active():
                    stream.stop_stream()
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                if stream.is_active():
                    stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        try:
            self._pa.terminate()
        except Exception:
            pass
