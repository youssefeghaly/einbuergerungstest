# Einbürgerungstest – Übung

Eine einzelne, Offline-fähige Webseite zum Üben für den Einbürgerungstest.

**Öffnen:** `index.html` doppelklicken. Kein Webserver, kein Build, keine Installation.

**Online:** https://einbuergerungstest-mu.vercel.app (Vercel, wird bei jedem Push auf `main` neu gebaut)
· https://youssefeghaly.github.io/einbuergerungstest/ (GitHub Pages)

## Was die Seite macht

- **33 Fragen pro Durchlauf**: 30 allgemeine Fragen aus dem amtlichen Katalog von
  300 und 3 Fragen zum gewählten Bundesland aus dessen 10 Landesfragen.
- **Sofortige Rückmeldung** nach jeder Antwort: richtig/falsch markiert, die
  richtige Antwort wird genannt.
- **Keine Uhr und kein Bestehen/Durchfallen** – du gehst in deinem Tempo vor,
  kannst Fragen überspringen und am Ende alles in der Auswertung durchsehen.
- **Auswertung** am Ende: Punktzahl, Vergleich mit der im echten Test nötigen
  Zahl von 17 richtigen Antworten und eine Liste aller 33 Fragen mit der jeweils
  richtigen Antwort.
- **Der Test passt sich an:** Fragen, die du falsch beantwortest, kommen in den
  folgenden Durchläufen häufiger. Sicher beherrschte Fragen werden seltener,
  noch nie gesehene bevorzugt. Fragen, die du schon einmal falsch hattest,
  werden vor der Antwort als Wiederholung gekennzeichnet.
- **Bundesland** wird auf dem Startbildschirm gewählt (Voreinstellung Hessen).
- Tastatur: `1`–`4` beantworten, `Enter`/`→` weiter, `←` zurück.

## Wie die Anpassung funktioniert

Zu jeder der 460 Fragen merkt sich die Seite im `localStorage` des Browsers
(Schlüssel `eit.progress.v1`) drei Werte: wie oft die Frage gesehen wurde, wie
oft sie falsch beantwortet wurde und wie viele richtige Antworten in Folge
kamen.

Daraus ergibt sich ein Gewicht:

| Zustand der Frage | Gewicht |
| --- | --- |
| noch nie gesehen | 3,0 |
| einmal falsch | 3,0 |
| zweimal falsch | 5,0 |
| dreimal falsch | 7,0 |
| ab vier Fehlern | 8,0 (Obergrenze) |
| richtig beantwortet | sinkt, z. B. 0,2 nach vier richtigen in Folge |

Eine richtige Antwort senkt die Dringlichkeit wieder, sodass eine inzwischen
sitzende Frage nicht dauerhaft den Test dominiert. Die 33 Fragen werden
gewichtet **ohne Zurücklegen** gezogen, es gibt also nie Doppelte in einem
Durchlauf. Gemessen an 400 Durchläufen erscheint eine viermal falsch
beantwortete Frage rund 97-mal, eine sicher beherrschte rund 3-mal.

Der Lernstand lässt sich auf dem Startbildschirm zurücksetzen. Er ist nur lokal
im Browser gespeichert und wird nirgendwohin übertragen. Verbietet der Browser
das Speichern (etwa bei manchen `file://`-Aufrufen), läuft die Seite ohne
Gedächtnis weiter und weist darauf hin.

## Projektstruktur

```
index.html                     die Seite (HTML, CSS und JavaScript in einer Datei)
data/questions.json            Datensatz (kanonisch, für Werkzeuge)
data/questions.js              derselbe Datensatz als Script, damit file:// funktioniert
data/images/                   Bildleisten der 43 Bildfragen (JPEG aus dem amtlichen PDF)
data/raw/                      amtliches BAMF-PDF, unverändert
data/source/                   Antwortschlüssel-Quelle samt MIT-Lizenztext
data/verification-report.md    Prüfbericht zur Datenherkunft
tools/extract_catalog.py       liest Fragen und Bilder aus dem PDF
tools/build_dataset.py         führt Fragen und Antwortschlüssel zusammen, prüft sie
tools/test_app.js              spielt die Seite automatisiert durch (benötigt jsdom)
NOTICE.md                      Herkunft und Lizenz der Inhalte
```

Warum zwei Datendateien? Browser erlauben `fetch()` nicht bei `file://`-URLs.
Damit die Seite per Doppelklick funktioniert, wird `data/questions.js` als
Kopie von `data/questions.json` erzeugt. Beide entstehen im selben Lauf von
`tools/build_dataset.py` und können nicht auseinanderlaufen.

## Daten neu erzeugen

Nötig nur, wenn das BAMF einen neuen Katalogstand veröffentlicht.

```bash
pip install pymupdf
python3 tools/extract_catalog.py    # PDF -> data/catalog_pdf.json + data/images/
python3 tools/build_dataset.py      # + Antwortschlüssel -> data/questions.json
```

Beide Skripte prüfen ihre Ergebnisse selbst (460 Fragen, 300 allgemein,
10 je Bundesland, je 4 Antwortoptionen) und brechen mit Fehlermeldung ab,
wenn etwas nicht passt.

## Test der Seite

```bash
npm install jsdom
node tools/test_app.js
```

Der Test spielt einen kompletten Durchlauf im DOM durch, zählt die Punktzahl
unabhängig mit und prüft unter anderem, dass genau 3 Landesfragen gezogen
werden, keine Frage doppelt vorkommt und die Rückmeldung zur Antwort passt.

## Bereitstellung

Das Vercel-Projekt `sandpitsolutions/einbuergerungstest` ist mit diesem
GitHub-Repository verbunden. **Jeder Push auf `main` löst automatisch eine neue
Bereitstellung aus** (Dauer bis zur Veröffentlichung: ein bis drei Minuten).
Ein `vercel deploy --prod` von Hand ist nicht nötig.

Ausgeliefert wird nur, was die Seite im Browser braucht; `data/raw` (das amtliche
PDF), `data/source` und `tools/` bleiben über `.vercelignore` aussen vor.

## Grenzen

Der amtliche Katalog enthält **keinen Lösungsschlüssel**. Die richtigen Antworten
stammen aus einem externen, MIT-lizenzierten Datensatz. Geprüft ist, dass jede
Frage eindeutig zugeordnet ist und die Antwort auf die richtige der vier
Optionen zeigt (siehe `data/verification-report.md`). Die inhaltliche
Richtigkeit des fremden Schlüssels ist damit nicht amtlich bestätigt.

Details zur Herkunft: `NOTICE.md`.
