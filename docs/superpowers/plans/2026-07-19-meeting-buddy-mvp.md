# Meeting Buddy MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lever de verticale MVP-snede: microfooncapture → incrementele STT → immutable Meeting State → heuristische hints in een compacte overlay, zonder transcriptviewer en zonder dictee te breken.

**Architecture:** Drie units via capabilities: `audio-capture` publiceert `AudioChunk`-events; `speech-to-text` consumeert chunks en publiceert `TranscriptDelta`s via `SharedWhisper`; `meeting-buddy` orkestreert sessies, past heuristieken toe via `StateProposal` → immutable `MeetingState` vN, en toont max. 3 hints. Geen PCM in Meeting Buddy; geen nieuwe `CycleEvent`-types.

**Tech Stack:** Python 3.10+, bestaande `modules/` + `CapabilityRegistry` + `SharedWhisper`, `sounddevice` (mic), PyYAML (drempels), tkinter overlay via `ui_dispatch`, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-07-19-meeting-buddy-mvp-design.md`

## Global Constraints

- Windows-first continuous mic; geen loopback/system-audio in deze slice
- Meeting Buddy consumeert **geen** PCM — alleen `TranscriptDelta` + capture status/fouten
- `MeetingStateService` muteert nooit in-place: altijd vN → vN+1
- Heuristieken primair; `ai.semantic_analysis` hoogstens Protocol + contracttest, geen runtime-stub
- Speaker default `UNKNOWN` (optioneel `audio.speaker_detection`)
- Actief dictee heeft voorrang op Buddy-STT; geen stille drops (gap-events)
- Drempels in `meeting-buddy.yaml`, niet als magic numbers
- Module enablement via bestaande `config.json` / Modules-UI
- Geen transcript in overlay; max 3 hints; twijfel → geen hint
- Fout in module mag dictee nooit crashen
- Branch-regel: werk op feature-branch, nooit commit op `main`

**PR-checkpoints (aanbevolen):** na Task 3 (capture+STT contracts werkend met fakes), na Task 7 (Buddy core zonder overlay), na Task 10 (E2E tray+overlay).

---

## File map

| File | Rol |
|------|-----|
| `modules/capabilities/continuous_capture.py` | Contract `audio.continuous_capture` + events/types |
| `modules/capabilities/speech_to_text.py` | Contract `transcription.speech_to_text` + `TranscriptDelta` |
| `modules/capabilities/semantic_analysis.py` | Protocol-only `ai.semantic_analysis` (geen provider) |
| `modules/_builtin/audio_capture.py` | Mic capture module + capability provider (Windows) |
| `modules/_builtin/speech_to_text.py` | STT module: chunks → deltas, SharedWhisper, backpressure |
| `modules/_builtin/meeting_buddy/__init__.py` | Export `MeetingBuddyModule` |
| `modules/_builtin/meeting_buddy/module.py` | PraatMaarModule + tray actions |
| `modules/_builtin/meeting_buddy/prep.py` | Agenda-tekst → topics |
| `modules/_builtin/meeting_buddy/state.py` | Entities + immutable `MeetingState` |
| `modules/_builtin/meeting_buddy/state_service.py` | `StateProposal` → vN+1 |
| `modules/_builtin/meeting_buddy/heuristics.py` | Topic/question/action proposals |
| `modules/_builtin/meeting_buddy/hints.py` | Hint Engine (3 types) |
| `modules/_builtin/meeting_buddy/config.py` | Load defaults + user `meeting-buddy.yaml` |
| `modules/_builtin/meeting_buddy/orchestrator.py` | Sessies starten/stoppen, wiring |
| `modules/_builtin/meeting_buddy/overlay.py` | Compacte tkinter overlay |
| `modules/_builtin/meeting_buddy/observability.py` | Debug-events (geen transcript in logs) |
| `modules/defaults/meeting-buddy.yaml` | Shipped defaults |
| `modules/registry.py` | Registreer nieuwe builtins |
| `modules/whisper.py` | Non-blocking / busy-aware acquire voor Buddy |
| `requirements.txt` / `pyproject.toml` | `PyYAML` |
| `locales/{nl,en,de}.json` | Module- + actielabels |
| `tests/test_continuous_capture_contract.py` | … |
| `tests/test_speech_to_text_*.py` | … |
| `tests/test_meeting_buddy_*.py` | … |

---

### Task 1: Capability-contract `audio.continuous_capture`

**Files:**
- Create: `modules/capabilities/continuous_capture.py`
- Create: `tests/test_continuous_capture_contract.py`
- Modify: `modules/capabilities/__init__.py` (re-export indien het project dat doet)

**Interfaces:**
- Produces:
  - `CAPABILITY_ID = "audio.continuous_capture"`
  - `CONTRACT_VERSION = 1`
  - `AudioChunk` (frozen dataclass)
  - `CaptureStatus` (StrEnum)
  - Event dataclasses: `AudioChunkReceived`, `CaptureStatusChanged`, `CaptureStopped`, `CaptureGap`
  - `ContinuousCaptureCapability` Protocol

- [ ] **Step 1: Write the failing test**

```python
# tests/test_continuous_capture_contract.py
from modules.capabilities.continuous_capture import (
    CAPABILITY_ID,
    AudioChunk,
    CaptureStatus,
    ContinuousCaptureCapability,
)


def test_capability_id():
    assert CAPABILITY_ID == "audio.continuous_capture"


def test_audio_chunk_is_frozen():
    chunk = AudioChunk(
        session_id="c1",
        chunk_id="1",
        start_ms=0,
        end_ms=100,
        sample_rate=16000,
        pcm_f32=b"",  # of memoryview/bytes van float32
        source="microphone",
    )
    assert chunk.session_id == "c1"
    try:
        chunk.session_id = "x"  # type: ignore[misc]
        raise AssertionError("expected frozen")
    except Exception:
        pass


def test_protocol_methods_exist():
    assert hasattr(ContinuousCaptureCapability, "start_session")
    assert hasattr(ContinuousCaptureCapability, "subscribe")
    assert hasattr(ContinuousCaptureCapability, "stop_session")
    assert hasattr(ContinuousCaptureCapability, "get_status")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_continuous_capture_contract.py -v`  
Expected: FAIL (import error / module not found)

- [ ] **Step 3: Write minimal implementation**

```python
# modules/capabilities/continuous_capture.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

CAPABILITY_ID = "audio.continuous_capture"
CONTRACT_VERSION = 1

CaptureEventHandler = Callable[[Any], None]


class CaptureStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True)
class CaptureSession:
    session_id: str


@dataclass(frozen=True)
class AudioChunk:
    session_id: str
    chunk_id: str
    start_ms: int
    end_ms: int
    sample_rate: int
    pcm_f32: bytes  # little-endian float32 mono
    source: str = "microphone"


@dataclass(frozen=True)
class AudioChunkReceived:
    chunk: AudioChunk


@dataclass(frozen=True)
class CaptureStatusChanged:
    session_id: str
    status: CaptureStatus
    message: str | None = None


@dataclass(frozen=True)
class CaptureStopped:
    session_id: str
    reason: str  # "user" | "error" | …


@dataclass(frozen=True)
class CaptureGap:
    session_id: str
    start_ms: int
    end_ms: int
    reason: str


@runtime_checkable
class ContinuousCaptureCapability(Protocol):
    def start_session(self, config: dict[str, Any] | None = None) -> CaptureSession: ...

    def subscribe(self, session_id: str, handler: CaptureEventHandler) -> None: ...

    def unsubscribe(self, session_id: str, handler: CaptureEventHandler) -> None: ...

    def stop_session(self, session_id: str) -> None: ...

    def get_status(self, session_id: str) -> CaptureStatus: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_continuous_capture_contract.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/capabilities/continuous_capture.py tests/test_continuous_capture_contract.py
git commit -m "Add audio.continuous_capture capability contract."
```

---

### Task 2: Capability-contract `transcription.speech_to_text` + semantic Protocol

**Files:**
- Create: `modules/capabilities/speech_to_text.py`
- Create: `modules/capabilities/semantic_analysis.py`
- Create: `tests/test_speech_to_text_contract.py`

**Interfaces:**
- Produces:
  - `TranscriptDelta`, `SpeechToTextCapability`
  - Events: `TranscriptDeltaReceived`, `TranscriptionStatusChanged`, `TranscriptGap`
  - `SemanticAnalysisCapability` Protocol only (`CAPABILITY_ID = "ai.semantic_analysis"`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_speech_to_text_contract.py
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID,
    TranscriptDelta,
    SpeechToTextCapability,
)
from modules.capabilities import semantic_analysis as sa


def test_ids():
    assert CAPABILITY_ID == "transcription.speech_to_text"
    assert sa.CAPABILITY_ID == "ai.semantic_analysis"


def test_delta_fields():
    d = TranscriptDelta(
        session_id="t1",
        sequence=1,
        start_ms=0,
        end_ms=3000,
        text="hallo",
        is_final=True,
        confidence=0.9,
    )
    assert d.sequence == 1
    assert d.is_final is True
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_speech_to_text_contract.py -v`

- [ ] **Step 3: Implement contracts**

```python
# modules/capabilities/speech_to_text.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

CAPABILITY_ID = "transcription.speech_to_text"
CONTRACT_VERSION = 1

SttEventHandler = Callable[[Any], None]


class TranscriptionStatus(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    DELAYED = "delayed"
    ERROR = "error"


@dataclass(frozen=True)
class TranscriptionSession:
    session_id: str


@dataclass(frozen=True)
class TranscriptDelta:
    session_id: str
    sequence: int
    start_ms: int
    end_ms: int
    text: str
    is_final: bool
    confidence: float


@dataclass(frozen=True)
class TranscriptDeltaReceived:
    delta: TranscriptDelta


@dataclass(frozen=True)
class TranscriptionStatusChanged:
    session_id: str
    status: TranscriptionStatus
    message: str | None = None


@dataclass(frozen=True)
class TranscriptGap:
    session_id: str
    start_ms: int
    end_ms: int
    reason: str


@runtime_checkable
class SpeechToTextCapability(Protocol):
    def start_session(
        self,
        *,
        capture_session_id: str,
        capture: Any,  # ContinuousCaptureCapability
        config: dict[str, Any] | None = None,
    ) -> TranscriptionSession: ...

    def subscribe(self, session_id: str, handler: SttEventHandler) -> None: ...

    def unsubscribe(self, session_id: str, handler: SttEventHandler) -> None: ...

    def stop_session(self, session_id: str) -> None: ...

    def get_status(self, session_id: str) -> TranscriptionStatus: ...
```

```python
# modules/capabilities/semantic_analysis.py
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

CAPABILITY_ID = "ai.semantic_analysis"
CONTRACT_VERSION = 1


@runtime_checkable
class SemanticAnalysisCapability(Protocol):
    """MVP: geen provider. Contract voor latere lokale AI."""

    def analyze_delta(self, delta: Any, state_snapshot: Any) -> list[Any]: ...
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/capabilities/speech_to_text.py modules/capabilities/semantic_analysis.py tests/test_speech_to_text_contract.py
git commit -m "Add speech_to_text and semantic_analysis capability contracts."
```

---

### Task 3: In-memory capture + STT fakes (integratie zonder hardware)

**Files:**
- Create: `modules/testing/fake_capture.py`
- Create: `modules/testing/fake_stt.py`
- Create: `tests/test_capture_stt_wiring.py`

**Interfaces:**
- Produces: `FakeContinuousCapture`, `FakeSpeechToText` die echte contracts volgen
- Consumes: contracts uit Task 1–2

Doel: Meeting Buddy (later) en STT kunnen zonder mic/Whisper getest worden. Fake capture pusht `AudioChunkReceived`; Fake STT zet chunk → vaste `TranscriptDelta`.

- [ ] **Step 1: Write failing integration test**

```python
# tests/test_capture_stt_wiring.py
from modules.testing.fake_capture import FakeContinuousCapture
from modules.testing.fake_stt import FakeSpeechToText
from modules.capabilities.continuous_capture import AudioChunkReceived
from modules.capabilities.speech_to_text import TranscriptDeltaReceived


def test_stt_subscribes_and_emits_delta():
    capture = FakeContinuousCapture()
    stt = FakeSpeechToText(text_for_chunk=lambda c: "hallo wereld")
    deltas: list = []

    cs = capture.start_session()
    ts = stt.start_session(capture_session_id=cs.session_id, capture=capture)
    stt.subscribe(ts.session_id, lambda ev: deltas.append(ev) if isinstance(ev, TranscriptDeltaReceived) else None)

    capture.emit_seconds(0.1)  # synthetische chunk
    assert any(isinstance(d, TranscriptDeltaReceived) for d in deltas)
    assert deltas[0].delta.text == "hallo wereld"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement fakes** (minimaal: start/subscribe/stop/get_status + `emit_seconds` / chunk→delta)

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/testing/fake_capture.py modules/testing/fake_stt.py tests/test_capture_stt_wiring.py
git commit -m "Add fake capture/STT for capability wiring tests."
```

---

### Task 4: `audio-capture` module (mic, Windows) + registry

**Files:**
- Create: `modules/_builtin/audio_capture.py`
- Modify: `modules/registry.py` — voeg `AudioCaptureModule` toe aan `all_builtin_modules()`
- Modify: `locales/nl.json`, `locales/en.json`, `locales/de.json`
- Create: `tests/test_audio_capture_ringbuffer.py`
- Optional: `tests/test_audio_capture_module_register.py`

**Interfaces:**
- Consumes: `ContinuousCaptureCapability` contract
- Produces: registered provider; ringbuffer met gap bij overflow
- Chunk-beleid: ~3000 ms vensters / 500 ms overlap (constants in module; later optioneel yaml onder `audio-capture/`)

**Implementatie-notities:**
- Gebruik `sounddevice.InputStream` (16 kHz mono float32), zelfde als dictee
- Worker-thread leest blocks → ringbuffer → emit `AudioChunkReceived`
- Op non-Windows: module mag registreren maar `start_session` faalt met duidelijke status ERROR (MVP Windows-only)
- `default_enabled()`: `True` (Buddy heeft capture nodig) of `False` tot Buddy aan staat — kies **`True`** zodat capability beschikbaar is wanneer Buddy start; Buddy fail-soft als ontbreekt

- [ ] **Step 1: Write failing ringbuffer test**

```python
# tests/test_audio_capture_ringbuffer.py
from modules._builtin.audio_capture import RingBuffer, CaptureGap


def test_overflow_emits_gap_and_drops_oldest():
    buf = RingBuffer(max_duration_s=0.05, sample_rate=16000)
    gaps = []
    buf.on_gap = gaps.append
    # schrijf meer samples dan max
    import numpy as np
    samples = np.zeros(16000, dtype=np.float32)  # 1s > 0.05s
    buf.write(samples, start_ms=0)
    assert gaps, "expected CaptureGap on overflow"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement RingBuffer + AudioCaptureModule provider**

Kern `on_app_start`:

```python
ctx.capabilities.register(
    capability_id=CAPABILITY_ID,
    provider=self._engine,
    owner_module_id=self.id,
    contract_version=CONTRACT_VERSION,
)
```

`id = "audio-capture"`. Shutdown: `unregister_owner`.

- [ ] **Step 4: Tests PASS + register smoke test**

```python
def test_module_registers_capability():
    from modules.capabilities.registry import CapabilityRegistry
    from modules._builtin.audio_capture import AudioCaptureModule
    from modules._contract import ModuleContext
    from modules.capabilities.continuous_capture import CAPABILITY_ID
    from pathlib import Path

    caps = CapabilityRegistry()
    mod = AudioCaptureModule()
    ctx = ModuleContext(app_dir=Path("."), ui_dispatch=lambda f: f(), capabilities=caps)
    mod.on_app_start(ctx)
    assert caps.get(CAPABILITY_ID) is not None
```

- [ ] **Step 5: Commit**

```bash
git add modules/_builtin/audio_capture.py modules/registry.py locales/*.json tests/test_audio_capture_ringbuffer.py
git commit -m "Add audio-capture module with mic continuous capture capability."
```

---

### Task 5: SharedWhisper busy-aware access + `speech-to-text` module

**Files:**
- Modify: `modules/whisper.py` — voeg `try_locked_model(timeout: float = 0.0)` toe
- Create: `modules/_builtin/speech_to_text.py`
- Modify: `modules/registry.py`
- Modify: `locales/*.json`
- Create: `tests/test_speech_to_text_backpressure.py`
- Create: `tests/test_shared_whisper_try_lock.py`

**Interfaces:**
- Consumes: `SharedWhisper`, `ContinuousCaptureCapability`, contracts
- Produces: `transcription.speech_to_text` provider
- Gedrag:
  - Subscribe op capture events voor `AudioChunkReceived`
  - Probeer Whisper-lock; bij bezet (dictee): queue chunks tot `max_whisper_queue_duration_s`
  - Bij overschrijding: drop oudste, emit `TranscriptGap`, status `DELAYED`
  - Chunk aggregatie: ~3s + 0.5s overlap → `TranscriptDelta` (`is_final=True` voor MVP-vensters; non-final mag later)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_shared_whisper_try_lock.py
import threading
import time
from modules.whisper import SharedWhisper


def test_try_locked_model_returns_false_when_busy():
    w = SharedWhisper()
    w.set_model(object())
    held = threading.Event()
    release = threading.Event()

    def holder():
        with w.locked_model():
            held.set()
            release.wait(2)

    t = threading.Thread(target=holder)
    t.start()
    held.wait(1)
    assert w.try_locked_model(0.0) is None  # of contextmanager die False oplevert
    release.set()
    t.join()
```

```python
# tests/test_speech_to_text_backpressure.py
from modules.testing.fake_capture import FakeContinuousCapture
from modules._builtin.speech_to_text import IncrementalSpeechToText
from modules.capabilities.speech_to_text import TranscriptGap, TranscriptionStatus


class AlwaysBusyWhisper:
    def try_locked_model(self, timeout: float = 0.0):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield None

        return _cm()


def test_gap_when_queue_exceeds_max():
    capture = FakeContinuousCapture()
    events: list = []
    stt = IncrementalSpeechToText(
        whisper=AlwaysBusyWhisper(),
        max_whisper_queue_duration_s=0.01,
        on_event=events.append,
    )
    cs = capture.start_session()
    ts = stt.start_session(capture_session_id=cs.session_id, capture=capture)
    for _ in range(20):
        capture.emit_seconds(0.05)
    assert any(isinstance(e, TranscriptGap) for e in events)
    assert stt.get_status(ts.session_id) == TranscriptionStatus.DELAYED
```

Kies één API en gebruik die overal:

```python
@contextmanager
def try_locked_model(self, timeout: float = 0.0) -> Iterator[Any | None]:
    """Yields model, or None if lock not acquired within timeout."""
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement try_lock + SpeechToTextModule**

`start_session` moet `capture.subscribe(...)` aanroepen en mapping `capture_session_id → transcription_session_id` bewaren.

Voor Whisper-inferentie in tests: injecteer `transcribe_fn` of mock `locked_model` zodat CI geen model nodig heeft.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/whisper.py modules/_builtin/speech_to_text.py modules/registry.py locales/*.json tests/test_shared_whisper_try_lock.py tests/test_speech_to_text_backpressure.py
git commit -m "Add speech-to-text capability with SharedWhisper backpressure."
```

---

### Task 6: Meeting State + immutable StateService + prep

**Files:**
- Create: `modules/_builtin/meeting_buddy/state.py`
- Create: `modules/_builtin/meeting_buddy/state_service.py`
- Create: `modules/_builtin/meeting_buddy/prep.py`
- Create: `tests/test_meeting_buddy_state.py`
- Create: `tests/test_meeting_buddy_prep.py`

**Interfaces:**
- Produces:
  - `MeetingState` (frozen, met `version: int`)
  - `Topic`, `Question`, `ActionItem`, `Hint` entities
  - `StateProposal`
  - `MeetingStateService.apply(state, proposal) -> MeetingState`  # nieuwe versie
  - `parse_agenda(text: str) -> list[str]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_meeting_buddy_prep.py
from modules._builtin.meeting_buddy.prep import parse_agenda


def test_parse_strips_bullets_and_numbers():
    text = "1. Stand van zaken planning\n2. Budget\n- Beveiligingsrisico's\nBesluit over livegang\n\n"
    assert parse_agenda(text) == [
        "Stand van zaken planning",
        "Budget",
        "Beveiligingsrisico's",
        "Besluit over livegang",
    ]
```

```python
# tests/test_meeting_buddy_state.py
from modules._builtin.meeting_buddy.state import MeetingState, Topic, TopicStatus, TopicSource
from modules._builtin.meeting_buddy.state_service import MeetingStateService, StateProposal


def test_apply_increments_version_immutably():
    s0 = MeetingState.empty(meeting_session_id="m1")
    assert s0.version == 0
    p = StateProposal(
        proposal_id="p1",
        meeting_session_id="m1",
        type="add_topics",
        payload={"titles": ["Budget"], "source": "agenda"},
        source_delta_ids=[],
        confidence=1.0,
    )
    s1 = MeetingStateService().apply(s0, p)
    assert s1.version == 1
    assert s0.version == 0  # unchanged
    assert len(s1.topics) == 1
    assert s1.topics[0].title == "Budget"
    assert s1.topics[0].status == TopicStatus.OPEN
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement prep + state + service**

`MeetingState.empty(...)` zet lege tuples/lists als tuples voor freeze. `apply` ondersteunt minimaal proposal types die heuristics later nodig hebben: `add_topics`, `mark_topic_discussed`, `add_question`, `update_question`, `add_action`, `update_action`, `set_hints` (of hints buiten state-service — spec: `emitted_hints` in state; Hint Engine mag via proposal `upsert_hints`).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/_builtin/meeting_buddy/ tests/test_meeting_buddy_state.py tests/test_meeting_buddy_prep.py
git commit -m "Add Meeting Buddy immutable state service and agenda prep."
```

---

### Task 7: Config yaml + heuristics + Hint Engine

**Files:**
- Create: `modules/defaults/meeting-buddy.yaml` (defaults uit spec)
- Create: `modules/_builtin/meeting_buddy/config.py`
- Create: `modules/_builtin/meeting_buddy/heuristics.py`
- Create: `modules/_builtin/meeting_buddy/hints.py`
- Modify: `requirements.txt`, `pyproject.toml` — voeg `PyYAML` toe (pin een recente stabiele versie)
- Create: `tests/test_meeting_buddy_config.py`
- Create: `tests/test_meeting_buddy_heuristics.py`
- Create: `tests/test_meeting_buddy_hints.py`

**Interfaces:**
- `load_meeting_buddy_config(app_dir: Path) -> MeetingBuddyConfig` — merge shipped defaults + `%APPDATA%/.../meeting-buddy/meeting-buddy.yaml`
- `HeuristicsEngine.proposals_for(delta, state, config, now) -> list[StateProposal]`
- `HintEngine.evaluate(state, config, now) -> list[Hint]` — max `max_visible_hints`; types exact: `topic_not_discussed`, `question_open`, `candidate_action_without_owner`; twijfel → weglaten

- [ ] **Step 1: Write failing tests**

```python
# tests/test_meeting_buddy_config.py
def test_defaults_load_without_user_file(tmp_path):
    from modules._builtin.meeting_buddy.config import load_meeting_buddy_config
    cfg = load_meeting_buddy_config(tmp_path)
    assert cfg.max_visible_hints == 3
    assert cfg.topic_match_score == 0.55
```

```python
# tests/test_meeting_buddy_heuristics.py
from modules._builtin.meeting_buddy.state import MeetingState, Topic, TopicStatus, TopicSource
from modules._builtin.meeting_buddy.heuristics import HeuristicsEngine
from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules.capabilities.speech_to_text import TranscriptDelta


def _cfg(**kwargs) -> MeetingBuddyConfig:
    base = MeetingBuddyConfig.defaults()
    return base.model_copy(update=kwargs) if hasattr(base, "model_copy") else base.replace(**kwargs)


def test_question_mark_opens_question():
    state = MeetingState.empty("m1")
    delta = TranscriptDelta("t1", 1, 0, 1000, "Hoe gaan we dit doen?", True, 0.9)
    props = HeuristicsEngine().proposals_for(delta, state, MeetingBuddyConfig.defaults(), now_s=10.0)
    assert any(p.type == "add_question" for p in props)


def test_topic_match_requires_score_and_tokens():
    topic = Topic(id="tp1", title="Beveiligingsrisico's", status=TopicStatus.OPEN, source=TopicSource.AGENDA, confidence=1.0, last_matched_at=None)
    state = MeetingState.empty("m1").with_topics((topic,))
    weak = TranscriptDelta("t1", 1, 0, 1000, "risico", True, 0.9)
    strong = TranscriptDelta("t1", 2, 1000, 2000, "beveiligingsrisico's besproken", True, 0.9)
    eng = HeuristicsEngine()
    cfg = MeetingBuddyConfig.defaults()
    assert not any(p.type == "mark_topic_discussed" for p in eng.proposals_for(weak, state, cfg, now_s=10.0))
    assert any(p.type == "mark_topic_discussed" for p in eng.proposals_for(strong, state, cfg, now_s=10.0))


def test_action_pattern_creates_candidate_without_owner():
    state = MeetingState.empty("m1")
    delta = TranscriptDelta("t1", 1, 0, 1000, "we moeten nog de website controleren", True, 0.9)
    props = HeuristicsEngine().proposals_for(delta, state, MeetingBuddyConfig.defaults(), now_s=10.0)
    action_props = [p for p in props if p.type == "add_action"]
    assert action_props
    assert action_props[0].payload.get("owner") in (None, "UNKNOWN", "unknown")
```

```python
# tests/test_meeting_buddy_hints.py
from modules._builtin.meeting_buddy.hints import HintEngine, HintType
from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.state import (
    MeetingState, Topic, TopicStatus, TopicSource, Question, QuestionStatus, ActionItem, ActionStatus,
)


def test_max_three_hints():
    topics = tuple(
        Topic(id=f"t{i}", title=f"Topic {i}", status=TopicStatus.OPEN, source=TopicSource.AGENDA, confidence=1.0, last_matched_at=None)
        for i in range(5)
    )
    state = MeetingState.empty("m1").with_topics(topics)
    cfg = MeetingBuddyConfig.defaults()
    # forceer min_wait=0 via replace indien beschikbaar
    hints = HintEngine().evaluate(state, cfg, now_s=10_000.0)
    assert len(hints) <= cfg.max_visible_hints


def test_low_confidence_question_no_hint():
    q = Question(id="q1", text="Wat?", status=QuestionStatus.OPEN, source_delta_id="d1", created_at=0.0, resolved_at=None, confidence=0.1)
    state = MeetingState.empty("m1").with_questions((q,))
    hints = HintEngine().evaluate(state, MeetingBuddyConfig.defaults(), now_s=10_000.0)
    assert not any(h.type == HintType.QUESTION_OPEN for h in hints)


def test_cooldown_suppresses_repeat():
    engine = HintEngine()
    cfg = MeetingBuddyConfig.defaults()
    topic = Topic(id="tp1", title="Budget", status=TopicStatus.OPEN, source=TopicSource.AGENDA, confidence=1.0, last_matched_at=None)
    state = MeetingState.empty("m1").with_topics((topic,))
    first = engine.evaluate(state, cfg, now_s=10_000.0)
    assert first
    second = engine.evaluate(state, cfg, now_s=10_001.0)  # binnen cooldown
    assert second == [] or all(h.related_entity_id != "tp1" for h in second)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement yaml load + heuristics + hints**

Shipped defaults-bestand kopiëren/lezen via `Path(__file__).resolve().parents[2] / "defaults" / "meeting-buddy.yaml"` (pad verifiëren t.o.v. package layout). User-file: `module_dir(app_dir, "meeting-buddy") / "meeting-buddy.yaml"`.

NL vraagpatronen en actiepatronen als in de spec (constants OK; drempels uit config).

- [ ] **Step 4: Run — expect PASS** + `ruff check` op nieuwe files

- [ ] **Step 5: Commit**

```bash
git add modules/defaults/meeting-buddy.yaml modules/_builtin/meeting_buddy/ requirements.txt pyproject.toml tests/test_meeting_buddy_config.py tests/test_meeting_buddy_heuristics.py tests/test_meeting_buddy_hints.py
git commit -m "Add Meeting Buddy config, heuristics, and hint engine."
```

---

### Task 8: Orchestrator + observability + module tray actions

**Files:**
- Create: `modules/_builtin/meeting_buddy/orchestrator.py`
- Create: `modules/_builtin/meeting_buddy/observability.py`
- Create: `modules/_builtin/meeting_buddy/module.py`
- Create: `modules/_builtin/meeting_buddy/__init__.py`
- Modify: `modules/registry.py` — `MeetingBuddyModule`, `default_enabled=False`
- Modify: `locales/*.json` — name, description, actions (`start`, `stop`, `prepare_agenda`)
- Create: `tests/test_meeting_buddy_orchestrator.py`
- Create: `tests/test_meeting_buddy_observability.py`

**Interfaces:**
- `MeetingSessionBinding(meeting_session_id, capture_session_id, transcription_session_id)`
- `MeetingOrchestrator.start(agenda_text: str) -> None` — require capture+STT; fail duidelijk als missing
- `stop()`, `on_stt_event()`, `on_capture_status()`
- Flow per delta: heuristics → apply proposals → hint engine → notify UI callback
- `log_event(name: str, **fields)` — geen `text=` transcriptvelden

Tray actions via `ModuleWithActions`:
- `prepare_agenda` → simpele tkinter dialoog (multiline) of minimale input; sla draft op in module state
- `start_meeting` / `stop_meeting`

- [ ] **Step 1: Write failing orchestrator test (fakes)**

```python
# tests/test_meeting_buddy_orchestrator.py
from pathlib import Path
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.continuous_capture import CAPABILITY_ID as CAP_CAPTURE
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID as CAP_STT,
    TranscriptDelta,
    TranscriptDeltaReceived,
)
from modules.testing.fake_capture import FakeContinuousCapture
from modules.testing.fake_stt import FakeSpeechToText
from modules._builtin.meeting_buddy.orchestrator import MeetingOrchestrator
from modules._builtin.meeting_buddy.observability import RecordingObserver


def test_start_wires_capture_and_stt_and_updates_state():
    caps = CapabilityRegistry()
    capture = FakeContinuousCapture()
    stt = FakeSpeechToText(text_for_chunk=lambda c: "Budget is rond")
    caps.register(CAP_CAPTURE, capture, "audio-capture", 1)
    caps.register(CAP_STT, stt, "speech-to-text", 1)
    obs = RecordingObserver()
    orch = MeetingOrchestrator(capabilities=caps, app_dir=Path("."), observer=obs)
    orch.set_agenda("Budget\nPlanning")
    orch.start()
    assert obs.names[0] == "meeting_started"
    assert orch.state.version >= 1
    assert len(orch.state.topics) == 2
    # STT event simuleren
    delta = TranscriptDelta(orch.binding.transcription_session_id, 1, 0, 1000, "Budget is rond", True, 0.9)
    orch.on_stt_event(TranscriptDeltaReceived(delta=delta))
    assert orch.state.version >= 2
    orch.stop()
    assert "meeting_stopped" in obs.names


def test_start_fails_without_capture():
    caps = CapabilityRegistry()
    orch = MeetingOrchestrator(capabilities=caps, app_dir=Path("."), observer=RecordingObserver())
    try:
        orch.start()
        raise AssertionError("expected failure")
    except Exception as exc:
        assert "capture" in str(exc).lower() or "audio" in str(exc).lower()
```

```python
# tests/test_meeting_buddy_observability.py
from modules._builtin.meeting_buddy.observability import log_event, RecordingObserver


def test_log_event_has_no_transcript_field():
    obs = RecordingObserver()
    log_event(obs, "hint_emitted", meeting_session_id="m1", hint_type="question_open", text="GEHEIM")
    payload = obs.events[0]
    assert "text" not in payload or payload.get("text") is None
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement orchestrator + module + observability**

Speaker: sla over / UNKNOWN. Geen AI-capability lookup vereist.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/_builtin/meeting_buddy/ modules/registry.py locales/*.json tests/test_meeting_buddy_orchestrator.py tests/test_meeting_buddy_observability.py
git commit -m "Wire Meeting Buddy orchestrator, tray actions, and debug events."
```

---

### Task 9: Compact overlay UI

**Files:**
- Create: `modules/_builtin/meeting_buddy/overlay.py`
- Create: `tests/test_meeting_buddy_overlay.py` (pure helpers: format timer, select emphasis hint — geen GUI must in CI)
- Modify: `module.py` / `orchestrator.py` — `ui_dispatch` toont/update overlay
- Modify: `locales/*.json` — overlay strings (status delayed, dismiss, confirm, minimize)

**Interfaces:**
- Overlay toont: timer, tot 3 hints (één emphasized), capture/STT/session status
- Controls: dismiss, confirm (voor candidate actions), minimize
- **Geen** transcriptwidget, geen state-lijsten

- [ ] **Step 1: Write failing pure tests**

```python
def test_format_elapsed():
    from modules._builtin.meeting_buddy.overlay import format_elapsed
    assert format_elapsed(1458) == "00:24:18"


def test_pick_emphasis_is_highest_priority():
    from modules._builtin.meeting_buddy.overlay import pick_emphasis
    # hints with priorities → exactly one emphasized id
    ...
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement overlay + wire dismiss/confirm → orchestrator proposals**

Gebruik bestaand patroon: `ctx.ui_dispatch(lambda: ...)` voor tkinter. Op macOS: Modules-dialog heeft geen action buttons — tray actions blijven leidend (documenteer in module docstring).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/_builtin/meeting_buddy/overlay.py modules/_builtin/meeting_buddy/*.py locales/*.json tests/test_meeting_buddy_overlay.py
git commit -m "Add Meeting Buddy compact overlay without transcript view."
```

---

### Task 10: Packaging, docs touchpoints, handmatige acceptatiechecklist

**Files:**
- Modify: `pyproject.toml` / `praatMaar.spec` indien nodig — include `modules/defaults/meeting-buddy.yaml`, package `modules._builtin.meeting_buddy`
- Modify: `docs/STATUS.md` — Meeting Buddy MVP experimenteel / behind module toggle
- Modify: `CHANGELOG.md` — Unreleased note
- Modify: `docs/modules-authoring.md` — korte verwijzing naar capture/STT/Buddy capabilities (alleen indien nodig voor consistency)
- Create: geen nieuwe RFC; design spec status mag → “In implementatie”

- [ ] **Step 1: Verify package discovers modules**

Run: `pytest tests/test_continuous_capture_contract.py tests/test_speech_to_text_contract.py tests/test_capture_stt_wiring.py tests/test_audio_capture_ringbuffer.py tests/test_shared_whisper_try_lock.py tests/test_speech_to_text_backpressure.py tests/test_meeting_buddy_*.py -q`  
Expected: all PASS

- [ ] **Step 2: Ruff**

Run: `ruff check modules/capabilities modules/_builtin/audio_capture.py modules/_builtin/speech_to_text.py modules/_builtin/meeting_buddy modules/testing tests/test_*capture* tests/test_*speech* tests/test_meeting_buddy* && ruff format ...`  
Expected: clean

- [ ] **Step 3: Update STATUS/CHANGELOG**

Kort: modules `audio-capture`, `speech-to-text`, `meeting-buddy` (default uit); MVP mic-only; zie design spec.

- [ ] **Step 4: Manual acceptatie (Windows)**

Checklist uit spec:

- [ ] Meeting starten/stoppen via tray Modules
- [ ] Mic capture actief
- [ ] Incrementele transcriptie (hints bewegen mee)
- [ ] State vN stijgt (debug log `state_version` of test)
- [ ] Hints max 3; geen transcript in overlay
- [ ] Dictee tegelijk: blijft werken; bij conflict “vertraagd” + geen crash
- [ ] Capture unplug/fout: Buddy open, fout zichtbaar
- [ ] Drempel wijzigen in `meeting-buddy.yaml` zonder herbouw
- [ ] Debug events in log

- [ ] **Step 5: Commit**

```bash
git add docs/STATUS.md CHANGELOG.md pyproject.toml praatMaar.spec docs/superpowers/specs/2026-07-19-meeting-buddy-mvp-design.md
git commit -m "Document Meeting Buddy MVP modules in STATUS and packaging."
```

---

## Spec coverage (self-review)

| Spec-eis | Task |
|----------|------|
| `audio.continuous_capture` + events | 1, 4 |
| Mic-only Windows, ringbuffer/gaps | 4 |
| `transcription.speech_to_text` + deltas | 2, 5 |
| SharedWhisper priority / backpressure / gap | 5 |
| Meeting Buddy orchestreert, geen PCM | 8 |
| Immutable MeetingState vN | 6 |
| Prep agenda parse | 6 |
| Heuristieken topic/question/action | 7 |
| Hint Engine 3 types, max 3, twijfel | 7 |
| `meeting-buddy.yaml` | 7 |
| Overlay zonder transcript | 9 |
| Observability events | 8 |
| AI contract only | 2 |
| Speaker UNKNOWN default | 8 |
| Acceptatiecriteria | 10 |
| Geen nieuwe CycleEvents | overal |

**Bewust later (buiten plan):** loopback, AI-provider, review/export, macOS capture.

**Type consistency:** `subscribe`/`unsubscribe` op capture én STT; `TranscriptDelta.session_id` = transcription session; binding in orchestrator.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-meeting-buddy-mvp.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — this session with executing-plans, batch checkpoints  

Which approach?
