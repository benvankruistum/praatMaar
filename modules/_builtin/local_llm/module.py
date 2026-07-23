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

from .config import DEFAULT_MODEL, load_local_llm_config
from .ollama_client import OllamaClient, OllamaError
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
        cfg = load_local_llm_config(ctx.app_dir)
        self._client = OllamaClient(cfg["ollama_base_url"])
        self._provider = OllamaSemanticAnalysis(self._client, model=cfg["ollama_model"])
        if self._provider.is_ready():
            self._register()
        else:
            log.info(
                "local-llm: Ollama/model niet klaar (model=%s); capability niet geregistreerd",
                cfg["ollama_model"],
            )

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

    def check_status(self) -> None:
        from tkinter import messagebox

        import i18n

        status = self._status_message()
        messagebox.showinfo(i18n.t("modules.local_llm.dialog.title"), status)

    def open_install_page(self) -> None:
        webbrowser.open(_OLLAMA_INSTALL_URL)

    def pull_default_model(self) -> None:
        from tkinter import messagebox

        import i18n

        cfg = load_local_llm_config(self._require_app_dir())
        model = cfg["ollama_model"] or DEFAULT_MODEL
        ollama_bin = shutil.which("ollama")
        if ollama_bin is None:
            local = Path.home() / "AppData/Local/Programs/Ollama/ollama.exe"
            ollama_bin = str(local) if local.is_file() else None
        if not ollama_bin:
            messagebox.showerror(
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
            messagebox.showerror(
                i18n.t("modules.local_llm.dialog.title"),
                i18n.t("modules.local_llm.status.pull_failed", error=str(exc)),
            )
            return
        messagebox.showinfo(
            i18n.t("modules.local_llm.dialog.title"),
            i18n.t("modules.local_llm.status.pull_started", model=model),
        )

    def _status_message(self) -> str:
        import i18n

        cfg = load_local_llm_config(self._require_app_dir())
        client = self._client or OllamaClient(cfg["ollama_base_url"])
        try:
            tags = client.tags()
        except OllamaError:
            return i18n.t("modules.local_llm.status.ollama_offline")
        model = cfg["ollama_model"]
        if client.has_model(model):
            if self._capabilities is not None and self._capabilities.get(CAPABILITY_ID) is None:
                self._provider = OllamaSemanticAnalysis(client, model=model)
                self._client = client
                self._register()
            return i18n.t("modules.local_llm.status.ready", model=model)
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
