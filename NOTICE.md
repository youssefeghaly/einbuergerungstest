# Herkunft und Lizenz der Inhalte

## Fragen und Bilder

**Quelle:** Bundesamt für Migration und Flüchtlinge (BAMF),
*Gesamtfragenkatalog zum Test „Leben in Deutschland“ und zum „Einbürgerungstest“*,
Stand **07.05.2025**.

Vollständige Fundstelle:
https://www.bamf.de/SharedDocs/Anlagen/DE/Integration/Einbuergerung/gesamtfragenkatalog-lebenindeutschland.pdf

Die Datei liegt unverändert unter `data/raw/gesamtfragenkatalog-2025-05-07.pdf`.
`tools/extract_catalog.py` liest daraus die 460 Fragen (300 allgemeine Fragen und
10 Fragen je Bundesland) sowie die zugehörigen Bildleisten aus. Der amtliche Text
wird dabei nicht inhaltlich verändert, nur Layout und Seitenumbrüche werden
aufgelöst; die Bilder werden als Bildausschnitte aus demselben PDF erzeugt.

**Wichtig:** Der amtliche Katalog enthält **keinen Lösungsschlüssel**. Die
richtigen Antworten stammen daher aus einer zweiten Quelle (siehe unten).

## Antwortschlüssel

**Quelle:** Projekt `leben-in-deutschland/leben-in-deutschland-app`
(https://github.com/leben-in-deutschland/leben-in-deutschland-app),
Datei `src/web/data/questions-core.json`.

**Lizenz:** MIT License, Copyright (c) 2026 lebenindeutschland.
Der vollständige Lizenztext liegt unter
`data/source/LICENSE-leben-in-deutschland.txt`.

Übernommen wurde ausschließlich die Angabe der richtigen Antwort je Frage
(Feld `solution`). Fragetexte, Antwortoptionen und Bilder stammen aus dem
amtlichen PDF. Die Übernahme ist in `data/verification-report.md` dokumentiert;
`tools/build_dataset.py` rechnet die Antwortposition um, weil der fremde
Datensatz die Antwortoptionen anders anordnet als das amtliche PDF.

## Keine amtliche Verbindung

Dieses Projekt ist eine private Übungshilfe. Es steht in keiner Verbindung zum
BAMF und ersetzt weder den amtlichen Test noch eine Beratung. Maßgeblich sind
allein die aktuellen Veröffentlichungen des BAMF.
