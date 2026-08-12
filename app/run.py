"""Application run loop: splash → ready → Qt mainloop."""

from __future__ import annotations

import sys
from typing import Any

import hotkeys
import i18n
from app.recent_transcripts import recent_transcript_menu_entries
from app.settings_service import active_destination_path, user_config_dict
from app.settings_service import apply_settings as apply_settings_svc
from app.settings_service import current_settings as current_settings_svc
from app.startup import startup


def run() -> None:
    """Start indicator, tray en globale toetsenbordlistener.

    Dependencies worden via het ``dictation``-module-object gelezen zodat
    bestaande tests kunnen monkeypatchen (ensure_app, Splash, session, …).
    """

    import dictation as d

    d.win_identity.apply_windows_app_identity()

    log_file = d.app_logging.setup_logging()
    d.config.ensure_app_data_dirs()
    app = d.ensure_app()
    print(i18n.t("log.path", path=log_file))

    if not d.host.acquire_single_instance():
        if sys.platform != "darwin":
            print(i18n.t("already_running"))
        raise SystemExit(0)

    # Session: monkeypatch mag ``dictation.session`` zetten; anders lazy build.
    session = d.get_session()

    def assign_globals(**kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(d, key, value)

    try:
        d.model = d.Splash().run(
            lambda reporter: startup(
                reporter,
                bind_audio=getattr(session, "bind_audio", lambda **_k: None),
                assign_globals=assign_globals,
                model_name=d.MODEL_NAME,
                device=d.DEVICE,
                compute_type=d.COMPUTE_TYPE,
                get_whisper_model_cls=lambda: d.WhisperModel,
            )
        )
    except Exception as exc:
        print(i18n.t("model.load_failed"))
        print(i18n.t("model.error", error=exc))
        raise SystemExit(1) from exc

    if hasattr(session, "model"):
        session.model = d.model

    # Modules pas na splash-intent (ADR-0007).
    d._reload_modules()

    print(i18n.t("model.loaded"))
    if d.WARM_MICROPHONE and hasattr(session, "warmup_microphone"):
        session.warmup_microphone()
    print(
        i18n.t(
            "controls",
            mode=d.MODE,
            hotkey=hotkeys.format_hotkey(d.HOTKEY_TOKENS),
        )
    )

    router = d.get_hotkey_router()

    def _on_indicator_moved(position: str, x: int, y: int) -> None:
        d.INDICATOR_POSITION = position
        d.INDICATOR_XY = (x, y)
        d.config.save_config(user_config_dict(d))

    def pill_toggle_mode() -> None:
        if d.MODE == "meeting":
            return
        settings = user_config_dict(d)
        settings["mode"] = "ptt" if d.MODE == "toggle" else "toggle"
        apply_settings_svc(
            d,
            settings,
            d._indicator,
            session=session,
            reload_modules=d._reload_modules,
            refresh_mic_attention=d._refresh_mic_attention,
            tray=d._tray,
        )
        print("\n" + i18n.t("dictation.mode_switched", mode=i18n.t(f"state.tag.{d.MODE}")))

    def pill_retry() -> None:
        d._refresh_mic_attention()
        router.pill_control_press()

    indicator = d.RecordingIndicator(
        position=d.INDICATOR_POSITION,
        xy=d.INDICATOR_XY,
        on_moved=_on_indicator_moved,
        on_control_press=router.pill_control_press,
        on_control_release=router.pill_control_release,
        on_retry=pill_retry,
        on_mode_toggle=pill_toggle_mode,
    )
    d._indicator = indicator
    if d._runtime is not None:
        d._runtime.indicator = indicator
    indicator.set_destination(d.ACTIVE_DESTINATION, active_destination_path(d))
    indicator.set_hotkey_label(hotkeys.format_hotkey(d.HOTKEY_TOKENS))
    indicator.show_ready_cue()

    d._ui_dispatch = indicator.call_on_main
    d._reload_modules()

    def run_module_action(module_id: str, action_id: str) -> None:
        indicator.call_on_main(lambda: d.module_bus.run_action(module_id, action_id))

    def open_settings() -> None:
        from settings import open_settings_dialog

        indicator.call_on_main(
            lambda: open_settings_dialog(
                indicator,
                current_settings_svc(d),
                lambda new: apply_settings_svc(
                    d,
                    new,
                    indicator,
                    session=session,
                    reload_modules=d._reload_modules,
                    refresh_mic_attention=d._refresh_mic_attention,
                    tray=d._tray,
                ),
                router.set_capture,
                on_retranscribe=d.retranscribe_recovery_wav,
            )
        )

    def open_destinations() -> None:
        from destinations_dialog import open_destinations_dialog

        indicator.call_on_main(
            lambda: open_destinations_dialog(
                indicator,
                current_settings_svc(d),
                lambda new: apply_settings_svc(
                    d,
                    new,
                    indicator,
                    session=session,
                    reload_modules=d._reload_modules,
                    refresh_mic_attention=d._refresh_mic_attention,
                    tray=d._tray,
                ),
            )
        )

    def open_modules() -> None:
        from modules_dialog import open_modules_dialog

        indicator.call_on_main(
            lambda: open_modules_dialog(
                indicator,
                current_settings_svc(d),
                lambda new: apply_settings_svc(
                    d,
                    new,
                    indicator,
                    session=session,
                    reload_modules=d._reload_modules,
                    refresh_mic_attention=d._refresh_mic_attention,
                    tray=d._tray,
                ),
                on_module_action=run_module_action,
                enabled_module_ids={module.id for module in d.module_bus.modules},
                get_enabled_module_ids=lambda: {module.id for module in d.module_bus.modules},
            )
        )

    def open_help() -> None:
        from help_dialog import open_help as show_help

        indicator.call_on_main(lambda: show_help(indicator))

    def request_shutdown() -> None:
        indicator.request_stop()
        app.quit()

    tray = d.TrayIcon(
        on_quit=request_shutdown,
        on_settings=open_settings,
        on_destinations=open_destinations,
        on_modules=open_modules,
        on_help=open_help,
        on_module_action=run_module_action,
        get_module_tray_actions=lambda: d.tray_action_entries(list(d.module_bus.modules)),
        get_module_tray_root_actions=lambda: d.tray_root_action_entries(list(d.module_bus.modules)),
        get_recent_transcript_entries=lambda: recent_transcript_menu_entries(
            d.DESTINATIONS,
            pyperclip_mod=d.pyperclip,
            ui_dispatch=d._ui_dispatch,
        ),
    )
    d._tray = tray
    if d._runtime is not None:
        d._runtime.tray = tray

    indicator.state_listener = tray.set_state

    def show_pill_context_menu(x: int, y: int) -> None:
        tray.popup_menu(x, y)

    indicator.on_context_menu = show_pill_context_menu
    tray.start()
    d._refresh_mic_attention()

    listener = d.keyboard.Listener(
        on_press=router.on_press,
        on_release=router.on_release,
    )
    listener.start()

    d.signal.signal(d.signal.SIGINT, lambda *_: request_shutdown())

    try:
        indicator.run()
        app.exec()
    except KeyboardInterrupt:
        pass
    finally:
        print()
        print(i18n.t("shutdown"))

        listener.stop()
        tray.stop()

        active_recording = bool(getattr(session, "is_recording", False))
        if active_recording and hasattr(session, "cancel"):
            session.cancel()

        if hasattr(session, "stop_audio_stream"):
            session.stop_audio_stream()
        d.module_bus.shutdown()
        indicator.destroy()


def main() -> None:
    run()
