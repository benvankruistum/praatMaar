"""
Local LLM module — Ollama + Qwen as ``ai.semantic_analysis`` provider.

Default off. Enable via tray Modules. Setup (detect/pull) lives here so other
modules (e.g. Meeting Buddy) only consume the capability.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import webbrowser
from pathlib import Path

from modules._contract import CycleEvent, ModuleAction, ModuleContext
from modules.capabilities.semantic_analysis import CAPABILITY_ID, CONTRACT_VERSION
from ui.dialogs import message

from .config import DEFAULT_MODEL, load_local_llm_config, save_local_llm_config
from .ollama_client import OllamaClient, OllamaError
from .properties_dialog import show_properties_dialog
from .provider import OllamaSemanticAnalysis

log = logging.getLogger("praatmaar.local_llm")

_OLLAMA_INSTALL_URL = "https://ollama.com/download"


class LocalLlmModule:
    id = "local-llm"

    def __init__(self) -> None:
        self._app_dir: Path | None = None
        self._capabilities = None
        self._provider: OllamaSemanticAnalysis | None = None
        self._client: OllamaClient | None = None
        self._ui_dispatch = None

    def display_name_key(self) -> str:
        return "modules.local_llm.name"

    def description_key(self) -> str:
        return "modules.local_llm.description"

    def default_enabled(self) -> bool:
        return False

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._app_dir = ctx.app_dir
        self._capabilities = ctx.capabilities
        self._ui_dispatch = ctx.ui_dispatch
        self._reload_provider()

    def on_event(self, event: CycleEvent) -> None:
        return None

    def on_app_shutdown(self) -> None:
        if self._capabilities is not None:
            self._capabilities.unregister_owner(self.id)
        self._provider = None
        self._client = None

    def actions(self) -> list[ModuleAction]:
        return [
            ModuleAction(
                id="properties",
                label_key="modules.local_llm.actions.properties",
                handler=self.open_properties,
                in_tray=True,
            ),
            ModuleAction(
                id="check_status",
                label_key="modules.local_llm.actions.check_status",
                handler=self.check_status,
                in_tray=True,
            ),
            ModuleAction(
                id="open_install",
                label_key="modules.local_llm.actions.open_install",
                handler=self.open_install_page,
                in_tray=False,
            ),
            ModuleAction(
                id="pull_model",
                label_key="modules.local_llm.actions.pull_model",
                handler=self.pull_default_model,
                in_tray=False,
            ),
        ]

    def open_properties(self) -> None:
        if self._ui_dispatch is None:
            raise RuntimeError("local-llm is niet gestart")
        self._ui_dispatch(self._show_properties_dialog)

    def check_status(self) -> None:
        import i18n

        status = self._status_message()
        message.info(i18n.t("modules.local_llm.dialog.title"), status)

    def open_install_page(self) -> None:
        webbrowser.open(_OLLAMA_INSTALL_URL)

    def pull_default_model(self) -> None:
        import i18n

        cfg = load_local_llm_config(self._require_app_dir())
        model = cfg["ollama_model"] or DEFAULT_MODEL
        ollama_bin = shutil.which("ollama")
        if ollama_bin is None:
            local = Path.home() / "AppData/Local/Programs/Ollama/ollama.exe"
            ollama_bin = str(local) if local.is_file() else None
        if not ollama_bin:
            message.error(
                i18n.t("modules.local_llm.dialog.title"),
                i18n.t("modules.local_llm.status.ollama_missing"),
            )
            return
        try:
            subprocess.Popen(  # noqa: S603 — user-initiated local tool
                [ollama_bin, "pull", model],
                cwd=str(Path(ollama_bin).parent),
            )
        except OSError as exc:
            message.error(
                i18n.t("modules.local_llm.dialog.title"),
                i18n.t("modules.local_llm.status.pull_failed", error=str(exc)),
            )
            return
        message.info(
            i18n.t("modules.local_llm.dialog.title"),
            i18n.t("modules.local_llm.status.pull_started", model=model),
        )

    def _show_properties_dialog(self) -> None:
        cfg = load_local_llm_config(self._require_app_dir())
        result = show_properties_dialog(
            endpoint_mode=str(cfg["endpoint_mode"]),
            custom_base_url=str(cfg["custom_base_url"]),
            custom_model=str(cfg["custom_model"]),
        )
        if result is None:
            return
        if result.endpoint_mode == "custom":
            save_local_llm_config(
                self._require_app_dir(),
                endpoint_mode=result.endpoint_mode,
                ollama_base_url=result.ollama_base_url,
                ollama_model=result.ollama_model,
            )
        else:
            save_local_llm_config(
                self._require_app_dir(),
                endpoint_mode=result.endpoint_mode,
            )
        self._reload_provider()

    def _reload_provider(self) -> None:
        """Herlaadt URL/model uit config en (her)registreert de capability."""

        cfg = load_local_llm_config(self._require_app_dir())
        if self._capabilities is not None:
            try:
                self._capabilities.unregister(CAPABILITY_ID, self.id)
            except ValueError:
                self._capabilities.unregister_owner(self.id)

        self._client = OllamaClient(cfg["ollama_base_url"])
        self._provider = OllamaSemanticAnalysis(self._client, model=cfg["ollama_model"])
        if self._provider.is_ready():
            self._register()
        else:
            log.info(
                "local-llm: Ollama/model niet klaar (url=%s model=%s); capability niet geregistreerd",
                cfg["ollama_base_url"],
                cfg["ollama_model"],
            )

    def _status_message(self) -> str:
        import i18n

        # Altijd verse config (na eigenschappen-wijziging zonder aparte herstart).
        self._reload_provider()
        cfg = load_local_llm_config(self._require_app_dir())
        client = self._client or OllamaClient(cfg["ollama_base_url"])
        try:
            tags = client.tags()
        except OllamaError:
            return i18n.t(
                "modules.local_llm.status.ollama_offline",
                url=cfg["ollama_base_url"],
            )
        model = cfg["ollama_model"]
        if client.has_model(model):
            return i18n.t(
                "modules.local_llm.status.ready",
                model=model,
                url=cfg["ollama_base_url"],
            )
        return i18n.t(
            "modules.local_llm.status.model_missing",
            model=model,
            available=", ".join(tags) if tags else "—",
        )

    def _register(self) -> None:
        if self._capabilities is None or self._provider is None:
            return
        if self._capabilities.get(CAPABILITY_ID) is not None:
            return
        self._capabilities.register(
            capability_id=CAPABILITY_ID,
            provider=self._provider,
            owner_module_id=self.id,
            contract_version=CONTRACT_VERSION,
        )
        log.info("local-llm: registered %s", CAPABILITY_ID)

    def _require_app_dir(self) -> Path:
        if self._app_dir is None:
            raise RuntimeError("local-llm is niet gestart")
        return self._app_dir
