# Security Policy

## Ondersteunde versies

Dit project heeft nog geen formele release-branches. Meld kwetsbaarheden tegen
de huidige `main`-branch.

## Privacy & vertrouwensoppervlak

praatMaar is een **lokale** dicteertool op Windows. Relevant voor security reviews:

| Oppervlak | Gedrag |
|-----------|--------|
| Netwerk | **Hugging Face** — Whisper-modeldownload (eerste start / modelwissel). **Optioneel Local LLM** (`local-llm` module, standaard uit): HTTP naar Ollama, default `http://127.0.0.1:11434`; custom URL is expliciete gebruikerskeuze (kan off-box). Geen cloud-STT als default. |
| Microfoon | Opname via `sounddevice` tijdens de dicteercyclus; Meeting Buddy (experimenteel) kan continue capture ± WASAPI-loopback gebruiken. |
| Toetsenbord | Globale hotkey-listener (`pynput`) — ziet toetsaanslagen om de sneltoets te herkennen. |
| Klembord | Zet getranscribeerde tekst op het klembord en simuleert plakken via `host.paste`. |
| Schijf | `%APPDATA%\praatMaar\` (of macOS Application Support) — config, transcripts, recovery-audio, event-journal (`events.jsonl` **zonder** volle transcripttekst; wel `transcript_chars`), inbox-kopieën, logbestand. Console/log print standaard **geen** volle transcripttekst. |
| Autostart | Optioneel via OS (`host.set_autostart`: Windows Run-registry / macOS LaunchAgent / Linux `.desktop`). |
| Installer | Windows Setup/portable zijn **niet** Authenticode-gesigneerd (bewuste indie/OSS-keuze); SmartScreen kan waarschuwen. |

Transcripts, recovery-WAV’s, inbox-kopieën en meetingjournals zijn **niet
versleuteld**. Behandel de AppData-map als gevoelige gebruikersdata.

## Een kwetsbaarheid melden

Open **geen** publieke GitHub-issue voor securityproblemen die uitbuitbaar zijn.

1. Mail de maintainer via het e-mailadres op het GitHub-profiel van
   [benvankruistum](https://github.com/benvankruistum), of
2. Gebruik [GitHub Security Advisories](https://github.com/benvankruistum/praatMaar/security/advisories/new)
   als die voor de repo zijn ingeschakeld.

Vermeld graag: impact, stappen om te reproduceren, geraakte versie/commit, en
of er al een PoC is (geen publieke exploit-details nodig).

We streven ernaar binnen **7 dagen** te bevestigen dat de melding is ontvangen.
