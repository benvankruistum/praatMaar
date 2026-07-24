from __future__ import annotations

from types import SimpleNamespace

import dictation


class _FakeApp:
    def __init__(self) -> None:
        self.exec_called = False
        self.quit_called = False
        self.tray: _FakeTray | None = None

    def exec(self) -> int:
        self.exec_called = True
        assert self.tray is not None
        self.tray.on_quit()
        return 0

    def quit(self) -> None:
        self.quit_called = True


class _FakeIndicator:
    def __init__(self, **_kwargs: object) -> None:
        self.run_called = False
        self.stop_requested = False
        self.destroyed = False
        self.state_listener = None
        self.on_context_menu = None

    def set_destination(self, _destination: str | None) -> None:
        pass

    def call_on_main(self, fn: object) -> None:
        assert callable(fn)
        fn()

    def run(self) -> None:
        self.run_called = True

    def request_stop(self) -> None:
        self.stop_requested = True

    def destroy(self) -> None:
        self.destroyed = True


class _FakeTray:
    def __init__(self, **kwargs: object) -> None:
        self.on_quit = kwargs["on_quit"]
        self.stopped = False

    def set_state(self, *_args: object) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self.stopped = True

    def popup_menu(self, *_args: object, **_kwargs: object) -> None:
        pass

    def refresh_modules_menu(self) -> None:
        pass

    def refresh_language(self) -> None:
        pass

    def set_attention_needed(self, _needed: bool) -> None:
        pass


class _FakeListener:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def test_main_uses_qt_event_loop_and_quits_through_application(monkeypatch) -> None:
    app = _FakeApp()
    indicator: _FakeIndicator | None = None
    tray: _FakeTray | None = None

    def make_indicator(**kwargs: object) -> _FakeIndicator:
        nonlocal indicator
        indicator = _FakeIndicator(**kwargs)
        return indicator

    def make_tray(**kwargs: object) -> _FakeTray:
        nonlocal tray
        tray = _FakeTray(**kwargs)
        app.tray = tray
        return tray

    session = SimpleNamespace(
        model=None,
        is_recording=False,
        is_processing=False,
        warmup_microphone=lambda: None,
        probe_microphone=lambda: True,
        stop_audio_stream=lambda: None,
    )
    bus = SimpleNamespace(
        modules=[],
        set_modules=lambda _modules: None,
        shutdown=lambda: None,
        run_action=lambda _module_id, _action_id: None,
    )

    monkeypatch.setattr(dictation, "ensure_app", lambda: app)
    monkeypatch.setattr(dictation, "Splash", lambda: SimpleNamespace(run=lambda _worker: object()))
    monkeypatch.setattr(dictation, "RecordingIndicator", make_indicator)
    monkeypatch.setattr(dictation, "TrayIcon", make_tray)
    monkeypatch.setattr(dictation, "session", session)
    monkeypatch.setattr(dictation, "module_bus", bus)
    monkeypatch.setattr(dictation, "load_enabled_modules", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(dictation, "tray_action_entries", lambda _modules: [])
    monkeypatch.setattr(dictation, "tray_root_action_entries", lambda _modules: [])
    monkeypatch.setattr(dictation.host, "acquire_single_instance", lambda: True)
    monkeypatch.setattr(dictation.config, "ensure_app_data_dirs", lambda: None)
    monkeypatch.setattr(dictation.app_logging, "setup_logging", lambda: "praatMaar.log")
    monkeypatch.setattr(dictation.win_identity, "apply_windows_app_identity", lambda: None)
    monkeypatch.setattr(dictation.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(
        dictation,
        "keyboard",
        SimpleNamespace(Listener=lambda **_kwargs: _FakeListener()),
    )

    dictation.main()

    assert app.exec_called
    assert app.quit_called
    assert indicator is not None and indicator.run_called and indicator.stop_requested
    assert tray is not None and tray.stopped
