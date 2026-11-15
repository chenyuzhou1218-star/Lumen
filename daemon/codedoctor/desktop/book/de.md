# Lumen-Funktionshandbuch

Lumen ist ein Team aus KIs, das auf deinem Windows-Computer läuft. Du sprichst nur mit Lumen, ganz normal in deiner Sprache; es verteilt die Arbeit an das passendste Mitglied, wählt selbst die richtigen Werkzeuge aus und gibt dir das Ergebnis, wenn es fertig ist. Code schreiben, Fehler suchen, Videos schneiden, 3D erstellen, Webseiten und PDFs machen, im Netz recherchieren und den Computer bedienen: all das kann es.

## 1. Erste Schritte

- **Was du brauchst**: Windows, Python 3.12 und eine KI: Claude Code oder Codex (nach der Installation einmal im Terminal anmelden) oder einen API-Schlüssel (Dienste mit OpenAI- oder Anthropic-kompatibler Schnittstelle funktionieren).
- **Installation**: Führe `setup.ps1` im Lumen-Ordner aus (die chinesische Anleitung steht in `安装环境.ps1`). Dabei wird in diesem Ordner eine `.venv` angelegt und alle Pakete installiert, die Lumen braucht. Dein System-Python bleibt unverändert. Danach öffnest du Lumen mit einem Doppelklick auf `Lumen.cmd`.
- **Erstes Öffnen**: Nach der Begrüßungsseite wählst du die Oberflächensprache und einen Arbeitsordner, dann kann es losgehen. Das Modell kannst du später unter dem Eingabefeld wechseln.
- **Beim nächsten Öffnen**: Lumen kehrt in den Ordner zurück, mit dem du zuletzt gearbeitet hast. In der linken Leiste wechselst du den Ordner, beginnst einen neuen Chat oder durchsuchst deine Chats.

## 2. Nachrichten senden

- Schreib in das Eingabefeld, was du erledigt haben möchtest, und drück Enter zum Senden. Dateien kannst du hineinziehen oder hineinkopieren.
- **Spracheingabe**: Klick auf das Mikrofon und sprich. Du musst nicht druckreif reden; Lumen versteht dich dem Sinn nach und achtet nicht auf deine Grammatik.
- **Modell**: Unter dem Eingabefeld wählst du die KI (Claude Code, Codex oder ein Modell aus einem deiner angebundenen Dienste), daneben die Denkstärke. Das Modell bestimmst allein du; Lumen wechselt es nie von sich aus.
- **Wenn es nicht sicher ist, fragt es zuerst nach**: Versteht Lumen nicht genau, was du willst, erscheint ein Fragefenster. Jede Frage hat fertige Antworten zur Auswahl, du klickst einfach an. Möchtest du nicht antworten, kannst du überspringen; dann entscheidet Lumen selbst.
- **Unter einer Antwort**: kopieren, merken, neu beantworten, ändern und erneut fragen. Ist die Antwort fertig, klappen die Arbeitsschritte ein; nur das Ergebnis bleibt sichtbar. Klappst du sie auf, siehst du jeden einzelnen Schritt.

## 3. Freigabemodus

Unter dem Eingabefeld wählst du den Freigabemodus für diesen Chat. Er legt fest, ob die KI dich vor einer Aktion fragt:

| Freigabemodus | Wann sie dich fragt |
|---|---|
| Vollständig freigeben | Fragt nie, macht einfach |
| Für mich prüfen | Nur vor dem Löschen von Dateien und bevor sie mit Maus oder Tastatur den Computer bedient |
| Alles bei mir abfragen | Vor jeder Aktion, die etwas verändert |

Wenn sie fragen muss, erscheint oberhalb des Eingabefelds rechts unten eine kleine Karte: eine Zeile, was getan werden soll, daneben **Erlauben** und **Nicht erlauben**. Mit **Nicht erlauben** überspringst du nur diese eine Aktion, alles andere läuft weiter. Darüber hinaus gibt es keine weiteren Zugriffsbeschränkungen: Jeder Ordner und jede Festplatte auf diesem Computer ist nutzbar.

## 4. Das Lumen-Team

| Mitglied | Zuständig für |
|---|---|
| Lumen | Koordination: spricht mit dir, verteilt die Arbeit und gibt dir am Ende die Antwort |
| Spark | Schreibt Code und benutzt die verschiedenen Erstellungswerkzeuge |
| Prism | Prüft |
| Torch | Praxistest: lässt das Programm wirklich einmal laufen |
| Ray | Recherchiert im Netz |
| Lantern | Verwaltet Dateien |
| Beacon | Aufsicht: prüft die Ergebnisse der anderen nach |
| Iris | Bedient den Computer |

Jedes Mitglied hat sein eigenes Arbeitsgedächtnis und kann bei Bedarf einmalige Helfer rufen. Mitglieder arbeiten gleichzeitig, ohne sich in die Quere zu kommen.

**Lumen und du sind gleichberechtigt.** Es spricht wie ein fähiger Kollege: Liegst du falsch, sagt es das direkt und erklärt, warum. Hat es recht, ändert es seine Meinung nicht, nur weil du drängst, es sei denn, du nennst einen Grund. Wenn du eine Entscheidung treffen musst, setzt es sie um, sobald du entschieden hast.

## 5. Werkzeuge automatisch nutzen (ohne @)

Sag einfach, was du willst, zum Beispiel „Mach aus diesem Bild ein PDF“, „Schneide dieses Video auf die ersten 10 Sekunden“ oder „Mach einen roten 3D-Würfel“. Lumen kennt die Werkzeuge auf diesem Computer, wählt das passende aus und gibt die Aufgabe an das Mitglied weiter, das damit arbeiten kann.

Du kannst im Eingabefeld auch mit @ ein Werkzeug gezielt benennen; dann wird nur das genannte verwendet.

| Werkzeug | Wofür |
|---|---|
| CodeCut | Videos schneiden: schneiden, zusammensetzen, Untertitel, Musik, Export |
| Code3D | 3D-Modelle und Szenen mit dem Blender auf deinem Computer, Export als GLB und Bilder |
| CodeSound | Musik und Soundeffekte |
| CodePage | Webseiten |
| CodeGame | Kleine spielbare Spiele |
| CodeDeck | Folien und Dokumente (PowerPoint, Word, PDF) |
| CodeData | Excel- und CSV-Dateien analysieren; jede Zahl im Bericht lässt sich bis zur Quelle zurückverfolgen |
| CodeCAD | Teile für den 3D-Druck, Maße in Millimetern |
| CodeLab | Protokolle und Fortschritt von Modelltrainings anzeigen |
| CodeTools | Dutzende kleine Werkzeuge: Logoplakate, Flussdiagramme, QR-Codes, Untertitel, Vertonung, Stapelbearbeitung von Fotos, Dateien ordnen und mehr |
| CodeFilm | Aus einem Satz einen kurzen Film machen |
| CodePDF | Bilder in PDF umwandeln, zusammenführen, teilen, komprimieren, drehen, Seiten auswählen |

## 6. Rechte Seite

- **Werkzeugfenster**: Benutzt das Team ein Werkzeug, öffnet es sich automatisch rechts, damit du zusehen kannst. Dieses Fenster gehört der KI: Sie klickt und tippt darin, ohne deine Maus und Tastatur zu belegen; du siehst einen kleinen blauen Mauszeiger, der sich bewegt. Mit dem × oben im Fenster schließt du es.
- **Browser** (Strg+Umschalt+B): Hier suchst und öffnest du Webseiten; Links aus dem Chat öffnen sich ebenfalls hier. Recherchiert das Team im Netz, wird es hier angezeigt.
- **Terminal** (Strg+J): Eine echte PowerShell im aktuellen Ordner. Befehle, die das Team ausführt, werden hier farbig angezeigt.

## 7. Langzeitgedächtnis

- **Die KI merkt sich dich**: Bevor ein neuer Chat beginnt, geht die KI frühere Chats durch und verdichtet die wichtigsten Punkte zu einer Erinnerung: über dich (wer du bist, wie du sprichst, was du magst, welche Regeln du aufgestellt hast; gilt für alle Projekte) und über dieses Projekt (was gemacht wurde, was festgelegt ist, wo es gerade steht). Der neue Chat startet damit, sodass du nichts jedes Mal neu erklären musst.
- **Die Länge richtet sich nach dem Verlauf**: Bei wenigen Gesprächen sind es ein paar Zeilen, bei vielen wird es länger. Im Normalfall bleibt es unter 50.000 Zeichen, höchstens etwa 80.000. Darüber hinaus wird es neu verdichtet; dabei werden nur Details gekürzt, keine Ereignisse gehen verloren.
- **Wenn du warten musst, wird es dir gesagt**: Ist die Erinnerung des vorherigen Chats noch nicht fertig, zeigt der neue Chat „Frühere Chats werden durchgesehen…“, höchstens 90 Sekunden lang.
- **Du kannst sie einsehen, ändern und leeren**: unter „Einstellungen → Langzeitgedächtnis → Was die KI über dich weiß“. Was du änderst, berücksichtigt die KI künftig. Nach dem Leeren werden frühere Chats nicht mehr für eine neue Verdichtung herangezogen.
- Beim Arbeiten halten Mitglieder außerdem wichtige Fakten fest und rufen sie beim nächsten Mal automatisch ab. Wenn du ein Embedding-Modell auswählst, finden sie auch alte Erkenntnisse wieder, die mit anderen Worten formuliert sind.

## 8. Mehrere Dinge gleichzeitig

- Mehrere Chats können gleichzeitig laufen, ohne aufeinander zu warten: Wartet einer auf deine Antwort, arbeitet der andere weiter.
- Denselben Ordner kannst du in mehreren Fenstern öffnen (Strg+Umschalt+N).
- Was ein Chat gelernt hat, weiß der nächste Chat, auch wenn es ein anderer ist (siehe Abschnitt 7).

## 9. Computerbedienung

- Ab dem Start verfügbar: Screenshots, Maus, Tastatur, Programme öffnen und schließen, Terminal, und zwar in allen Fenstern außer den Lumen-Fenstern. Gib einen Programmnamen oder den vollständigen Pfad an, dann lässt sich jedes Programm öffnen.
- Ob vorher nachgefragt wird, richtet sich nach dem Freigabemodus (Abschnitt 3).
- **Arbeitsweise**: Von Anfang an arbeitet die KI im Hintergrund und belegt deine Maus und Tastatur nicht. Bei Spielen oder anderen Programmen, die eine echte Maus brauchen, stellst du unter „Einstellungen → Computerbedienung“ auf Vordergrund um.
- **Not-Stopp**: Drück `Strg+Alt+Ende` oder bewege die Maus in die obere linke Ecke des Bildschirms.
- Soll die KI den Computer gar nicht anfassen: Schalte unter „Einstellungen → Computerbedienung“ die Option „Computersteuerung verbieten“ ein.

## 10. Wenn Administratorrechte nötig sind

Systemordner wie `C:\Windows` oder `Program Files` brauchen Administratorrechte. Meldet Windows „Zugriff verweigert“, startet die KI den Befehl mit Administratorrechten neu. Dann zeigt Windows sein eigenes Bestätigungsfenster, und du entscheidest, ob du es erlaubst.

## 11. Automatische Tests

Trage unter „Einstellungen → Automatische Tests“ den Testbefehl des Projekts ein, oder klick auf „Automatisch erkennen“. Ändert das Team Code, laufen die Tests automatisch vor Arbeitsbeginn, nach jeder Änderung und vor der Abgabe, ohne Modell und ohne Tokens. Wer einen bisher bestandenen Test kaputt macht, wird sofort darauf hingewiesen. Empfehlung: Committe vor Arbeitsbeginn einmal mit git. Dann siehst du jederzeit, was sich geändert hat, und kannst es zurücknehmen.

## 12. Oberflächensprache

English, Français, Español, Deutsch, Italiano, Português, 简体中文, insgesamt 7 Sprachen. Umstellen kannst du sie unter „Einstellungen → Erscheinungsbild“, die Änderung wirkt sofort. Auch das Werkzeugfenster rechts wechselt mit. Die KI antwortet in der Sprache, in der du schreibst.

## 13. Überblick über die Einstellungen

- **Dienste und Schlüssel**: Beliebig viele KI-Dienste anbinden. Schlüssel werden nur im Windows-Anmeldeinformationsspeicher abgelegt, nie in einer Konfigurationsdatei.
- **KI-Modelle**: Welcher Dienst mit welchem Modell für jedes Mitglied arbeitet, wie gründlich es denkt und auf welches Ersatzmodell bei Fehlern umgeschaltet wird.
- **Langzeitgedächtnis**: Erinnern ein- oder ausschalten, „Was die KI über dich weiß“, Erinnern nach Bedeutung.
- **Automatische Tests**, **Computerbedienung**: siehe oben.
- **Erscheinungsbild**: Sprache, Hintergrundbild, Schriftgröße, Akzentfarbe und mehr; Änderungen wirken sofort.
- **Nutzung**: Wie viel du heute, in den letzten sieben Tagen und insgesamt verbraucht hast.
- **Funktionshandbuch**: Diese Seite.

## 14. Praktische Kleinigkeiten

- **Strg+K**: Ein Feld findet alles: Chats, Seiten, Aktionen. Ab zwei Buchstaben findest du sogar Sätze, die du im Chat geschrieben hast. **Strg+/** zeigt alle Tastenkürzel.
- **Strg+N** neuer Chat, **Strg+B** linke Leiste ein- oder ausblenden, **Strg+F** im Chat suchen, **Strg+,** öffnet die Einstellungen.
- **Rechtsklick auf einen Chat**: umbenennen, als Markdown exportieren oder aus der Liste ausblenden (nicht gelöscht).
- **Phrasen**: Schreib einen Text und drück Strg+S, um ihn als Phrase zu speichern. In einem leeren Eingabefeld rufst du sie mit / auf. Nicht gesendete Texte bleiben auch erhalten, wenn du das Fenster schließt.
- **Erinnerung bei Fertigstellung**: Ist das Fenster nicht im Vordergrund, blinkt die Taskleiste, sobald eine Antwort fertig ist, und unten rechts erscheint ein Hinweis.
- **Browser**: Mit dem Stern merkst du dir diese Seite als Lesezeichen, Strg+Umschalt+T holt geschlossene Tabs zurück, und mit der Sprechblase schickst du diese Seite an Lumen.
- **Terminal**: Ein Rechtsklick auf die Ausgabe sendet die markierte oder die letzte Ausgabe an Lumen.

## 15. Sicherheit und Datenschutz

- Alle Modelle wählst du selbst; Lumen wechselt sie nie von sich aus.
- Deine Chats, Erinnerungen und Protokolle werden auf deinem eigenen Computer gespeichert (im Ordner `~/.codedoctor`).
- Schlüssel liegen nur im Windows-Anmeldeinformationsspeicher; in der Erinnerung werden keine Schlüssel gespeichert.
- Zahlungen und Anmeldungen erledigt die KI nicht für dich.

## 16. Tipps

- Je genauer du formulierst, desto näher kommt das Ergebnis beim ersten Versuch. Ungenaue Angaben sind auch in Ordnung; dann fragt Lumen zuerst nach.
- Wenn du schneller und günstiger arbeiten willst, wähle ein kleineres Modell oder eine geringere Denkstärke; für schwierige Aufgaben nimmst du ein größeres.
- Bei einem Absturz schick die Datei `~/.codedoctor/crash.log` an den Entwickler.
