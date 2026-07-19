# Module authoring (ingebouwd)

Checklist voor een **nieuwe in-process module** in de praatMaar-repo. Externe
integratie zonder code-wijziging: [modules-integration.md](modules-integration.md).

Architectuur: [ADR-0003](adr/0003-hybrid-module-system.md) ·
feature-spec: [2026-07-19-modules-design.md](superpowers/specs/2026-07-19-modules-design.md).

## v1-beperking

Modules worden **niet** dynamisch geladen. Elke module:

1. Leeft in `modules/_builtin/<jouw_module>.py` (of subpackage)
2. Wordt geregistreerd in `modules/registry.py` → `all_builtin_modules()`
3. Komt binnen via **PR** naar `main`

Plugin-download / `entry_points` is bewust later.

## Interface

Implementeer het `PraatMaarModule`-Protocol (`modules/_contract.py`):

| Member | Verplicht | Notities |
|--------|-----------|----------|
| `id` | ja | Stabiel, kebab-case, uniek (bijv. `inbox-mirror`) |
| `display_name_key()` | ja | i18n-key voor UI |
| `description_key()` | ja | i18n-key voor UI |
| `default_enabled()` | ja | Default als key ontbreekt in config |
| `on_app_start(ctx)` | ja | Eenmalig; `ctx.app_dir` = app-datamap |
| `on_event(event)` | ja | Alle `CycleEvent`s; filter zelf op `event.type` |

Referentie-implementatie: `modules/_builtin/inbox_mirror.py`.

### Event-afhandeling

- Reageer op expliciete types (`CycleEventType.TRANSCRIPT_SAVED`, …).
- Gooi **niet** ongevangen exceptions door — `ModuleBus` vangt af, maar logt
  wel; kapotte modules mogen dicteren niet verstoren.
- Threading: events kunnen van de transcriptie-thread komen; geen tkinter/GUI
  in `on_event` zonder marshalling naar de hoofdthread.
- Finaal gedrag: `transcript.saved` + `path` is het betrouwbare moment om
  bestanden te lezen/kopiëren.

## Stappen (checklist)

### 1. Module-class

```python
# modules/_builtin/my_module.py
from modules._contract import CycleEvent, CycleEventType, ModuleContext

class MyModule:
    id = "my-module"

    def display_name_key(self) -> str:
        return "modules.my_module.name"

    def description_key(self) -> str:
        return "modules.my_module.description"

    def default_enabled(self) -> bool:
        return False

    def on_app_start(self, ctx: ModuleContext) -> None:
        ...

    def on_event(self, event: CycleEvent) -> None:
        if event.type != CycleEventType.TRANSCRIPT_SAVED:
            return
        ...
```

### 2. Registry

In `modules/registry.py`:

```python
from modules._builtin.my_module import MyModule

def all_builtin_modules() -> list[PraatMaarModule]:
    return [InboxMirrorModule(), MyModule()]
```

Onbekende keys in `config.json` → `modules` worden genegeerd door
`sanitize_modules_config`.

### 3. i18n (nl / en / de)

Voeg keys toe in **alle drie** `locales/*.json`:

```json
"modules.my_module.name": "…",
"modules.my_module.description": "…"
```

De modules-dialoog (`modules_dialog.py`) toont naam + beschrijving automatisch
voor elke entry in `all_builtin_modules()`.

### 4. Tests

Voeg `tests/test_modules_my_module.py` toe:

- Mock `ModuleContext` met `tmp_path` als `app_dir`
- Roep `on_app_start` + `on_event` met synthetische `CycleEvent`
- Geen echte mic/Whisper

Voorbeelden: `tests/test_modules_inbox_mirror.py`, `tests/test_modules_bus.py`.

### 5. Documentatie (indien user-visible)

- User help (`docs/user/help.nl.md` + `.en` + `.de`) als gedrag voor eindgebruikers
  relevant is
- `CHANGELOG.md` `[Unreleased]` · eventueel `CONTEXT.md` als er een nieuwe
  domeinterm is
- Geen ADR tenzij een **architectuurkeuze** (zie `/domain-modeling`)

### 6. Verificatie

```powershell
python -m pytest tests/test_modules_*.py
python -m ruff check modules tests/test_modules_*.py
python -m ruff format .
```

## Module-specifieke config (v1)

**Niet** in v1: per-module settings in de UI of extra keys in `config.json`.
Als je configuratie nodig hebt:

- Hardcode een veilig default, of
- Gebruik vaste paden onder `ctx.app_dir`, of
- Wacht op een vervolgfeature (module settings in dialoog)

## UI

Nieuwe modules verschijnen **automatisch** in tray → **Modules** (checkbox
aan/uit). Geen wijziging in `modules_dialog.py` nodig, tenzij je custom UI
toevoegt (buiten scope v1).

macOS: dialoog draait via `settings_process.py` (`--praatmaar-modules-ui`).

## Domeintaal

Gebruik termen uit [CONTEXT.md](../CONTEXT.md) (`dicteercyclus`, `CycleEvent`,
`event-journal`, …). Nieuwe termen → glossary-update in dezelfde PR.

## Wat niet doen

- Module-logica in `dictation.py` hotkey-routing of `Opnamesessie` transcriptie
- OS-code in modules (gebruik `host` indien nodig, via bestaande seams)
- Exceptions laten escaleren uit `on_event`
- Alleen `locales/nl.json` bijwerken

## Verder lezen

- Contract: `modules/_contract.py`
- Bus + journal: `modules/bus.py`, `modules/journal.py`
- Wiring: `dictation.py` (`module_bus`, `_build_session`)
