# praatMaar — Hilfe

## Was sind Ziele?

Ein **Ziel** ist ein Name, der mit einem Ordner auf Ihrem Computer verknüpft ist. Beim
Diktieren wird das Transkript im Ordner des aktiven Ziels gespeichert.

**Sticky:** das aktive Ziel bleibt gesetzt, bis Sie wechseln oder auf Standard
zurücksetzen. Sie müssen den Namen nicht jedes Mal erneut sagen.

**Automatisches Einfügen:** pro Ziel können Sie Zwischenablage + Einfügen erlauben.
Standard ist **aus** (nur im Ordner speichern). Ohne aktives Ziel gilt die globale
Einstellung.

**Pill:** die kleine Bildschirm-Anzeige zeigt den Namen des aktiven Ziels (sichtbar
auch ohne laufende Aufnahme). Kein Label bedeutet: Standardordner.

## Wechseln per Sprache

Nehmen Sie eine kurze Aufnahme auf, in der Sie **nur** den exakten Zielnamen sagen —
keine zusätzlichen Wörter davor oder danach. praatMaar vergleicht die gesamte Aufnahme
mit Ihren gespeicherten Namen (exakte Übereinstimmung nach Normalisierung).

- **Treffer:** das Ziel wird aktiv, die Pill wird aktualisiert. Es wird nichts
  eingefügt und der Name selbst wird nicht als Transkript gespeichert.
- **Kein Treffer:** normaler Diktierablauf — Text einfügen und im aktuellen Ordner
  speichern.

**Zurück auf Standard:** sagen Sie nur **Standard**, **default** oder **standaard**
(eine Aufnahme, exakt). Das aktive Ziel wird gelöscht. Alle drei Wörter funktionieren,
unabhängig von Sprach- oder Oberflächensprache.

## Wo landen Ihre Dateien?

| Situation | Ordner |
|-----------|--------|
| Kein aktives Ziel (Standard) | `%APPDATA%\praatMaar\transcripts\` |
| Aktives Ziel | Der Ordner, den Sie mit diesem Namen verknüpft haben |

Im Standardordner behält praatMaar automatisch nur die neuesten Transkripte (Retention).
Zielordner werden nicht bereinigt.

Recovery-Audiodateien (bei fehlgeschlagenen Aufnahmen) bleiben immer in
`%APPDATA%\praatMaar\recovery\`, unabhängig vom aktiven Ziel. Unter
**Einstellungen** → **Wiederherstellungs-Audio** können Sie diese Dateien
auflisten, löschen oder erneut transkribieren lassen.

## Verwaltung über das Infobereich-Symbol

Rechtsklick auf das praatMaar-Symbol im Infobereich:

- **Einstellungen** — Mikrofon, Hotkey, Sprachen, Wiederherstellungs-Audio
- **Ziele** — Dialog zum Hinzufügen, Ändern oder Entfernen von Namen und Ordnern sowie
  zum Setzen oder Löschen des aktiven Ziels. In diesem Dialog finden Sie auch
  Schaltflächen zum Öffnen des Transkriptordners oder des aktiven Ordners.
- **Module** — Erweiterungen ein-/ausschalten und inkrementelle Transkription
- **Hilfe** — diese Benutzeranleitung
- **Beenden**

## Module und externe Tools

Unter **Module** im Infobereich schalten Sie Erweiterungen ein oder aus und
aktivieren optional **inkrementelle Transkription**. Whisper läuft dann bereits
während der Aufnahme im Hintergrund (Zwischentext für Module/Tools). Beim Stoppen
wird der letzte Zwischentext zum Endtranskript — schneller, aber die letzten
Sekunden nach diesem Zwischenlauf können fehlen.

**Event-Journal:** jeder Diktierzyklus wird als JSON-Zeilen nach
`%APPDATA%\praatMaar\events\events.jsonl` geschrieben (macOS: Application Support).
Externe Programme können diese Datei beobachten, ohne praatMaar anzupassen. Jedes
Event hat `session_id`, `type` (z. B. `transcript.saved`) und Metadaten.

**Inbox-Spiegel** (standardmäßig an): kopiert jedes gespeicherte Transkript nach
`%APPDATA%\praatMaar\inbox\` — fester Ablageort für Skripte.

Wiederherstellungs-Transkription (Einstellungen → Wiederherstellungs-Audio)
sendet dieselben Event-Typen mit `source: "recovery"`.

## Risiken und Tipps

**Whisper versteht den Namen falsch**
Stimmt das Transkript nicht exakt mit einem Zielnamen überein, passiert nichts
Zusätzliches: Sie bleiben beim aktuellen Ziel und der Text wird normal verarbeitet.
Sicher, aber Sie wechseln nicht.

**Kurze oder generische Namen**
Namen wie „Notizen“ oder „Arbeit“ kommen leichter versehentlich in normaler Diktat
vor. Wählen Sie kurze, aber eindeutige Namen, z. B. „einkaufsliste“ oder
„projekt-alpha“.

**Unverschlüsselte Dateien**
Transkripte werden als Klartextdateien auf der Festplatte gespeichert, ohne
Verschlüsselung. Verwenden Sie keine Ziele in freigegebenen oder unsicheren Ordnern,
wenn Sie vertrauliche Inhalte diktieren.

## Meeting Buddy und Microsoft Teams (Windows)

Aktivieren Sie **Meeting Buddy** über Tray → **Module**. Nach **Speichern** bleibt
das Fenster offen und zeigt Schaltflächen für Start, Schnellstart, Stopp, Agenda
und Eigenschaften. Im Tray gibt es außerdem **Meeting Buddy ▸** mit denselben
Aktionen.

- **Besprechung starten…** öffnet die Agenda (Bibliothek mit Zuletzt + alle `.md`-Agenden).
- **Besprechung starten (schnell)** startet mit der aktuellen Agenda ohne Dialog.
- **Agenda bearbeiten** zum Speichern/Laden ohne Start.
- **Eigenschaften** für Meeting-Audio (Windows-Loopback), Ausgabegerät und
  optional einen anderen Transkriptordner.

Während eines Meetings wächst das Transkript als `.md` unter
`%APPDATA%\praatMaar\meeting-buddy\transcripts\` (nur finale Texte; änderbar
unter Eigenschaften). Beim Stoppen erscheint eine Meldung mit dem Pfad.

### Local LLM, Live-Zusammenfassung und Agenda-Review

Optional (standardmäßig aus): aktivieren Sie **Local LLM** unter **Module**.
Das Modul nutzt [Ollama](https://ollama.com/) mit einem lokalen Qwen-Modell.
Über Modulaktionen prüfen Sie den Status, öffnen Installationshilfe und laden
das Modell herunter. Ohne bereites Local LLM bleibt Meeting Buddy bei
heuristischen Hinweisen.

Mit bereitem Local LLM schalten Sie Live-Zusammenfassung und Agenda-Review unter
Meeting-Buddy-**Eigenschaften** ein (standardmäßig aus):

- **Live-Zusammenfassung** im Overlay (Schwellen für Zeit/neuen Text).
- **Agenda-Review**: Statusleiter pro Agendapunkt und „Fragen von anderen“
  (experimentell; hängt von Sprechererkennung ab).

Unter Windows kann Meeting Buddy neben dem Mikrofon optional **Meeting-Audio** vom
gewählten Windows-Ausgabegerät per Loopback aufnehmen.

Für Teams-Anrufe:

1. Stellen Sie die Windows-**Soundausgabe** auf das Gerät, über das Teams abspielt (oft Ihr Headset).
2. Stellen Sie den Teams-**Lautsprecher** auf dasselbe Gerät.
3. Verwenden Sie ein **Headset**, um Echo zu reduzieren (Ihr Mikrofon soll die Lautsprecher nicht mitaufnehmen).

Das Meeting-Buddy-Overlay zeigt, ob Meeting-Audio aktiv ist. Ist Loopback nicht
verfügbar, wird nur das Mikrofon aufgenommen und das Overlay warnt Sie.
