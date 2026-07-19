# Design — module-capabilities (acties, shutdown, UI-dispatch, settings)

- **Datum:** 2026-07-19
- **Status:** Goedgekeurd (chat)
- **Basis:** [ADR-0003](../adr/0003-hybrid-module-system.md),
  [2026-07-19-modules-design.md](2026-07-19-modules-design.md)

## Doel

De bestaande module-architectuur uitbreiden zodat **rijkere modules** (zoals
Meeting Buddy) kunnen draaien zonder de huidige inbox-spiegel of het
dicteercyclus-event-contract te breken.

Geen plugin-framework, geen submodules, geen nieuwe EventBus-events.

## Principes

| Regel | Keuze |
|-------|--------|
| Backward compatible | `PraatMaarModule` blijft minimaal; extra's zijn **optionele** protocols |
| EventBus | Alleen dicteercyclus-events; modules met eigen lifecycle regelen dat intern |
| Submodule-registratie | Nee — één praatMaar-module per feature (intern subpackage mag wel) |
| Module-instellingen | Per module eigen map onder app-dir (`<module-id>/config.json`) |
| GUI | Alleen via `ctx.ui_dispatch(...)` vanuit achtergrondthreads |

## Nieuwe contracten

### `ModuleAction`

```python
@dataclass(frozen=True)
class ModuleAction:
    id: str
    label_key: str
    handler: Callable[[], None]
    in_tray: bool = False
```

- **`in_tray=False` (default):** actie verschijnt in de **Modules-dialoog**
  (knoppen per ingeschakelde module).
- **`in_tray=True`:** actie verschijnt **ook** onder tray → **Modules** (submenu).

Tray-submenu alleen wanneer minstens één ingeschakelde module tray-acties heeft;
anders blijft **Modules** één klik naar de dialoog (huidig gedrag).

### `ModuleWithActions` (optioneel)

```python
def actions(self) -> list[ModuleAction]: ...
```

### `ModuleWithShutdown` (optioneel)

```python
def on_app_shutdown(self) -> None: ...
```

Aangeroepen vanuit `dictation.main()` vóór `indicator.destroy()`, en bij
herladen van modules (`_reload_modules`).

### `ModuleContext` (uitgebreid)

```python
@dataclass(frozen=True)
class ModuleContext:
    app_dir: Path
    ui_dispatch: UiDispatch  # indicator.call_on_main na opstart

    def module_dir(self, module_id: str) -> Path: ...
```

`ui_dispatch` is `noop` tot de indicator klaar is; daarna `_reload_modules()`.

### Module-instellingen (`modules/settings_store.py`)

- `load_config(app_dir, module_id)` / `save_config(...)`
- Pad: `%APPDATA%\praatMaar\<module-id>\config.json`

Nog **niet** in de centrale `config.json` of Modules-dialoog — YAGNI.

## UI-plaatsing acties

**Primair:** Modules-dialoog — knoppen onder elke **ingeschakelde** module.

**Optioneel:** tray → Modules → submenu:

```
Modules ▶
  Modules beheren…     → opent dialoog
  ─────────────────
  <module-naam> ▶      → alleen acties met in_tray=True
    Actie A
    Actie B
```

**macOS:** Modules-dialoog draait in subprocess → actieknoppen daar **niet**
beschikbaar (geen IPC). Tray-acties (`in_tray=True`) werken wel op alle platformen.

## Eigen vensters

Geen extra framework. Modules openen tkinter-vensters via `ctx.ui_dispatch`.
Parent voor dialogs: `indicator.root` (via dispatch, niet direct importeren).

## Wiring

| Plek | Wijziging |
|------|-----------|
| `modules/_contract.py` | Acties, shutdown, ui_dispatch |
| `modules/settings_store.py` | Per-module JSON-config |
| `modules/registry.py` | shutdown, run_action, tray_action_entries |
| `modules/bus.py` | `shutdown()`, `run_action()`, `modules` property |
| `modules_dialog.py` | Actieknoppen + `on_module_action` callback |
| `tray.py` | Optioneel Modules-submenu |
| `dictation.py` | ui_dispatch, shutdown, tray/dialoog callbacks |

## Gedeeld Whisper (`SharedWhisper`)

`ModuleContext.whisper` wijst naar hetzelfde object als de dicteercyclus:

- `set_model` / `is_ready` / `model`
- `locked_model()` — contextmanager: model onder lock, of `RuntimeError` als leeg

`Opnamesessie` gebruikt diezelfde lock; modules moeten **niet** zelf
`WhisperModel(...)` laden. Geen lange meeting-pipeline in de core — alleen
modeltoegang.

## Buiten scope

- Meeting Buddy zelf (volgende PR)
- IPC voor module-acties vanuit macOS subprocess-dialoog
- Centrale module-settings UI
- Nieuwe CycleEvent-types
- DI / service locator / dynamisch laden

## Teststrategie

- Contract: acties, tray-filter, shutdown-isolatie
- Settings store: read/write/defaults
- Bus: run_action + shutdown
- Bestaande inbox-spiegel tests blijven groen
