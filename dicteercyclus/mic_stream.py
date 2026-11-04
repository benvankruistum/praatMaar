"""Warm mic, stream open/close, lazy rebind en PortAudio-refresh."""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

import i18n
from mic_errors import (
    device_identity,
    first_input_device_index,
    format_recording_start_error,
    refresh_portaudio,
)

# Eén audiobuffer is genoeg om CallbackAbort te laten landen. Langer wachten
# houdt de sneltoets-thread vast terwijl de stream al stopt.
_STREAM_ABORT_GRACE_S = 0.3
# Pa_StopStream / Pa_AbortStream mogen de Qt-thread niet vasthouden. Op macOS
# deadlockt die call soms tegen de CoreAudio-IO-thread.
_STREAM_STOP_JOIN_S = 1.0


class _StreamHalt:
    """Sein naar de audiocallback: stop de stream daar, niet via Pa_StopStream."""

    def __init__(self) -> None:
        self.requested = False


class MicStreamMixin:
    def warmup_microphone(self) -> bool:
        """
        Opent de microfoonstream alvast (na model-load).

        Alleen als `warm_microphone` aan staat (en niet op macOS). Zonder
        warmup kost de eerste InputStream.open op Windows vaak 0,5–2 s
        (zeker Bluetooth). Op macOS nooit warm: anders blijft de systeembrede
        mic-indicator permanent in de menubalk staan.

        Retourneert True als de microfoon bruikbaar is (of warm houden uit staat
        en een stille probe slaagt).
        """

        if not self._keep_stream_warm():
            return True

        try:
            self._ensure_stream()
            print(i18n.t("mic.warm"))
            if self._on_mic_ready is not None:
                self._on_mic_ready()
            return True
        except Exception as exc:
            # Warmup is best-effort: geen dialoog (GUI bestaat vaak nog niet).
            print(i18n.t("mic.warm_failed", error=exc))
            print(format_recording_start_error(exc))
            return False

    def probe_microphone(self) -> bool:
        """Controleert stilletjes of een inputstream geopend kan worden."""

        try:
            self._ensure_stream()
            if self._on_mic_ready is not None:
                self._on_mic_ready()
            return True
        except Exception:
            return False
        finally:
            if not self._keep_stream_warm():
                self.stop_audio_stream()

    def _keep_stream_warm(self) -> bool:
        """Effectief warm houden: user-optie, nooit op macOS (menubalk-indicator)."""

        return bool(self.warm_microphone) and sys.platform != "darwin"

    def _release_stream_if_cold(self) -> None:
        """Sluit de stream na een sessie tenzij warm houden aan staat."""

        if not self._keep_stream_warm():
            self.stop_audio_stream()

    def refresh_input_device(self) -> None:
        """Sluit de warme stream zodat een gewijzigde microfoon opnieuw opent."""

        self.stop_audio_stream()

    def _require_audio(self) -> tuple[Any, Any, Any]:
        if self._np is None or self._sd is None or self._write_wav is None:
            raise RuntimeError("Audio-libraries zijn nog niet gekoppeld (bind_audio).")
        return self._np, self._sd, self._write_wav

    def _stream_is_alive(self) -> bool:
        """True als de warme InputStream nog bruikbaar lijkt."""

        stream = self._audio_stream
        if stream is None:
            return False
        if not getattr(stream, "active", True):
            return False

        now = time.monotonic()
        opened_at = self._stream_opened_at
        if opened_at is not None and (now - opened_at) < self._stream_stale_after_seconds:
            # Net geopend: wacht op eerste callbacks.
            return True

        last = self._last_audio_callback_at
        if last is None:
            return False
        return (now - last) <= self._stream_stale_after_seconds

    def _ensure_stream(self) -> None:
        """Start één InputStream als die nog niet loopt. Heropent dode of stale warme streams."""

        if self._audio_stream is not None and not self._stream_is_alive():
            self.stop_audio_stream()

        if self._audio_stream is not None:
            # Peek zonder refresh_portaudio: terminate zou de eigen warme stream killen.
            _, sd_peek, _ = self._require_audio()
            desired = self._desired_device_identity(sd_peek)
            bound = self._bound_device_identity
            if desired is not None and bound is not None and desired == bound:
                return
            if desired is None and bound is None:
                # Geen identity beschikbaar (bijv. query faalt): warme stream houden.
                return
            if desired is not None and bound is None:
                # Stream leeft al; identity alsnog vastleggen zonder reopen.
                self._bound_device_identity = desired
                return
            self.stop_audio_stream()

        with self._lock:
            if self._audio_stream is not None:
                return

        _, sd, _ = self._require_audio()
        # Bluetooth/hotplug: herenumereren vóór open (geen eigen stream hier).
        self._refresh_portaudio_if_safe(sd)

        device = self._resolve_input_device(sd)
        try:
            self._open_input_stream(sd, device)
        except Exception as first_exc:
            # Stale default (-1) of oude index: opnieuw enumereren + concrete mic.
            self._refresh_portaudio_if_safe(sd)
            device = self._resolve_input_device(sd)
            if device is None:
                device = first_input_device_index(sd)
            if device is None:
                raise first_exc
            self._open_input_stream(sd, device)

    def _desired_device_identity(self, sd: Any) -> tuple[str, int] | None:
        """Identity die we nu willen binden (na preference-clear indien nodig)."""

        resolved = self._resolve_input_device(sd)
        return device_identity(sd, resolved)

    def _refresh_portaudio_if_safe(self, sd: Any) -> bool:
        """Herenumereer PortAudio alleen als er app-breed geen streams open zijn.

        ``refresh_portaudio`` doet ``_terminate()`` tot PortAudio uit is; met een
        actieve module-stream (Meeting Buddy-capture op dezelfde sounddevice-
        module) trekt dat die stream eronder weg — dode streams of een native
        crash. Overslaan kost alleen hotplug-detectie voor deze start.
        """

        if self._has_external_streams is not None:
            try:
                if self._has_external_streams():
                    return False
            except Exception:
                # Onbekende toestand: niet herinitialiseren (veilige kant).
                return False
        refresh_portaudio(sd)
        return True

    def _open_input_stream(self, sd: Any, device: int | None) -> None:
        """Opent en start een InputStream; koppelt die aan de sessie."""

        # latency='low': kleinere buffers, snellere eerste callback na start.
        halt = _StreamHalt()
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._stream_callback(halt),
            device=device,
            latency="low",
        )
        stream.start()

        with self._lock:
            if self._audio_stream is not None:
                extra = True
            else:
                extra = False
                self._audio_stream = stream
                self._stream_halt = halt
                self._stream_opened_at = time.monotonic()
                self._last_audio_callback_at = None
                self._bound_device_identity = device_identity(sd, device)
        if extra:
            # Parallel geopend — onze stream is overbodig.
            halt.requested = True
            self._close_stream(stream, halt)

    def _stream_callback(self, halt: _StreamHalt):
        """Audiocallback die de stream zelf laat stoppen als daarom gevraagd is.

        sounddevice zet ``CallbackAbort`` om in PortAudio ``paAbort``. Daarmee
        stopt het apparaat op de IO-thread. ``Pa_StopStream`` vanaf de
        sneltoets-thread deadlockt op macOS soms tegen diezelfde IO-thread
        (``AudioDeviceStop`` wacht op een HAL-lock die ``startStopCallback``
        ook pakt).
        """

        def callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            self.audio_callback(indata, frames, time_info, status)
            if not halt.requested:
                return
            abort = getattr(self._sd, "CallbackAbort", None)
            if isinstance(abort, type) and issubclass(abort, BaseException):
                raise abort

        return callback

    def audio_callback(
        self,
        indata: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        """sounddevice-callback: buffer + RMS voor de indicator (alleen tijdens opname)."""

        self._last_audio_callback_at = time.monotonic()

        np = self._np
        if status:
            print("\n" + i18n.t("rec.audio_warning", status=status))

        with self._lock:
            is_recording = self._recording
            if is_recording:
                self._audio_chunks.append(indata.copy())

        if is_recording and frames > 0 and np is not None:
            self._push_level(float(np.sqrt(np.mean(np.square(indata)))))

    def _resolve_input_device(self, sd: Any) -> int | None:
        """
        Geeft een bruikbaar input-device terug, of None (= Windows-standaard).

        Device-indexen op Windows schuiven (Bluetooth, docks). Een oude index
        kan later een pure output zijn → PortAudio -9996 Invalid device.
        """

        chosen = self.microphone_device
        if chosen is None:
            return None

        try:
            info = sd.query_devices(chosen)
        except Exception as exc:
            print(i18n.t("rec.device_invalid", device=chosen, error=exc))
            self.microphone_device = None
            return None

        if int(info.get("max_input_channels", 0) or 0) <= 0:
            print(
                i18n.t(
                    "rec.device_no_input",
                    device=chosen,
                    name=info.get("name", "?"),
                )
            )
            self.microphone_device = None
            return None

        return chosen

    def stop_audio_stream(self) -> None:
        """Stopt en sluit de microfoonstream.

        De aanroeper (op macOS de Qt-sneltoets) wacht begrensd. Een vastgelopen
        ``Pa_StopStream`` mag de pill en de transcriptie niet meenemen.
        """

        with self._lock:
            stream = self._audio_stream
            halt = getattr(self, "_stream_halt", None)
            self._audio_stream = None
            self._stream_halt = None
            self._stream_opened_at = None
            self._last_audio_callback_at = None
            self._bound_device_identity = None
            if halt is not None:
                halt.requested = True

        if stream is None:
            return

        self._close_stream(stream, halt)

    def _close_stream(self, stream: Any, halt: _StreamHalt | None) -> None:
        worker = threading.Thread(
            target=self._close_stream_worker,
            args=(stream, halt),
            daemon=True,
            name="praatmaar-mic-stop",
        )
        worker.start()
        timeout = float(getattr(self, "_stream_stop_join_seconds", _STREAM_STOP_JOIN_S))
        worker.join(timeout)
        if worker.is_alive():
            print(i18n.t("rec.mic_stop_timeout"))

    def _close_stream_worker(self, stream: Any, halt: _StreamHalt | None) -> None:
        sd = self._sd
        can_abort = (
            halt is not None and sd is not None and getattr(sd, "CallbackAbort", None) is not None
        )
        if can_abort and getattr(stream, "active", False):
            deadline = time.monotonic() + _STREAM_ABORT_GRACE_S
            while time.monotonic() < deadline and getattr(stream, "active", False):
                time.sleep(0.01)
        if getattr(stream, "active", False):
            self._call_stream_method(stream, "abort", "stop", warn_key="rec.mic_stop_warn")
        self._call_stream_method(stream, "close", warn_key="rec.mic_close_warn")

    def _call_stream_method(self, stream: Any, *names: str, warn_key: str) -> None:
        for name in names:
            method = getattr(stream, name, None)
            if method is None:
                continue
            try:
                method()
            except Exception as exc:
                print(i18n.t(warn_key, error=exc))
            return
