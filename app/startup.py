"""Splash → dependencies → model load (geen Opnamesessie side effects hier)."""

from __future__ import annotations

import threading
from typing import Any

import hotkeys
import i18n
from splash import Splash


def format_mb(num_bytes: float) -> str:
    """Bytes als megabytes met een Nederlandse komma, bijv. '28,4'."""

    return f"{num_bytes / (1024 * 1024):.1f}".replace(".", ",")


class DownloadTracker:
    """Verzamelt downloadvoortgang over alle bestanden heen."""

    def __init__(self, reporter: Splash) -> None:
        self._reporter = reporter
        self._lock = threading.Lock()
        self._bars: dict[int, tuple[float, float]] = {}

    def update(self, bar_id: int, done: float, total: float) -> None:
        with self._lock:
            self._bars[bar_id] = (done, total)
            total_done = sum(d for d, _ in self._bars.values())
            total_all = sum(t for _, t in self._bars.values() if t)

        if total_all > 0:
            self._reporter.set_progress(
                total_done / total_all,
                f"{format_mb(total_done)} / {format_mb(total_all)} MB",
            )


def download_model_with_progress(model_name: str, reporter: Splash) -> str:
    """Downloadt het model via huggingface_hub met voortgang op de splash."""

    import huggingface_hub
    from tqdm.auto import tqdm

    _KNOWN_REPO_IDS = {
        "tiny": "Systran/faster-whisper-tiny",
        "tiny.en": "Systran/faster-whisper-tiny.en",
        "base": "Systran/faster-whisper-base",
        "base.en": "Systran/faster-whisper-base.en",
        "small": "Systran/faster-whisper-small",
        "small.en": "Systran/faster-whisper-small.en",
        "medium": "Systran/faster-whisper-medium",
        "medium.en": "Systran/faster-whisper-medium.en",
        "large-v1": "Systran/faster-whisper-large-v1",
        "large-v2": "Systran/faster-whisper-large-v2",
        "large-v3": "Systran/faster-whisper-large-v3",
        "large": "Systran/faster-whisper-large-v3",
        "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
        "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
        "distil-small.en": "Systran/faster-distil-whisper-small.en",
        "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    }
    try:
        from faster_whisper.utils import _MODELS as _fw_models
    except ImportError:
        _fw_models = {}
    repo_id = _fw_models.get(model_name) or _KNOWN_REPO_IDS.get(model_name, model_name)

    allow_patterns = [
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    ]

    tracker = DownloadTracker(reporter)

    class _NullSink:
        def write(self, *_args: Any) -> None:
            pass

        def flush(self) -> None:
            pass

    class _ProgressTqdm(tqdm):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._track = kwargs.get("unit") == "B"
            kwargs["file"] = _NullSink()
            kwargs["disable"] = False
            super().__init__(*args, **kwargs)

        def update(self, n: float | None = 1) -> bool | None:
            displayed = super().update(n)
            if self._track:
                tracker.update(id(self), self.n, self.total or 0)
            return displayed

    return huggingface_hub.snapshot_download(
        repo_id,
        allow_patterns=allow_patterns,
        tqdm_class=_ProgressTqdm,
    )


def load_dependencies(
    reporter: Splash,
    *,
    bind_audio: Any,
    assign_globals: Any,
) -> None:
    """Importeert zware libraries op de splash-achtergrondthread."""

    total_steps = 5

    def step(index: int, label: str) -> None:
        reporter.set_status(f"{label}…")
        reporter.set_progress(None, i18n.t("splash.part", index=index, total=total_steps))

    step(1, i18n.t("splash.dep.whisper"))
    from faster_whisper import WhisperModel as _WhisperModel

    step(2, i18n.t("splash.dep.audio"))
    import numpy as _np
    from scipy.io.wavfile import write as _write_wav

    step(3, i18n.t("splash.dep.mic"))
    import sounddevice as _sd

    step(4, i18n.t("splash.dep.keyboard"))
    import sys

    import pyperclip as _pyperclip

    if sys.platform == "darwin":
        from host._mac_hotkeys import QuartzKeyListener

        class _DarwinKeyboard:
            """Shim: zelfde ``Listener``-API als pynput, zonder achtergrondthread."""

            Listener = QuartzKeyListener

        _keyboard = _DarwinKeyboard()
    else:
        from pynput import keyboard as _keyboard

        hotkeys.init(_keyboard)

    step(5, i18n.t("splash.dep.tray"))
    from tray import TrayIcon as _TrayIcon

    assign_globals(
        np=_np,
        sd=_sd,
        pyperclip=_pyperclip,
        keyboard=_keyboard,
        write_wav=_write_wav,
        WhisperModel=_WhisperModel,
        TrayIcon=_TrayIcon,
    )
    bind_audio(numpy_mod=_np, sounddevice_mod=_sd, write_wav=_write_wav)


def load_model(
    reporter: Splash,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    whisper_model_cls: Any,
) -> Any:
    """Laadt het Whisper-model (download indien nodig)."""

    from faster_whisper.utils import download_model

    try:
        model_path = download_model(model_name, local_files_only=True)
        need_download = False
    except Exception:
        model_path = None
        need_download = True

    if need_download:
        reporter.set_status(i18n.t("splash.download"))
        reporter.set_progress(0.0, "")
        model_path = download_model_with_progress(model_name, reporter)

    reporter.set_status(i18n.t("splash.loading"))
    reporter.set_progress(None)

    return whisper_model_cls(
        model_path,
        device=device,
        compute_type=compute_type,
    )


def startup(
    reporter: Splash,
    *,
    bind_audio: Any,
    assign_globals: Any,
    model_name: str,
    device: str,
    compute_type: str,
    get_whisper_model_cls: Any,
) -> Any:
    """Volledige splash-opstarttaak: dependencies + model."""

    load_dependencies(reporter, bind_audio=bind_audio, assign_globals=assign_globals)
    return load_model(
        reporter,
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        whisper_model_cls=get_whisper_model_cls(),
    )
