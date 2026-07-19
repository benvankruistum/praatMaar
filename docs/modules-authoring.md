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
| `on_app_start(ctx)` | ja | Eenmalig; `ctx.app_dir`, `ctx.ui_dispatch`, `ctx.whisper`, `ctx.capabilities`, `ctx.module_dir(id)` |
| `on_event(event)` | ja | Alle `CycleEvent`s; filter zelf op `event.type` |

Optionele protocols (duck typing — bestaande modules hoeven niets te wijzigen):

| Protocol | Wanneer |
|----------|---------|
| `ModuleWithActions` | `actions()` → knoppen in Modules-dialoog; optioneel tray via `in_tray=True` |
| `ModuleWithShutdown` | `on_app_shutdown()` — threads/vensters opruimen |

Referentie-implementatie (minimaal): `modules/_builtin/inbox_mirror.py`.

### Event-afhandeling

- Reageer op expliciete types (`CycleEventType.TRANSCRIPT_SAVED`, …).
- Gooi **niet** ongevangen exceptions door — `ModuleBus` vangt af, maar logt
  wel; kapotte modules mogen dicteren niet verstoren.
- Threading: events kunnen van de transcriptie-thread komen; **geen tkinter/GUI**
  in `on_event` — gebruik `ctx.ui_dispatch(...)` (na `on_app_start`).
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

## Module-acties

Implementeer `ModuleWithActions`:

```python
from modules._contract import ModuleAction, ModuleContext

def actions(self) -> list[ModuleAction]:
    return [
        ModuleAction(
            id="open",
            label_key="modules.my_module.open",
            handler=self._open_window,
        ),
        ModuleAction(
            id="start",
            label_key="modules.my_module.start",
            handler=self._start,
            in_tray=True,  # optioneel: ook onder tray → Modules
        ),
    ]
```

- Standaard verschijnen acties als **knoppen in de Modules-dialoog** (alleen als
  de module ingeschakeld is).
- `in_tray=True` → extra entry onder tray → **Modules** (submenu).
- macOS: dialoog draait in subprocess → actieknoppen alleen via tray
  (`in_tray=True`) tot er IPC komt.

## Module-instellingen

Gebruik `modules.settings_store` (eigen map per module):

```python
from modules.settings_store import load_config, save_config

def on_app_start(self, ctx: ModuleContext) -> None:
    self._config = load_config(ctx.app_dir, self.id, default={"mic": None})
    self._app_dir = ctx.app_dir

def _persist(self) -> None:
    save_config(self._app_dir, self.id, self._config)
```

Pad: `%APPDATA%\\praatMaar\\<module-id>\\config.json`. Nog geen UI in de
Modules-dialoog — module beheert eigen instellingenvenster.

## Afsluiten en UI-thread

- **`on_app_shutdown`:** stop threads, sluit vensters (via `ui_dispatch` indien nodig).
- **`ctx.ui_dispatch(fn)`:** plan tkinter-werk op de hoofdthread (Windows: pill-root;
  macOS: main-thread runloop).

## Gedeeld Whisper-model

Het Faster-Whisper-model wordt **eenmaal** geladen (splash) en gedeeld met modules
via `ctx.whisper` (`SharedWhisper`). Gebruik **niet** `Opnamesessie` vanuit een
module (die is voor korte dicteercycli); houd eigen opname/chunking, maar
transcribeer via de gedeelde lock:

```python
def on_app_start(self, ctx: ModuleContext) -> None:
    self._whisper = ctx.whisper

def _transcribe_wav(self, path: Path) -> str:
    with self._whisper.locked_model() as model:
        segments, _info = model.transcribe(
            str(path),
            language="nl",
            beam_size=5,
            vad_filter=True,
        )
        parts = [s.text.strip() for s in segments if s.text.strip()]
    return " ".join(parts)
```

Check `ctx.whisper.is_ready` vóór je start; anders is het model nog niet geladen.
Dicteren en modules serialiseren via dezelfde lock — parallelle `transcribe`-
calls blokkeren elkaar (geen tweede model in RAM).

## Capabilities (services tussen modules)

Modules mogen **niet** elkaars interne packages importeren. Bied functionaliteit
aan via de gedeelde registry:

```python
# Provider (in on_app_start)
ctx.capabilities.register(
    capability_id="audio.speaker_detection",
    provider=self._service,
    owner_module_id=self.id,
    contract_version=1,
)

# Consumer (optioneel)
provider = ctx.capabilities.get("audio.speaker_detection")
# of verplicht:
# provider = ctx.capabilities.require("audio.speaker_detection")
```

Gedeelde protocollen: `modules/capabilities/<naam>.py`. Concrete implementatie:
`modules/_builtin/`. Bij afsluiten verwijdert de registry automatisch alle
capabilities van de module (`unregister_owner`) — ook als `on_app_shutdown` faalt.

Zie [capability-registry design](superpowers/specs/2026-07-19-capability-registry-design.md)
en [speaker-detection design](superpowers/specs/2026-07-19-speaker-detection-design.md).

## UI

Nieuwe modules verschijnen **automatisch** in tray → **Modules** (checkbox
aan/uit). Acties en tray-submenu worden automatisch opgebouwd als je
`ModuleWithActions` implementeert.

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
