# Incremental live-paste Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Prefer `/agent-handoff` per task when dispatching praatMaar specialists.

**Goal:** Optionele live-plak onder Incrementele transcriptie: chunk- en staart-delta’s via klembord + `host.paste()` naar het actieve veld, met optioneel klembord-herstellen.

**Spec:** [docs/superpowers/specs/2026-08-10-incremental-live-paste-design.md](../specs/2026-08-10-incremental-live-paste-design.md)

**ADR:** n/a (bouwt op ADR-0001 host-seam; geen nieuw ADR in v1)

**Architecture:** `Opnamesessie` houdt bij welke tekst al live geplakt is. Bij chunk-commit en bij stop-staart: alleen de delta → injecteerbare `copy_text` → modifier-clear → `paste_delay` → `host.paste()`. Bij live-plak aan: skip `match_command` en skip volle eind-plak/`auto_paste`. Clipboard snapshot/restore via injecteerbare hooks (platform-implementatie achter `host` / dictation helpers). UI + config in Modules-blok incremental.

**Tech stack:** Python 3, pytest, bestaande `Opnamesessie` / `FakeHost`, pyperclip + Qt-clipboard-fallback, PySide6 Modules-dialoog, `host` adapters.

## Global constraints

- Geen commits op `main`; branch: `cursor/incremental-live-paste`
- Geen app kill/restart tenzij de gebruiker dat vraagt
- Injectie v1 = **alleen** klembord + bestaande `host.paste()` — geen SendInput/typen/hybride
- `incremental_live_paste` default `false`; `incremental_live_paste_restore_clipboard` default `true`
- Live-plak alleen effectief als `incremental_transcription` ook aan staat
- Live aan ⇒ `auto_paste` negeren voor inserts; géén bestemmings-spraakcommando’s
- Snapshot bij **start** van een live-sessie (na succesvolle opname-start); restore in **alle** eindpaden (succes / te kort / geen speech / fout) als restore aan stond en er een snapshot was
- Geen OS-API’s in `dictation.py` buiten bestaande clipboard-helpers; nieuwe restore-logica in `host` of dunne helper die platform-adapters aanroept
- Linux: best-effort; Wayland niet beloven in copy

## File map

| File | Role |
|------|------|
| `opnamesessie.py` | Flags, delta-boekhouding, live paste bij chunk/staart, skip command/full-paste |
| `dictation.py` | Config load/save/apply; wire copy + clipboard snapshot/restore hooks |
| `host/__init__.py` | Optionele Protocol-methods of module-helpers voor clipboard snapshot/restore |
| `host/_win.py` | Windows clipboard snapshot/restore (best-effort) |
| `host/_mac.py` | macOS pasteboard snapshot/restore (+ changeCount-guard) |
| `host/_linux.py` | Linux best-effort via pyperclip/Qt text only |
| `ui/dialogs/modules.py` | Live-plak + restore checkboxes in incremental-blok |
| `locales/{nl,en,de}.json` | UI-strings |
| `docs/user/help.{nl,en,de}.md` | Gebruikersuitleg + limieten |
| `SECURITY.md` | Korte noot live-plak / klembord |
| `docs/STATUS.md` | Korte vermelding onder incremental / experimenteel indien nodig |
| `CHANGELOG.md` | Unreleased entry |
| `tests/test_live_paste.py` | Opnamesessie live-plak gedrag (FakeHost) |
| `tests/test_clipboard_restore.py` | Snapshot/restore helpers / FakeHost hooks |
| `tests/test_modules_dialog.py` of bestaande modules-tests | Settings round-trip UI |

## Task order overview

1. Opnamesessie live-paste core (TDD) — delta, chunk/staart paste, skip command & full paste
2. Clipboard snapshot/restore seam + wiring
3. Config + dictation apply
4. Modules UI + locales
5. Docs (help / SECURITY / STATUS / CHANGELOG)
6. Integratie-verificatie tegen spec ACs

---

### Task 1: Opnamesessie live-paste core (TDD)

**Owner:** `core-python-architect`  
**Consult:** `audio-speech`  
**Review:** `/code-review` na Task 3–4 of bij PR  
**Depends on:** none

**Files:**
- Modify: `opnamesessie.py`
- Create: `tests/test_live_paste.py`

**In scope:**
- [ ] Flags `incremental_live_paste: bool = False` op `Opnamesessie.__init__` / attribuut
- [ ] Boekhouding `_live_pasted_text: str` (reset bij sessie-start / te-kort / cancel-paden die chunks wissen)
- [ ] Helper `_live_paste_enabled() -> bool` = incremental én live_paste
- [ ] `_paste_delta(text: str) -> None`: strip; als leeg return; serialiseer met lock/event; `copy_text(delta)`; `wait_until_modifiers_clear()`; `sleep(paste_delay_seconds)`; `host.paste()`; append delta aan `_live_pasted_text` (met spatie-regel consistent met chunk-join: zelfde als `" ".join` — delta = nieuw piece_text zoals gecommit)
- [ ] Na succesvolle chunk-commit in `_try_commit_chunk`: als live aan en `piece_text`: `_paste_delta(piece_text)` (niet de volle combined opnieuw)
- [ ] In `_finalize_chunk_transcript` / pad naar `_apply_transcript`: als live aan, staart-piece apart plakken vóór of via aangepaste apply — **alleen** nog niet geplakte staart-tekst
- [ ] `_apply_transcript`: als `_live_paste_enabled()`: **skip** `match_command`-branch; save/events zoals nu; **geen** `resolve_auto_paste` volle plak; wél eventuele **staart-delta** als die nog niet geplakt is (als staart al in finalize geplakt is, hier niets plakken)
- [ ] Live uit: gedrag ongewijzigd (bestaande tests groen)

**Out of scope:**
- Clipboard restore
- Modules UI / config keys
- `insert_text` op Host-Protocol

**Interfaces:**
- Consumes: bestaande `copy_text`, `wait_until_modifiers_clear`, `host.paste()`, `_chunk_transcripts`, `_try_commit_chunk`, `_apply_transcript`
- Produces:
  - `Opnamesessie.incremental_live_paste: bool`
  - `Opnamesessie._live_pasted_text: str`
  - `Opnamesessie._live_paste_enabled() -> bool`
  - `Opnamesessie._paste_delta(delta: str) -> None`

**Implementation notes:**

Delta-regel (v1, eenvoudig en testbaar): elk gecommit `piece_text` / staart-stuk wordt **eenmaal** als delta geplakt. Track `_live_pasted_chunks: list[str]` of plak direct na commit en houd `_live_pasted_text = " ".join(pasted_pieces)`. Bij stop: als finalize een extra staart-string append aan texts, plak die staart-string als die nieuw is.

Serialisatie: één `threading.Lock` (`_live_paste_lock`) rond copy+paste zodat chunk-worker en finalize-thread niet overlappen.

Voorbeeld testopzet:

```python
def test_live_paste_pastes_chunk_deltas_not_full_transcript(tmp_path, monkeypatch):
    pastes: list[str] = []
    clipboard: list[str] = []

    class TrackingHost:
        def paste(self) -> None:
            pastes.append(clipboard[-1] if clipboard else "")

    # Build Opnamesessie with incremental_transcription=True,
    # incremental_live_paste=True, auto_paste=False,
    # copy_text=clipboard.append, Fake stream/model returning
    # ["alfa", "beta"] then empty/short tail…
    # Drive record → enough audio for two commits → stop
    assert clipboard == ["alfa", "beta"]  # of + staart
    assert "alfa beta" not in clipboard  # geen volle herplak
    assert pastes == clipboard
```

Andere tests in hetzelfde bestand:
- `auto_paste=False` + live aan → toch pastes
- live aan → `on_destination_command` niet aangeroepen als transcript exact een bestemmingsnaam is
- lege piece_text → geen paste
- live uit → bestaande eind-plak via auto_paste (regressie-smoke)

- [ ] **Step 1:** Schrijf falende tests in `tests/test_live_paste.py`
- [ ] **Step 2:** Run `pytest tests/test_live_paste.py -v` → FAIL
- [ ] **Step 3:** Implementeer minimale wijzigingen in `opnamesessie.py`
- [ ] **Step 4:** `pytest tests/test_live_paste.py tests/test_incremental_transcription.py tests/test_opnamesessie.py -v` → PASS
- [ ] **Step 5:** Commit `feat: live-paste chunk and tail deltas in Opnamesessie`

**Verification:**
- [ ] Automated: commands hierboven
- [ ] Manual: n/a in deze task

**Completion criteria:**
- Maps to AC-1, AC-2, AC-3, AC-4, AC-7 (core-gedrag)

**Handoff:** `/agent-handoff` → `core-python-architect`

---

### Task 2: Clipboard snapshot / restore seam

**Owner:** `core-python-architect` (injectables + tests) met platform-slices  
**Consult:** `windows-platform`, `macos-platform`, `linux-platform`, `privacy-security`  
**Depends on:** Task 1

**Files:**
- Modify: `host/__init__.py`, `host/_win.py`, `host/_mac.py`, `host/_linux.py`
- Modify: `opnamesessie.py` (hooks aanroepen)
- Modify: `dictation.py` (wire hooks → host)
- Create: `tests/test_clipboard_restore.py`

**In scope:**
- [ ] Host-helpers (module-level of Protocol-optional methods — kies één patroon en gebruik overal):

```python
# Voorkeur v1: module-functies die default host aanroepen + injecteerbaar in Opnamesessie
def snapshot_clipboard() -> object | None: ...
def restore_clipboard(snapshot: object | None) -> None: ...
```

  Snapshot opaque (`object | None`); `None` = niets te restoren / niet ondersteund.

- [ ] Windows: plain-text snapshot via pyperclip of Win32 CF_UNICODETEXT; restore best-effort; geen crash bij lege/exotische formats
- [ ] macOS: general pasteboard string + `changeCount` bij snapshot; restore alleen als changeCount ongewijzigd is *of* alleen door ons is gewijzigd (documenteer gekozen guard)
- [ ] Linux: text-only via bestaande copy-pad / pyperclip; best-effort
- [ ] `Opnamesessie`: injecteer `snapshot_clipboard` / `restore_clipboard` (default no-op); flag `incremental_live_paste_restore_clipboard: bool = True`
- [ ] Bij start recording wanneer `_live_paste_enabled()` en restore-flag: `_clipboard_snapshot = snapshot_clipboard()`
- [ ] Bij elk sessie-einde dat een live-sessie was (succes apply, too short, no speech, error notify-paden die cycle afronden): als restore-flag en snapshot gezet → `restore_clipboard`; clear snapshot
- [ ] Restore **uit**: snapshot niet nemen (of wel nemen maar niet restoren — kies: **niet snapshotten** als restore uit, simpeler)

**Out of scope:**
- Per-chunk restore
- Perfecte multi-format clipboard (files, HTML) — plain text is genoeg voor v1; documenteer limitatie

**Interfaces:**
- Produces: `host.snapshot_clipboard() -> object | None`, `host.restore_clipboard(snapshot: object | None) -> None`
- Opnamesessie ctor kwargs: `snapshot_clipboard`, `restore_clipboard`, `incremental_live_paste_restore_clipboard`

- [ ] **Step 1:** Tests met fake snapshot/restore counters op Opnamesessie (zonder echte OS-clipboard)
- [ ] **Step 2:** Host-adapters implementeren; unit-test pure “None snapshot = no-op restore”
- [ ] **Step 3:** Wire in `dictation.py` naar `host.snapshot_clipboard` / `restore_clipboard`
- [ ] **Step 4:** `pytest tests/test_clipboard_restore.py tests/test_live_paste.py -v`
- [ ] **Step 5:** Commit `feat: clipboard snapshot restore for live-paste`

**Verification:**
- [ ] Automated: pytest hierboven
- [ ] Manual (later / Task 6): macOS TextEdit sessie + verify clipboard restored

**Completion criteria:**
- Maps to AC-6

**Handoff:** core + korte platform-consult voor Win/Mac adapters indien nodig

---

### Task 3: Config + dictation wiring

**Owner:** `core-python-architect`  
**Consult:** —  
**Depends on:** Task 1–2

**Files:**
- Modify: `dictation.py` (globals, `get_settings`/`apply_settings`, `Opnamesessie(...)` ctor)
- Test: uitbreiden `tests/test_live_paste.py` of kleine config-test als die patterns bestaan

**In scope:**
- [ ] Load:

```python
INCREMENTAL_LIVE_PASTE = bool(_user_config.get("incremental_live_paste", False))
INCREMENTAL_LIVE_PASTE_RESTORE_CLIPBOARD = bool(
    _user_config.get("incremental_live_paste_restore_clipboard", True)
)
```

- [ ] Include in settings dicts die Modules-dialoog voedt / opslaat (zelfde plekken als `incremental_transcription`)
- [ ] `apply_settings`: update globals + `session.incremental_live_paste` / `session.incremental_live_paste_restore_clipboard`
- [ ] Ctor: doorgeven aan `Opnamesessie(...)`

- [ ] **Step 1:** Grep bestaande incremental keys in `dictation.py`; mirror voor de twee nieuwe keys op **alle** load/save/apply sites
- [ ] **Step 2:** Smoke-test: settings round-trip via apply (of unit op extract als beschikbaar)
- [ ] **Step 3:** Commit `feat: config keys for incremental live-paste`

**Verification:**
- [ ] Automated: gerichte pytest + eventueel handmatige Modules save later in Task 4
- [ ] Maps to AC-5 (defaults)

**Completion criteria:**
- Keys persistent in `config.json`; runtime flags updaten zonder herstart waar andere incremental flags dat ook doen

---

### Task 4: Modules UI + locales

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design` (copy/layout)  
**Depends on:** Task 3

**Files:**
- Modify: `ui/dialogs/modules.py`
- Modify: `locales/nl.json`, `locales/en.json`, `locales/de.json`
- Test: bestaande modules-dialog tests indien aanwezig; anders lichte test op `result()` dict keys

**In scope:**
- [ ] Onder incremental-opties (na seam-note of vóór), genest:
  - `QCheckBox` / Toggle: Live plakken — enabled alleen als incremental-switch aan
  - Hint-label met klembord-waarschuwing
  - Nested checkbox: Klembord na afloop herstellen — enabled alleen als live-plak aan
- [ ] `_sync_incremental_style` (of nieuw sync): disable nested controls als parent uit
- [ ] `result()` / save payload include beide keys
- [ ] i18n keys (exact):

```text
modules.incremental_live_paste
modules.incremental_live_paste_hint
modules.incremental_live_paste_restore
```

Voorbeeld NL:
- title: `Live plakken`
- hint: `Plakt elk afgerond stuk tekst via het klembord in het actieve veld. Tijdens dicteren wordt je klembord tijdelijk overschreven.`
- restore: `Klembord na afloop herstellen`

EN/DE equivalent, geen mixed-language in één string.

- [ ] **Step 1:** Locales toevoegen
- [ ] **Step 2:** UI controls + enable/disable wiring
- [ ] **Step 3:** Test save dict bevat defaults/false/true correct
- [ ] **Step 4:** Commit `feat: modules UI for live-paste options`

**Verification:**
- [ ] Automated: dialog result keys
- [ ] Manual: open Modules, incremental uit → live controls disabled; incremental aan → live uit → restore disabled
- [ ] Maps to AC-5

**Completion criteria:**
- Gebruiker kan beide opties zetten; defaults matchen spec

---

### Task 5: Docs

**Owner:** skill `/update-documentation` (of core met die skill)  
**Consult:** `privacy-security` voor SECURITY-zin  
**Depends on:** Task 4

**Files:**
- Modify: `docs/user/help.nl.md`, `docs/user/help.en.md`, `docs/user/help.de.md`
- Modify: `SECURITY.md` (korte bullet onder klembord)
- Modify: `docs/STATUS.md` (één regel bij incremental / modules)
- Modify: `CHANGELOG.md` `[Unreleased]`

**In scope:**
- [ ] Help: uitleg live-plak, klembord, restore-optie, limieten (focus, elevated/UIPI, password fields, Linux X11 best-effort / Wayland niet beloven)
- [ ] SECURITY: live-plak zet delta’s op klembord; restore verkleint nabewerking
- [ ] CHANGELOG: feature-regel
- [ ] STATUS: vermelding indien passend bij “ondersteund / experimenteel”

- [ ] **Step 1:** Docs bijwerken
- [ ] **Step 2:** Commit `docs: live-paste help and changelog`

**Verification:**
- [ ] Manual read-through nl/en/de consistency
- [ ] Maps to AC-5 (transparantie klembord)

**Completion criteria:**
- Geen claim van echte word-streaming; geen Wayland-belofte

---

### Task 6: Integratie-verificatie (AC gate)

**Owner:** `quality-release`  
**Consult:** `product-owner`  
**Depends on:** Task 1–5

**Files:** n/a (evidence only)

**In scope:**
- [ ] Run: `pytest tests/test_live_paste.py tests/test_clipboard_restore.py tests/test_incremental_transcription.py tests/test_opnamesessie.py -v`
- [ ] Run: `ruff check` op gewijzigde files + `ruff format --check`
- [ ] Map elke spec AC 1–7 naar evidence (testnaam of handmatige check)
- [ ] Handmatig Windows (primair): Notepad live chunks; auto_paste uit; restore aan; bestemmingsnaam dicteren terwijl live aan → geen switch; Modules defaults
- [ ] Handmatig macOS indien beschikbaar: TextEdit + clipboard restore
- [ ] Linux: optioneel X11 smoke — niet blocking voor merge als Windows+tests groen

**Out of scope:**
- Release tag

**Completion criteria:**
- Alle ACs met evidence; `product-owner` kan accepteren

**Handoff:** `quality-release` → `product-owner`

---

## Spec coverage (self-review)

| AC / eis | Task |
|----------|------|
| AC-1 chunk-delta’s tijdens opname | 1, 6 |
| AC-2 staart-delta, geen dubbele volle plak | 1, 6 |
| AC-3 auto_paste uit + live aan | 1 |
| AC-4 geen bestemmingscommando’s | 1 |
| AC-5 defaults + copy klembord | 3, 4, 5 |
| AC-6 restore | 2, 6 |
| AC-7 live/incremental uit = oud gedrag | 1 |
| Injectie = klembord+paste | 1 (constraint) |
| host snapshot/restore | 2 |
| UI Modules | 4 |
| Docs/privacy | 5 |

**Uitgesteld (spec non-goals):** typen, hybride, `insert_text` Protocol-uitbreiding, Wayland parity, pill partials.
