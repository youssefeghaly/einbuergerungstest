# Einbürgerungstest – Übung

Eine einzelne, Offline-fähige Webseite zum Üben für den Einbürgerungstest –
und eine Android-App, die dieselbe Seite ganz ohne Netz zeigt.

**Android-App:** `einbuergerungstest.apk` (4 MB) auf das Handy kopieren und
antippen. Die Installation aus unbekannten Quellen muss dafür erlaubt sein.
Die App braucht **keine einzige Berechtigung**, auch nicht Internet.
Direkt auf dem Handy herunterladen:
https://youssefeghaly.github.io/einbuergerungstest/einbuergerungstest.apk

**Im Browser:** `index.html` doppelklicken. Kein Webserver, kein Build, keine Installation.

**Online:** https://youssefeghaly.github.io/einbuergerungstest/ (GitHub Pages, wird bei jedem Push auf `main` neu gebaut)

## Was die Seite macht

- **33 Fragen pro Durchlauf**: 30 allgemeine Fragen aus dem amtlichen Katalog von
  300 und 3 Fragen zum gewählten Bundesland aus dessen 10 Landesfragen.
- **Kein Fragetext zweimal pro Durchlauf**: Im amtlichen Katalog haben sieben
  Fragen denselben Wortlaut, aber andere Antwortmöglichkeiten – „Welches Land ist
  ein Nachbarland von Deutschland?“ kommt allein fünfmal vor. Der Test stellt
  jede Formulierung trotzdem nur einmal.
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
npm install
npm test
```

Der Test spielt einen kompletten Durchlauf im DOM durch, zählt die Punktzahl
unabhängig mit und prüft unter anderem, dass genau 3 Landesfragen gezogen
werden, keine Frage doppelt vorkommt, die Rückmeldung zur Antwort passt, die
adaptive Gewichtung wirkt und in 2000 Durchläufen kein Fragetext zweimal im
selben Test landet. `jsdom` wird nur für diesen Test gebraucht und ist die
einzige Abhängigkeit.

## Android-App bauen

```bash
cd android
./build.sh            # Debug-APK, sofort installierbar
./build.sh release    # unsigniertes Release-APK
```

Das Ergebnis landet als `einbuergerungstest.apk` im Projektverzeichnis.

`build.sh` benutzt das Android-SDK und die Gradle-Distribution, die unter
`../Financial Overview/.toolchain` bereits auf dem Rechner liegen – **es wird
nichts heruntergeladen**. Der Gradle-Abhängigkeitscache (~107 MB) wird beim
ersten Build einmalig nach `android/.gradle-home/` kopiert, damit Gradle seine
Artefakt-Transformationen schreiben kann; `GRADLE_RO_DEP_CACHE` funktioniert
dafür nicht.

Die Web-App wird bei jedem Build frisch nach `android/app/src/main/assets/`
kopiert, damit die APK nicht veralten kann.

### Wie die App aufgebaut ist

Eine Activity mit einem `WebView` in `android/app/src/main/java/com/einbuergerungstest/app/MainActivity.java`.
Keine einzige Abhängigkeit – nur `android.webkit.*` und `android.app.Activity`,
deshalb ist die APK 4 MB klein und der Build braucht kein Google-Maven.

Drei Entscheidungen sind erklärungsbedürftig:

- **Die Seite wird über eine erfundene `https`-Herkunft ausgeliefert**, nicht
  über `file:///android_asset/`. Eine `file://`-Seite ist eine undurchsichtige
  Herkunft, und darauf verweigert der WebView `localStorage` – der adaptive Teil
  (falsch beantwortete Fragen kommen häufiger) würde stillschweigend aufhören zu
  funktionieren, ohne dass auf dem Bildschirm etwas darauf hinweist. Jede
  Anfrage an diese Herkunft wird aus der APK beantwortet, das Netz wird nie
  benutzt.
- **Die App fordert keine `INTERNET`-Berechtigung an.** Damit kann sie
  nachweislich nichts nachladen, auch nicht versehentlich.
- **Die Seite wird um die Systemleisten herum eingerückt.** Ab Android 15 wird
  eine App mit `targetSdk 35` vom System auf Rand-zu-Rand gezwungen: Sie zeichnet
  unter die Statusleiste und in die Kamerakerbung, und nichts wird automatisch
  freigehalten. Ohne Gegenmaßnahme beginnt die erste Zeile der Seite hinter der
  Uhr. Die Einschnitte (Statusleiste, Aussparung, Navigationsleiste) werden
  deshalb als **Innenabstand des WebView** gesetzt – nicht als Fensterrand –,
  damit in der Lücke die Hintergrundfarbe der Seite steht und die Fläche neben
  der Kerbung wie ein Teil der App wirkt. Auf älteren Android-Versionen wird
  derselbe Zustand absichtlich hergestellt, damit ein einziger Codepfad für alle
  Geräte gilt.

## Bereitstellung

Ausgeliefert wird über **GitHub Pages** aus diesem Repository:
https://youssefeghaly.github.io/einbuergerungstest/

**Jeder Push auf `main` baut die Seite automatisch neu**, in der Regel binnen
einer Minute. Es gibt keinen Build-Schritt: die Dateien im Wurzelverzeichnis
sind die Seite. Aus demselben Grund liegt auch die APK unter
https://youssefeghaly.github.io/einbuergerungstest/einbuergerungstest.apk und
lässt sich direkt auf dem Handy herunterladen.

Nach einem Push brauchen die Dateien ein paar Minuten, bis sie überall
ankommen: beide Hosts zwischenspeichern sie (GitHub Pages und
`raw.githubusercontent.com` für rund fünf Minuten). Wer sofort den neuen Stand
braucht, hängt eine Versionsnummer an die Adresse, etwa `?v=2`.

Vercel wurde bewusst entfernt: Es hat hier genau dasselbe getan wie GitHub
Pages, und für eine einzelne statische Seite ist ein Host genug.

## Grenzen

Der amtliche Katalog enthält **keinen Lösungsschlüssel**. Die richtigen Antworten
stammen aus einem externen, MIT-lizenzierten Datensatz. Geprüft ist, dass jede
Frage eindeutig zugeordnet ist und die Antwort auf die richtige der vier
Optionen zeigt (siehe `data/verification-report.md`). Die inhaltliche
Richtigkeit des fremden Schlüssels ist damit nicht amtlich bestätigt.

Details zur Herkunft: `NOTICE.md`.
