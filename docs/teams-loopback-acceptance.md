# Teams-loopback acceptatie (handmatig)

Checklist voor Windows + echte Microsoft Teams-call. Niet geautomatiseerd in CI.

Voorbereiding:

1. Meeting Buddy aan via tray → **Modules**
2. Windows-uitvoer = het apparaat waar Teams doorheen speelt
3. Teams-luidspreker op hetzelfde apparaat
4. Headset aanbevolen (minder echo)

| # | Scenario | Verwacht | OK |
|---|----------|----------|----|
| 1 | Headset = default output + input, meeting start | Hints over wat **anderen** zeggen | [ ] |
| 2 | Loopback uit in prep-dialoog | Overlay: “alleen microfoon”; alleen eigen uitingen | [ ] |
| 3 | Loopback faalt (bijv. geen WASAPI-build) | Waarschuwing overlay; app crasht niet | [ ] |
| 4 | Headset af tijdens meeting | Reconnect-tekst of waarschuwing; “Herverbinden” herstelt | [ ] |
| 5 | Teams output ≠ Windows default | Kies uitvoer in prep-dialoog; meetinggeluid werkt | [ ] |
| 6 | Parallel dicteren tijdens meeting | Dicteer wint; STT delayed; geen crash | [ ] |

Optioneel — mix tunen via `%APPDATA%\praatMaar\meeting-buddy\meeting-buddy.yaml`:

```yaml
mic_mix_gain: 0.4
loopback_mix_gain: 0.6
```

Datum / machine / opmerkingen:
