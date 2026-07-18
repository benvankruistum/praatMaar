# praatMaar — Hilfe

## Was sind Ziele?

Ein **Ziel** ist ein Name, der mit einem Ordner auf Ihrem Computer verknüpft ist. Beim
Diktieren wird das Transkript im Ordner des aktiven Ziels gespeichert.

**Sticky:** das aktive Ziel bleibt gesetzt, bis Sie wechseln oder auf Standard
zurücksetzen. Sie müssen den Namen nicht jedes Mal erneut sagen.

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

**Zurück auf Standard:** sagen Sie nur das Wort **standaard** (eine Aufnahme, exakt).
Das aktive Ziel wird gelöscht. (Das Reset-Wort ist immer *standaard*, auch wenn die
Oberfläche auf Englisch oder Deutsch steht.)

## Wo landen Ihre Dateien?

| Situation | Ordner |
|-----------|--------|
| Kein aktives Ziel (Standard) | `%APPDATA%\praatMaar\transcripts\` |
| Aktives Ziel | Der Ordner, den Sie mit diesem Namen verknüpft haben |

Im Standardordner behält praatMaar automatisch nur die neuesten Transkripte (Retention).
Zielordner werden nicht bereinigt.

Recovery-Audiodateien (bei fehlgeschlagenen Aufnahmen) bleiben immer in
`%APPDATA%\praatMaar\recovery\`, unabhängig vom aktiven Ziel.

## Verwaltung über das Infobereich-Symbol

Rechtsklick auf das praatMaar-Symbol im Infobereich:

- **Einstellungen** — Mikrofon, Hotkey, Sprachen
- **Ziele** — Dialog zum Hinzufügen, Ändern oder Entfernen von Namen und Ordnern sowie
  zum Setzen oder Löschen des aktiven Ziels. In diesem Dialog finden Sie auch
  Schaltflächen zum Öffnen des Transkriptordners oder des aktiven Ordners.
- **Hilfe** — diese Benutzeranleitung
- **Beenden**

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
