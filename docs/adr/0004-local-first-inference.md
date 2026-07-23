# 0004 — Local-first inference (geen cloud-AI als default)

- **Status:** Aanvaard
- **Datum:** 2026-07-23
- **Context-term:** local-first inference — zie [CONTEXT.md](../../CONTEXT.md)
- **Feature-spec:**
  [2026-07-23-local-llm-module-design.md](../superpowers/specs/2026-07-23-local-llm-module-design.md)

## Context

praatMaar transcribeert al **lokaal** met Faster-Whisper (geen cloud-STT). Meeting
Buddy en toekomstige modules hebben behoefte aan **semantische analyse**
(samenvattingen per agendapunt, kwaliteitsbeoordeling van de behandeling). Dat
vraagt een LLM.

Cloud-API’s (OpenAI, Anthropic, enz.) zouden transcripten en agenda’s
verlaten; dat botst met het productprincipe dat gebruikers veilig en
betrouwbaar met gevoelige vergadercontent moeten kunnen werken. Tegelijk willen
we niet dat elke module een eigen model-download en runtime uitvindt — hetzelfde
patroon als SharedWhisper / capability registry.

## Beslissing

**Local-first inference** is de norm voor praatMaar en alle modules:

1. **STT, LLM en overige AI-inferentie** draaien op de machine van de gebruiker
   (of op een endpoint die de gebruiker zelf beheert op het lokale netwerk).
   Geen cloud-inference als default of als stille fallback.
2. **LLM als eigen praatMaar-module** (zelfde rang als Meeting Buddy, audio-
   capture, speech-to-text): standaard **uit**, inschakelbaar via tray
   **Modules**. Die module is de **provider** van capability
   `ai.semantic_analysis`; andere modules (o.a. Meeting Buddy) **consumeren**
   via `ModuleContext.capabilities` en importeren geen Ollama-client.
3. **Eerste runtime (v1-backend van die module):** [Ollama](https://ollama.com/)
   (HTTP op localhost). Eerste aanbevolen model: **Qwen2.5 Instruct**
   (`qwen2.5:7b`; lichtere `qwen2.5:3b` toegestaan).
4. **Setup/installatie** (detectie, Ollama-installatiebegeleiding, model pull,
   status) hoort bij de **local-llm-module**, niet bij Meeting Buddy.
5. **Latere uitbreiding (niet in v1-UI):** eigen model of bestaande
   Ollama-/OpenAI-compatible endpoint (URL + modelnaam) in dezelfde module.
   Cloud-providers vereisen een aparte, bewuste beslissing buiten deze ADR.

### Bewust buiten deze ADR

- Prompts, JSON-schema’s en Meeting Buddy-review-UX — feature-spec.
- Of analyse live of bij stop draait — productkeuze in de feature-spec.
- Bundelen van Ollama/Qwen in de Windows-installer — later.
- Exacte uitbreiding van het `SemanticAnalysisCapability`-Protocol voorbij de
  huidige MVP-stub — feature-spec + contracttests.

## Alternatieven overwogen

- **Cloud-API als default.** Verworpen: privacy- en vertrouwensrisico.
- **Ollama/Qwen alleen ín Meeting Buddy.** Verworpen: andere modules zouden
  dezelfde runtime opnieuw bouwen; botst met capability-registry-patroon.
- **LLM in-process in de praatMaar-venv.** Uitgesteld: zwaardere footprint;
  Ollama houdt modelbeheer buiten het app-proces.
- **Alleen out-of-process file-watchers zonder module.** Verworpen: geen
  first-class aan/uit in Modules, geen gedeelde capability.

## Gevolgen

- Nieuwe “AI”-features registreren of consumeren via capabilities; geen
  stille cloud-SDK’s.
- Gebruiker zet **Local LLM** (werknaam) aan in Modules; Meeting Buddy toont
  of de capability beschikbaar is en of agenda-review aan mag.
- Modelgewichten leven in de Ollama-datamap, niet onder `praatMaar\`.
- CI mockt de capability/HTTP-client; geen verplichte Ollama in CI.
