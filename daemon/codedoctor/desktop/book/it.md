# Manuale delle funzioni di Lumen

Lumen è una squadra di IA che vive sul tuo computer Windows. Parli solo con Lumen, in linguaggio naturale; lui assegna il lavoro al membro della squadra più adatto, sceglie da solo gli strumenti giusti e ti consegna il risultato a lavoro finito. Può scrivere codice, cercare problemi, montare video, creare 3D, siti web e PDF, cercare informazioni online e controllare il computer.

## 1. Come iniziare

- **Cosa serve**: Windows, Python 3.12, più un'IA: Claude Code o Codex (dopo l'installazione accedi una volta dal terminale), oppure una chiave API (vanno bene i servizi compatibili con le API OpenAI o Anthropic).
- **Installazione**: nella cartella di Lumen esegui `setup.ps1` (le istruzioni in cinese sono in `安装环境.ps1`). Crea in questa cartella un `.venv`, installa i pacchetti necessari a Lumen e non tocca il Python del tuo sistema. Poi apri Lumen con un doppio clic su `Lumen.cmd`.
- **Primo avvio**: dopo la schermata di benvenuto scegli la lingua dell'interfaccia e una cartella di lavoro, e puoi iniziare. Il modello può essere cambiato in seguito, sotto la casella di input.
- **Avvii successivi**: Lumen torna alla cartella che avevi aperto l'ultima volta. Nella barra a sinistra puoi cambiare cartella, aprire una nuova chat e cercare nelle chat.

## 2. Inviare messaggi

- Scrivi nella casella ciò che vuoi fare e premi Invio per inviare. Puoi trascinare o incollare dei file.
- **Input vocale**: clicca sul microfono e parla. Non serve un linguaggio curato: Lumen capisce il senso, non giudica la grammatica.
- **Modello**: sotto la casella scegli quale IA usare (Claude Code, Codex o un modello del servizio che hai collegato); accanto c'è l'intensità del ragionamento. Il modello lo decidi sempre tu: Lumen non lo cambia da solo.
- **Se non è sicuro, ti chiede prima**: se non ha capito bene cosa vuoi, compare un pannello di domande con le opzioni già pronte; ti basta cliccare. Se preferisci non rispondere, puoi saltare e lasciarlo decidere da solo.
- **Sotto la risposta**: copia, ricorda, rispondi di nuovo, oppure modifica e chiedi ancora. Quando la risposta è finita, i suoi passaggi si chiudono e resta solo il risultato; aprili per vedere ogni passo.

## 3. Modalità di approvazione

Sotto la casella scegli la modalità di approvazione di questa conversazione. Stabilisce se l'IA ti chiede conferma prima di agire:

| Modalità di approvazione | Quando ti chiede |
|---|---|
| Completamente libero | Mai, fa direttamente |
| Verifica per me | Solo prima di eliminare file e prima di usare mouse e tastiera sul computer |
| Chiedi a me per tutto | Prima di ogni operazione che modifica qualcosa |

Quando serve la tua conferma, sopra la casella in basso a destra compare una piccola scheda: una riga che descrive cosa sta per fare, accanto ai pulsanti **Consenti** e **Non consentire**. Con **Non consentire** salti solo quell'operazione, e il resto continua normalmente. A parte questo, Lumen non ha altri limiti di permesso: ogni cartella e ogni disco del computer è accessibile.

## 4. La squadra di Lumen

| Membro | Responsabilità |
|---|---|
| Lumen | Coordinatore: parla con te, distribuisce il lavoro e ti dà la risposta finale |
| Spark | Scrive codice e usa vari strumenti di creazione |
| Prism | Verifica |
| Torch | Prova sul campo: esegue davvero il programma |
| Ray | Cerca informazioni online |
| Lantern | Gestisce i file |
| Beacon | Supervisione: ricontrolla i risultati degli altri |
| Iris | Controlla il computer |

Ogni membro ha una propria memoria di lavoro e può chiamare degli assistenti temporanei per una mano. I membri possono lavorare contemporaneamente senza sovrapporsi.

**Lumen è alla pari con te.** Parla come un collega capace: se sbagli te lo dice apertamente e spiega il motivo; se ha ragione non cambia idea solo perché insisti, a meno che tu non gli dia una buona ragione. Le decisioni che spettano a te, una volta prese, lui le segue fedelmente.

## 5. Uso automatico degli strumenti (senza @)

Ti basta dire cosa vuoi, per esempio «trasforma questa immagine in PDF», «taglia questo video ai primi 10 secondi» o «crea un cubo 3D rosso». Lumen sa quali strumenti sono installati sul computer, sceglie quello giusto e affida il lavoro al membro che lo possiede.

Puoi anche scrivere @ nella casella per indicare uno strumento preciso: in quel caso viene usato solo quello.

| Strumento | A cosa serve |
|---|---|
| CodeCut | Montaggio video: tagli, unioni, sottotitoli, colonna sonora, esportazione |
| Code3D | Modelli e scene 3D, con il Blender installato sul tuo computer; esporta GLB e immagini |
| CodeSound | Musica ed effetti sonori |
| CodePage | Pagine web |
| CodeGame | Piccoli giochi giocabili |
| CodeDeck | Presentazioni e documenti (PowerPoint, Word, PDF) |
| CodeData | Analisi di Excel e CSV; ogni numero del rapporto è verificabile fino alla fonte |
| CodeCAD | Pezzi stampabili in 3D; dimensioni in millimetri |
| CodeLab | Log e avanzamento dell'addestramento dei modelli |
| CodeTools | Decine di piccoli strumenti: poster con logo, diagrammi di flusso, codici QR, sottotitoli, doppiaggio, ritocco fotografico in serie, organizzazione dei file e altro |
| CodeFilm | Un cortometraggio da una sola frase |
| CodePDF | Da immagini a PDF, unione, divisione, compressione, rotazione, selezione di pagine |

## 6. Pannello destro

- **Finestra degli strumenti**: quando la squadra usa uno strumento, la finestra si apre automaticamente a destra e puoi seguire il lavoro. Questa finestra è riservata all'IA: è lei a cliccare e digitare lì dentro, senza occupare il tuo mouse e la tastiera; vedrai un piccolo mouse blu che si muove. Clicca la × sulla finestra per chiuderla.
- **Browser** (Ctrl+Shift+B): qui cerchi e apri pagine web; anche i link della chat si aprono qui. Quando la squadra cerca informazioni online, lo vedi in questo pannello.
- **Terminale** (Ctrl+J): un vero PowerShell, già nella cartella attuale. I comandi eseguiti dalla squadra compaiono qui con i colori.

## 7. Memoria a lungo termine

- **L'IA ti ricorda**: prima che inizi ogni nuova chat, l'IA rilegge le chat precedenti e ne riassume i punti chiave in una memoria: su di te (chi sei, come parli, cosa ti piace, le regole che hai stabilito; vale per tutti i progetti) e sul progetto (cosa è stato fatto, cosa è stato deciso, a che punto si è arrivati). La nuova chat parte già con questa memoria, così non devi ripetere tutto ogni volta.
- **La lunghezza segue la storia**: se hai chiacchierato poco, sono poche righe; se hai chiacchierato molto, è più lunga. Di solito resta entro 50.000 caratteri e al massimo intorno a 80.000; oltre, viene compressa di nuovo, riducendo solo i dettagli senza perdere le cose importanti.
- **Ti avvisa quando deve aspettare**: se la memoria della chat precedente non è ancora pronta, la nuova chat mostra «Revisione delle chat precedenti…» e attende al massimo 90 secondi.
- **Puoi vederla, modificarla e svuotarla**: in «Impostazioni → Memoria a lungo termine → Cosa l'IA ricorda di te». Ciò che modifichi viene rispettato in seguito; dopo lo svuotamento, le vecchie chat non verranno più riutilizzate per riassumerle.
- Mentre lavorano, i membri annotano i fatti degni di nota e li ricordano la volta successiva; se scegli un modello di embedding, possono anche ritrovare conclusioni vecchie espresse con parole diverse.

## 8. Fare più cose insieme

- Più chat possono procedere in parallelo senza aspettarsi: se una chat aspetta la tua risposta, un'altra continua a lavorare.
- Puoi aprire più finestre per la stessa cartella (Ctrl+Shift+N).
- Ciò che una chat impara, le altre lo sapranno alla volta successiva (vedi sezione 7).

## 9. Controllo del computer

- Disponibile subito: screenshot, mouse, tastiera, apertura e chiusura di programmi, terminale, su tutte le finestre (tranne quelle di Lumen stesso). Dai il nome di un programma o il percorso completo e può avviarlo.
- Se chiedere prima la tua conferma dipende dalla modalità di approvazione (sezione 3).
- **Modo di operare**: fin dall'inizio lavora in background e non occupa mouse e tastiera; per i giochi e altre situazioni che richiedono il vero mouse, passa al modo in primo piano in «Impostazioni → Uso del computer».
- **Arresto d'emergenza**: premi `Ctrl+Alt+End`, oppure porta il mouse nell'angolo in alto a sinistra dello schermo.
- Se non vuoi che l'IA tocchi il computer: in «Impostazioni → Uso del computer» attiva «Vieta il controllo del computer».

## 10. Quando servono i diritti di amministratore

Cartelle di sistema come `C:\Windows` e `Program Files` richiedono i diritti di amministratore. Quando Windows risponde «Accesso negato», l'IA riesegue quel comando come amministratore; Windows mostrerà la sua finestra di conferma e sarai tu a decidere se consentire.

## 11. Test automatici

In «Impostazioni → Test automatici» inserisci il comando di test del progetto (oppure clicca «Rileva automaticamente»). Quando la squadra modifica il codice, il sistema esegue i test prima di iniziare, dopo ogni modifica e prima della consegna (senza passare dal modello e senza consumare token); se qualcuno rompe un test che prima passava, viene segnalato subito. Ti consigliamo di fare un commit con git prima di iniziare, così vedi sempre cosa è cambiato e puoi annullare.

## 12. Lingua dell'interfaccia

Sono disponibili 7 lingue: English、Français、Español、Deutsch、Italiano、Português、简体中文. Si cambiano in «Impostazioni → Aspetto» ed è immediato. Anche la finestra degli strumenti a destra cambia lingua. L'IA risponde nella lingua in cui scrivi i messaggi.

## 13. Panoramica delle impostazioni

- **Servizi e chiavi**: collega quanti servizi IA vuoi. Le chiavi sono conservate solo in Gestione credenziali di Windows, mai nel file di configurazione.
- **Modelli IA**: quale modello di quale servizio usa ogni membro, quanto a fondo deve ragionare e quale modello di riserva usare in caso di errore.
- **Memoria a lungo termine**: interruttore del richiamo, «Cosa l'IA ricorda di te», richiamo per significato.
- **Test automatici** e **Uso del computer**: vedi sopra.
- **Aspetto**: lingua, sfondo, dimensione del testo, colore di evidenziazione e altro; le modifiche hanno effetto subito.
- **Utilizzo**: quanto hai usato oggi, negli ultimi sette giorni e in totale.
- **Manuale delle funzioni**: è questa pagina.

## 14. Piccole funzioni utili

- **Ctrl+K**: una sola casella per trovare tutto: chat, pagine, operazioni; con due o più caratteri trova anche ciò che hai detto in chat. **Ctrl+/** mostra tutte le scorciatoie.
- **Ctrl+N** nuova chat, **Ctrl+B** nasconde o mostra la barra a sinistra, **Ctrl+F** cerca nella chat, **Ctrl+,** apre le impostazioni.
- **Clic destro su una chat**: rinomina, esporta in Markdown, nasconde dall'elenco (senza eliminarla).
- **Frasi salvate**: scrivi un testo, premi Ctrl+S per salvarlo come frase pronta e richiamala digitando / in una casella vuota. Se non l'hai inviata, resta anche dopo aver chiuso la finestra.
- **Promemoria a fine lavoro**: se la finestra non è in primo piano, quando la risposta è pronta la barra delle applicazioni si illumina e nell'angolo in basso a destra compare un avviso.
- **Browser**: la stellina salva questa pagina nei preferiti, Ctrl+Shift+T riapre una scheda chiusa, il fumetto invia questa pagina a Lumen.
- **Terminale**: clic destro sull'output per inviare a Lumen il testo selezionato o l'output più recente.

## 15. Sicurezza e privacy

- Tutti i modelli li scegli tu: Lumen non ne cambia nessuno da solo.
- Le tue chat, la memoria e i log sono salvati sul tuo computer (nella cartella `~/.codedoctor`).
- Le chiavi stanno solo in Gestione credenziali di Windows; la memoria non salva mai chiavi.
- L'IA non esegue al posto tuo pagamenti o accessi.

## 16. Consigli

- Più sei preciso, più al primo tentativo otterrai ciò che vuoi; se non sei preciso non fa niente, ti chiederà prima.
- Per andare più veloce e consumare meno, scegli un modello più piccolo o un'intensità di ragionamento più bassa; per i lavori difficili passa a un modello più grande.
- In caso di chiusura imprevista, invia il file `~/.codedoctor/crash.log` allo sviluppatore.
