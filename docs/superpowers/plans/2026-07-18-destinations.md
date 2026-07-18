# Bestemmingen + Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sticky bestemmingen (naam→map) met stem-wisseling via exacte match, zichtbaar in de pill; transcriptmap openen vanuit Instellingen; Help als tray-item naast Instellingen.

**Architecture:** Pure logica in `destinations.py` (normaliseren, matchen, padresolutie). `recovery.save_transcript` krijgt een optionele doelmap (prune alleen default). `Opnamesessie` checkt na transcriptie op bestemming-/reset-commando vóór plakken. Pill toont actieve naam in idle als er een bestemming actief is. Help is een Tk-venster met lokale markdown per UI-taal.

**Tech Stack:** Python 3.10+, bestaande tkinter/settings/tray/indicator, stdlib `pathlib`/`os.startfile`, pytest, i18n JSON + `docs/user/help.*.md`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-18-destinations-design.md`
- Geen nieuwe hotkeys; geen fuzzy match in v1
- Reset-frase: exact genormaliseerd **`standaard`**
- Prune alleen `%APPDATA%\praatMaar\transcripts\`
- Recovery-audio blijft in appdata `recovery\`
- UI-talen nl/en/de via bestaande i18n
- Windows-first (`os.startfile` voor mappen openen)

## File map

| File | Rol |
|------|-----|
| `destinations.py` | Normalisatie, match, config helpers, resolve save-dir |
| `recovery.py` | `save_transcript(text, directory=None)`; prune alleen default |
| `opnamesessie.py` | Na transcript: command-match → callback i.p.v. paste/save-inhoud |
| `dictation.py` | Config laden/bewaren; wiring save-dir + active destination + pill |
| `indicator.py` | Destination-label; idle zichtbaar als bestemming actief |
| `destinations_dialog.py` | Eigen dialoog bestemmingbeheer (tray-item) |
| `help_dialog.py` | Help-venster (markdown laden) |
| `tray.py` | Menu: Instellingen, Bestemmingen, Help, Afsluiten |
| `docs/user/help.nl.md` (+ en/de) | Gebruikerstekst werking + risico’s |
| `locales/*.json` | Labels |
| `tests/test_destinations.py` | Match/normalisatie/resolve |
| `praatMaar.spec` / `pyproject.toml` | Bundle `docs/user`, module `destinations`, `help_dialog` |

---

### Task 1: `destinations` pure logica (TDD)

**Files:**
- Create: `destinations.py`
- Create: `tests/test_destinations.py`

**Interfaces:**
- Produces:
  - `normalize_phrase(text: str) -> str`
  - `RESET_PHRASE = "standaard"` (na normalisatie)
  - `match_destination(transcript: str, destinations: list[dict]) -> str | None`  
    — `None` = geen match; `"__reset__"` of beter: return type `Literal["reset"] | str | None` waar `str` de canonical `name` is
  - Prefer: `match_command(transcript, destinations) -> tuple[str, str | None]`  
    — `("none", None)` | `("set", name)` | `("reset", None)`
  - `resolve_save_dir(active_name: str | None, destinations: list[dict], default_dir: Path) -> Path`
  - `sanitize_destinations(raw: Any) -> list[dict[str, str]]` — alleen items met non-empty name+path strings

- [ ] **Step 1: Write failing tests**

```python
# tests/test_destinations.py
from pathlib import Path
import destinations as d

def test_normalize_strips_punct_and_case():
    assert d.normalize_phrase("  Boodschappenlijst! ") == "boodschappenlijst"
    assert d.normalize_phrase("Hallo, wereld.") == "hallo wereld"

def test_match_set_exact():
    dests = [{"name": "Boodschappenlijst", "path": "D:/x"}]
    assert d.match_command("boodschappenlijst", dests) == ("set", "Boodschappenlijst")

def test_match_reset():
    assert d.match_command("Standaard!", []) == ("reset", None)

def test_match_none_for_content():
    dests = [{"name": "notities", "path": "D:/n"}]
    assert d.match_command("notities melk kopen", dests) == ("none", None)

def test_resolve_active_and_default(tmp_path: Path):
    dests = [{"name": "notities", "path": str(tmp_path / "n")}]
    assert d.resolve_save_dir("notities", dests, tmp_path / "default") == tmp_path / "n"
    assert d.resolve_save_dir(None, dests, tmp_path / "default") == tmp_path / "default"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_destinations.py -q`  
Expected: import/collection errors or FAIL

- [ ] **Step 3: Implement `destinations.py`**

```python
# destinations.py — kern
import re
from pathlib import Path
from typing import Any

RESET_PHRASE = "standaard"

def normalize_phrase(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def match_command(transcript: str, destinations: list[dict[str, str]]) -> tuple[str, str | None]:
    needle = normalize_phrase(transcript)
    if not needle:
        return ("none", None)
    if needle == RESET_PHRASE:
        return ("reset", None)
    for item in destinations:
        name = str(item.get("name", ""))
        if normalize_phrase(name) == needle:
            return ("set", name)
    return ("none", None)

def resolve_save_dir(active_name: str | None, destinations: list[dict[str, str]], default_dir: Path) -> Path:
    if active_name:
        for item in destinations:
            if item.get("name") == active_name:
                return Path(item["path"])
    return default_dir

def sanitize_destinations(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        path = str(item.get("path", "")).strip()
        if name and path:
            out.append({"name": name, "path": path})
    return out
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_destinations.py -q`  
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add destinations.py tests/test_destinations.py
git commit -m "Voeg destinations-logica toe (match + padresolutie)."
```

---

### Task 2: `recovery.save_transcript` met optionele map

**Files:**
- Modify: `recovery.py`
- Modify: `tests/test_recovery.py`

**Interfaces:**
- Consumes: default `transcripts_dir()`
- Produces: `save_transcript(text: str, directory: Path | None = None) -> Path`  
  — als `directory` is gezet en ≠ default: **geen** `prune_transcripts()`

- [ ] **Step 1: Failing test**

```python
def test_save_transcript_custom_dir_skips_prune(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)
    custom = tmp_path / "project"
    path = recovery.save_transcript("hallo", directory=custom)
    assert path.parent == custom
    assert path.read_text(encoding="utf-8") == "hallo"
    # Vul defaultmap met > MAX en bewaar custom — prune mag custom niet raken
```

(Uitbreiden: schrijf 3 files in default met max_files=2 via prune-test patroon; custom file blijft.)

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_recovery.py::test_save_transcript_custom_dir_skips_prune -v`

- [ ] **Step 3: Implement**

In `save_transcript`:

```python
def save_transcript(text: str, directory: Path | None = None) -> Path:
    default = transcripts_dir()
    target_dir = directory if directory is not None else default
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_path(target_dir, _timestamp(), ".txt")
    tmp = target.with_name(target.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)
    tmp.replace(target)
    if target_dir.resolve() == default.resolve():
        prune_transcripts()
    return target
```

- [ ] **Step 4: Run all recovery tests — PASS**

Run: `pytest tests/test_recovery.py -q`

- [ ] **Step 5: Commit**

```bash
git add recovery.py tests/test_recovery.py
git commit -m "Sta transcript-opslag in een gekozen map toe zonder prune."
```

---

### Task 3: Opnamesessie — command takes

**Files:**
- Modify: `opnamesessie.py`
- Modify: `tests/test_opnamesessie.py`

**Interfaces:**
- Consumes: `match_command`, injecteerbare `on_destination_command: Callable[[str, str | None], None] | None`
- Produces: bij `("set"|"reset")`: callback aanroepen, **geen** copy/paste/save van inhoud; notify idle; `on_ready`
- Sessie-attributen: `destinations: list[dict]`, `active_destination: str | None`, of liever alleen callback + matchlist via constructor/`set_destinations`

Aanbevolen injectie:

```python
# in __init__
on_destination_command: Callable[[str, str | None], None] | None = None
# ("set", name) of ("reset", None)
get_destinations: Callable[[], list[dict[str, str]]] | None = None
```

In `_transcribe_audio` na `transcript = ...`:

```python
dests = self._get_destinations() if self._get_destinations else []
kind, name = match_command(transcript, dests)
if kind in ("set", "reset"):
    if self._on_destination_command:
        self._on_destination_command(kind, name)
    print(...)  # i18n keys destination.switched / destination.reset
    return  # finally: notify idle + on_ready
# anders bestaande save/paste flow
```

- [ ] **Step 1: Failing test** — fake model returns `"boodschappenlijst"`; destinations list contains that name; assert paste_calls==0 and command callback fired with `("set", ...)`

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Minimal wiring in `opnamesessie.py`**

- [ ] **Step 4: Tests PASS** (bestaande + nieuw)

- [ ] **Step 5: Commit**

```bash
git add opnamesessie.py tests/test_opnamesessie.py
git commit -m "Behandel exacte bestemmingsnamen als sticky commando-takes."
```

---

### Task 4: dictation wiring + config + map openen helper

**Files:**
- Modify: `dictation.py`
- Modify: `host/_win.py` of kleine helper in `destinations.py`: `open_in_explorer(path: Path) -> None` via `os.startfile`

**Interfaces:**
- Config keys: `destinations`, `active_destination`
- `handle_destination_command(kind, name)` → update globals, `config.save_config`, `indicator.set_destination(...)`
- `_save_transcript_routed(text)` → `recovery.save_transcript(text, directory=resolve_save_dir(...))`
- Settings apply: destinations list + active

- [ ] **Step 1:** Laad/sanitise destinations bij startup; bouw session met callbacks
- [ ] **Step 2:** `current_settings` / `apply_settings` uitbreiden
- [ ] **Step 3:** Helper `open_folder(path: Path)` (Windows `os.startfile`)
- [ ] **Step 4:** Handmatige smoke: config.json schrijven met één bestemming (geen UI nog) — of unit-test resolve via dictation helpers als die puur genoeg zijn
- [ ] **Step 5: Commit**

```bash
git commit -m "Koppel bestemmingen aan config en transcript-opslag."
```

---

### Task 5: Pill toont sticky bestemming

**Files:**
- Modify: `indicator.py`

**Gedrag:**
- Nieuw canvas-item `_destination` (kleinere tekst onder/naast label) of hergebruik tag-gebied in idle
- `set_destination(name: str | None)` op hoofdthread
- Als `name` gezet: bij IDLE **niet** verbergen — toon venster met alleen bestemmingsnaam (gedempt)
- Als `name` is None: huidig idle-gedrag (verbergen)

- [ ] **Step 1:** `set_destination` + render in `_apply_state` / idle branch
- [ ] **Step 2:** Handmatig of kleine test als er indicator-tests bestaan; anders manuele checklist
- [ ] **Step 3: Commit**

```bash
git commit -m "Toon actieve bestemming op de status-pill."
```

---

### Task 6: Bestemmingen-dialoog + tray-item (niet in Instellingen)

**Files:**
- Create: `destinations_dialog.py` (of uitbreiding `settings.py` met aparte `open_destinations_dialog`)
- Modify: `tray.py` — menu: Instellingen, Bestemmingen, Help, separator, Afsluiten
- Modify: `dictation.py` — `on_destinations` → `call_on_main` → dialoog
- Modify: `locales/nl.json`, `en.json`, `de.json`

**UI (eigen venster):**
- Lijst bestemmingen (naam + pad), knoppen Toevoegen / Wijzigen / Verwijderen / Actief zetten / Wissen actief
- Folder browse: `tkinter.filedialog.askdirectory`
- Knoppen: “Transcriptmap openen”, “Actieve map openen”
- **Niet** opnemen in het algemene Instellingen-dialoog

**i18n:** `tray.destinations`, `destinations.*` labels

- [ ] **Step 1:** Dialoog + save via bestaande `apply_settings` of dedicated apply-callback
- [ ] **Step 2:** Tray + wiring
- [ ] **Step 3:** Locale strings
- [ ] **Step 4: Commit**

```bash
git commit -m "Voeg Bestemmingen-traydialoog toe."
```

---

### Task 7: Help tray-item + dialog + user docs

**Files:**
- Create: `help_dialog.py`
- Create: `docs/user/help.nl.md`, `help.en.md`, `help.de.md`
- Modify: `tray.py` — `on_help` callback; menu: Instellingen, Help, separator, Afsluiten
- Modify: `dictation.py` — open help via `indicator.call_on_main`
- Modify: `praatMaar.spec` datas `docs/user`; `pyproject.toml` modules
- Modify: `locales/*.json` — `tray.help`

**Help-inhoud (alle talen, zelfde structuur):**
1. Wat is een bestemming / sticky / pill
2. Wisselen: hele take = exacte naam; reset met “standaard”
3. Waar bestanden landen; knop transcriptmap
4. Risico’s: Whisper-mishoor (geen match = veilig); generieke namen; bestanden onversleuteld

Laden: `Path` naast repo of `sys._MEIPASS / "docs/user"`. Fallback: korte i18n-string als file ontbreekt.

- [ ] **Step 1:** Schrijf de drie markdown-bestanden (volledige tekst, geen TODO)
- [ ] **Step 2:** `help_dialog.open_help(parent)` — ScrolledText readonly
- [ ] **Step 3:** Tray + wiring
- [ ] **Step 4:** Bundle in spec
- [ ] **Step 5: Commit**

```bash
git commit -m "Voeg Help-menu en gebruikersdocumentatie toe."
```

---

### Task 8: Integratie, CONTEXT/CHANGELOG, pytest

**Files:**
- Modify: `CONTEXT.md` — term “bestemming”
- Modify: `CHANGELOG.md`
- Modify: `README.md` — korte vermelding Help + bestemmingen

- [ ] **Step 1:** `pytest -q` — all green
- [ ] **Step 2:** Docs bijwerken
- [ ] **Step 3:** Commit

```bash
git commit -m "Documenteer bestemmingen en Help in CONTEXT/CHANGELOG."
```

---

## Spec coverage check

| Spec-eis | Task |
|----------|------|
| Config destinations + active | 4, 6 |
| Opslaan in actieve map; prune alleen default | 2, 4 |
| Exacte stem-match; geen paste; reset standaard | 1, 3 |
| Pill sticky zichtbaar | 5 |
| Instellingen CRUD + map openen | 6 |
| Help tray-item + werking/risico’s | 7 |
| i18n nl/en/de | 6, 7 |
| Geen fuzzy / geen extra hotkey | — (niet gebouwd) |

## Placeholder scan

Geen TBD/TODO in stappen; testcode en kern-API’s concreet.
