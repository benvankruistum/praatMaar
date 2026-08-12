"""Chunk-worker en incrementele transcriptie-pad."""

from __future__ import annotations

import os
import threading
from typing import Any

from chunk_transcription import (
    OVERLAP_SECONDS,
    decide_chunk_cut,
    dedupe_overlap_text,
    trailing_silence_seconds,
)
from indicator import set_chunk_leds_enabled, signal_chunk_trigger
from modules._contract import CycleEvent, CycleEventType

# RMS onder deze drempel telt als stilte voor chunk-VAD (v1, eenvoudig).
_CHUNK_SILENCE_RMS = 0.01
_CHUNK_FRAME_SECONDS = 0.05
_CHUNK_POLL_SECONDS = 0.25


class IncrementalMixin:
    def _stop_incremental_worker(self, *, wait: bool = True) -> None:
        stop = self._incremental_stop
        thread = self._incremental_thread
        if stop is not None:
            stop.set()
        if (
            wait
            and thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=5.0)
        self._incremental_thread = None
        self._incremental_stop = None
        if wait:
            set_chunk_leds_enabled(False)

    def _start_incremental_worker(self) -> None:
        if not self.incremental_transcription:
            set_chunk_leds_enabled(False)
            return

        # Oude worker alleen seinen, niet joinen — anders blokkeert start de UI.
        self._stop_incremental_worker(wait=False)
        set_chunk_leds_enabled(True)
        self._incremental_stop = threading.Event()
        self._incremental_thread = threading.Thread(
            target=self._incremental_loop,
            daemon=True,
        )
        self._incremental_thread.start()

    def _concat_audio(self, chunks: list[Any]) -> Any:
        np, _, _ = self._require_audio()
        if not chunks:
            return np.zeros((0,), dtype=np.float32)
        return np.concatenate(chunks, axis=0).reshape(-1)

    def _sample_count_locked(self) -> int:
        return int(sum(int(chunk.shape[0]) for chunk in self._audio_chunks))

    def _rms_frames(self, audio: Any) -> list[float]:
        np, _, _ = self._require_audio()
        if audio.size == 0:
            return []
        frame = max(1, int(self.sample_rate * _CHUNK_FRAME_SECONDS))
        levels: list[float] = []
        for start in range(0, int(audio.shape[0]), frame):
            piece = audio[start : start + frame]
            levels.append(float(np.sqrt(np.mean(np.square(piece)))))
        return levels

    def _emit_partial(self, transcript: str, session_id: str) -> None:
        with self._lock:
            self._last_partial_transcript = transcript
        if self._emit_event is not None:
            self._emit_event(
                CycleEvent(
                    type=CycleEventType.TRANSCRIPT_PARTIAL,
                    session_id=session_id,
                    transcript=transcript,
                    language=self.language,
                    mode=self.mode,
                )
            )

    def _commit_audio_slice(
        self,
        *,
        audio: Any,
        start_sample: int,
        end_sample: int,
        previous_text: str,
    ) -> str | None:
        """Whisper over [start,end) + overlap-prefix; retourneert ontdubbelde tekst."""

        if end_sample <= start_sample:
            return None
        overlap = int(self.sample_rate * OVERLAP_SECONDS)
        slice_start = max(0, start_sample - overlap) if previous_text else start_sample
        piece = audio[slice_start:end_sample]
        if piece.size == 0:
            return None
        try:
            raw = self._transcribe_chunks_to_text([piece.reshape(-1, 1)])
        except Exception:
            return None
        if not raw:
            return None
        return dedupe_overlap_text(previous_text, raw) or None

    def _try_commit_chunk(self, reason: str) -> None:
        with self._lock:
            if not self._recording:
                return
            session_id = self._session_id
            chunks_copy = [chunk.copy() for chunk in self._audio_chunks]
            through = self._transcribed_through_samples
            previous = " ".join(self._chunk_transcripts).strip()
            total = self._sample_count_locked()

        if session_id is None or not chunks_copy or total <= through:
            return

        audio = self._concat_audio(chunks_copy)
        open_audio = audio[through:]
        silence_s = trailing_silence_seconds(
            self._rms_frames(open_audio),
            frame_seconds=_CHUNK_FRAME_SECONDS,
            silence_rms=_CHUNK_SILENCE_RMS,
        )
        silence_samples = int(silence_s * self.sample_rate)

        if reason == "vad":
            cut_end = total - silence_samples
            if cut_end <= through:
                # Open chunk is (bijna) alleen stilte — wacht op hard cap.
                return
        else:
            cut_end = min(
                total,
                through + int(self._incremental_chunk_seconds * self.sample_rate),
            )

        if cut_end <= through:
            return

        piece_text = self._commit_audio_slice(
            audio=audio,
            start_sample=through,
            end_sample=cut_end,
            previous_text=previous,
        )
        signal_chunk_trigger(reason)

        with self._lock:
            if self._session_id != session_id or not self._recording:
                return
            self._transcribed_through_samples = cut_end
            if piece_text:
                self._chunk_transcripts.append(piece_text)
                combined = " ".join(self._chunk_transcripts).strip()
            else:
                combined = previous

        if piece_text and combined:
            self._emit_partial(combined, session_id)
        if piece_text and self._live_paste_enabled():
            self._paste_delta(piece_text)

    def _incremental_loop(self) -> None:
        stop = self._incremental_stop
        if stop is None:
            return

        while not stop.wait(self._chunk_poll_seconds):
            with self._lock:
                if not self._recording:
                    return
                chunks_copy = [chunk.copy() for chunk in self._audio_chunks]
                through = self._transcribed_through_samples

            if not chunks_copy:
                continue

            audio = self._concat_audio(chunks_copy)
            total = int(audio.shape[0])
            open_seconds = (total - through) / float(self.sample_rate)
            silence_s = trailing_silence_seconds(
                self._rms_frames(audio[through:]),
                frame_seconds=_CHUNK_FRAME_SECONDS,
                silence_rms=_CHUNK_SILENCE_RMS,
            )
            reason = decide_chunk_cut(
                mode=self.incremental_chunk_mode,
                open_seconds=open_seconds,
                trailing_silence_seconds=silence_s,
                chunk_seconds=self._incremental_chunk_seconds,
                vad_ms=self.incremental_vad_ms,
                min_seconds=self._incremental_min_seconds,
            )
            if reason is None:
                continue
            try:
                self._try_commit_chunk(reason)
            except Exception:
                continue

    def _transcribe_chunks_to_text(self, chunks: list[Any]) -> str:
        """Transcribeert audioblokken naar tekst (incrementeel + finaal)."""

        temporary_path = self.create_temporary_wav(chunks)
        try:
            with self._whisper.locked_model() as model:
                segments, _info = model.transcribe(
                    str(temporary_path),
                    **self.transcribe_kwargs(),
                )
                text_parts: list[str] = []
                for segment in segments:
                    text = segment.text.strip()
                    if text:
                        text_parts.append(text)

            return " ".join(text_parts).strip()
        finally:
            if self.delete_temp_audio and temporary_path.exists():
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass


