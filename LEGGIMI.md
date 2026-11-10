# BookForge Studio · prima versione locale

Un ambiente per supervisionare e correggere un manoscritto scritto con l'AI. Il libro è al centro; le annotazioni e le proposte vivono nei margini. Il testo dimostrativo iniziale è inventato e non proviene dal tuo libro.

## Avvio

Apri **Avvia.cmd**. L'app si apre nel browser e il servizio gira esclusivamente su `127.0.0.1`, sul tuo computer. La finestra del servizio va lasciata aperta durante l'uso. Non serve un account e non ci sono chiamate a servizi AI dal programma.

Per fermare il servizio locale puoi chiudere la sua finestra oppure aprire **Arresta.cmd**. Chiudere soltanto la scheda del browser lascia il servizio disponibile per riaprire il libro.

Nella copia locale iniziale sono state installate e provate le voci Paola e Riccardo. Il repository pubblico contiene i sorgenti: su una nuova installazione scarica le voci dalle impostazioni di ascolto. Per trasferire un progetto personale, copia i sorgenti e la cartella `dati` senza copiare gli ambienti `.runtime` e `.studio`: vengono ricreati sulla nuova macchina, evitando percorsi Python legati al PC precedente. Serve Python **3.12**, richiesto dalle versioni delle dipendenze fissate in `requirements.txt`. L'avvio cerca anche il Python incluso con Codex, se disponibile. Per reinstallare le dipendenze occorre Internet; i modelli già presenti in `dati/voci` restano disponibili. Il profilo Studio va reinstallato e verificato sulla nuova GPU.

Il browser è l'interfaccia dell'app locale: non è un sito pubblicato. Nessuna CDN, font remoto o analitica viene caricata.

In alto a destra, il selettore **Chiaro / Scuro** cambia il tema di tutta l'interfaccia, compresi editor, commenti, differenze e lettore vocale. La preferenza viene conservata nel browser e ripristinata prima di mostrare la pagina alle aperture successive.

## Il ciclo di revisione

1. **Importa testo** da `.txt` o `.md`, oppure crea e modifica un capitolo. Ogni file importato diventa un capitolo. In questa versione il Markdown viene mostrato come testo, non interpretato come impaginazione.
2. Seleziona il brano e scegli **Annota il brano**. Scrivi cosa vorresti cambiare, con eventuali vincoli. La richiesta viene salvata subito, senza modificare il testo.
3. Completa la **Carta del libro** con voce, punto di vista, fatti di canone e indicazioni editoriali. Le regole pertinenti della tua BookForge possono essere incollate qui. La skill completa non viene caricata automaticamente.
4. Usa **Esporta richieste**. Si scarica un JSON autosufficiente con istruzioni, brani originali, commenti, capitoli interessati e un modello di risposta. L'esportazione comprende tutte le nuove richieste valide del progetto, anche su capitoli diversi.
5. Allega il JSON a un'altra AI, anche in una conversazione separata. Il pulsante **Copia il messaggio** fornisce il testo da accompagnare al file. L'app non invia automaticamente nulla.
6. **Importa proposte dell'AI** dal file JSON restituito o incollando il contenuto. Le proposte vengono verificate tutte prima dell'importazione; un errore strutturale annulla l'intera importazione.
7. Confronta originale e proposta. Le parti rimosse sono barrate, quelle aggiunte evidenziate. **Approva e applica** sostituisce esattamente il brano previsto. **Archivia** chiude la richiesta senza applicarla.

Per ritoccare ulteriormente il testo puoi usare **Modifica** sul capitolo, prima o dopo aver applicato una proposta. La prima versione non ha un editor dedicato alla singola proposta né una chat AI integrata.

Puoi continuare a leggere e annotare mentre l'AI lavora. Le annotazioni su parti rimaste uguali si spostano quando cambi altre parti del capitolo. Se tocchi il brano annotato, oppure applichi una correzione sovrapposta, la relativa proposta viene bloccata e segnalata. Crea una nuova richiesta sul brano aggiornato; il sistema non tenta una fusione creativa.

**Deterministico** riguarda l'applicazione: stesso brano originale, stessa sostituzione, stessa modifica. Non significa che un modello generativo produca sempre la stessa riscrittura. Ripetere un'importazione identica non duplica le proposte, e una richiesta già applicata non può essere applicata di nuovo.

## Ascolto completamente locale

Apri il selettore della voce in basso a sinistra.

| Profilo | Motore | Per cosa è previsto | Stato della prima consegna |
|---|---|---|---|
| Leggera · Paola | Piper, modello italiano medium | PC con CPU normale; nessuna GPU necessaria | Scaricato e verificato con sintesi reale |
| Essenziale · Riccardo | Piper, modello italiano x_low | PC meno potenti e modello più piccolo | Scaricato e verificato con sintesi reale |
| Studio · Narratore | Qwen3-TTS 1.7B CustomVoice, voce Ryan in italiano | GPU NVIDIA/CUDA compatibile; diversi GB di disco e memoria GPU | Integrazione presente; non collaudata su GPU in questa sessione |

I pesi vengono scaricati su disco. Una volta installati, testo e audio sono elaborati senza Internet. L'app non usa il lettore vocale del browser e non effettua fallback al cloud.

**Adatta la voce alle prestazioni del PC** sceglie fra i modelli già scaricati, usando il rapporto fra tempo di generazione e durata audio. Parte da Paola; preferisce Riccardo se Paola risulta lenta, e considera Studio dopo che è stato selezionato e provato almeno una volta con esito sufficientemente veloce. La scelta automatica non scarica modelli di propria iniziativa. I tempi osservati non garantiscono le stesse prestazioni su altri testi o durante carichi elevati.

Il download Studio crea un ambiente separato `.studio`, installa PyTorch CUDA e Qwen, verifica la GPU, scarica i modelli ed esegue una breve sintesi di prova locale. La voce diventa selezionabile soltanto se la prova riesce. Il primo download può richiedere diversi minuti e diversi GB. Se fallisce, il motivo appare nell'app e in `dati/installazione-studio.log`; Piper continua a essere disponibile. Questa implementazione GPU è prevista per Windows/Linux NVIDIA, non per GPU AMD o Apple Silicon.

La voce Studio usa un timbro fisso per mantenere continuità fra frasi. L'italiano è supportato dal modello; accento, pronuncia e naturalezza vanno ascoltati sul tuo manoscritto. Il profilo più pesante non garantisce sempre un risultato migliore.

Ogni frase è sintetizzata come un segmento esatto di testo. L'evidenziazione usa il tempo effettivo di riproduzione di quel segmento, senza stimare la durata in base al numero di caratteri. Fino a tre segmenti vengono preparati in anticipo e programmati con Web Audio. Questa scelta offre sincronizzazione semplice e precisa per la revisione; intonazione e continuità fra frasi restano meno ricche di una produzione professionale per paragrafi con allineamento fonetico. Un blocco eccezionale senza punteggiatura può essere suddiviso in più segmenti di massimo 900 caratteri.

Controlli: pausa/ripresa, frase precedente/successiva, velocità, evidenziazione, scorrimento automatico disattivabile. **Annota qui** ferma la lettura e apre una nota sulla frase corrente. Puoi anche selezionare un passaggio e scegliere **Ascolta da qui**. Scorciatoie: `Spazio` per pausa/ripresa; `N` durante l'ascolto per annotare. Le scorciatoie non interferiscono con i campi di scrittura.

Il primo caricamento del modello può richiedere più tempo. Le riproduzioni successive riutilizzano modello e audio. La cache audio viene limitata a circa 512 MB; i modelli restano scaricati.

## Salvataggio e recupero

- Il progetto corrente è in `dati/manoscritto.sqlite3`; il salvataggio è transazionale.
- **Esporta progetto** salva un JSON con capitoli, regole, richieste e proposte. Produce anche un backup SQLite locale.
- **Apri un progetto** ripristina un JSON esportato. Il progetto precedente viene conservato in un backup.
- **Annulla ultima operazione** ripristina l'operazione precedente sul progetto, comprese le correzioni. Non c'è ancora un comando Ripeti.
- I backup locali sono in `dati/backup`. Ne viene creato uno anche all'avvio. Non vengono eliminati automaticamente.
- **Riscarica l'ultimo pacchetto** recupera l'esportazione più recente.
- Due finestre con revisioni diverse non possono sovrascriversi silenziosamente: in caso di conflitto ricarica quella non aggiornata. Copia prima eventuali appunti non ancora salvati nei moduli.

Il download dei modelli comunica con i repository dei modelli e con i distributori delle dipendenze; non include il manoscritto. I pacchetti di revisione contengono il testo dei capitoli interessati: sei tu a passarli all'AI scelta. L'abbonamento o i costi di quell'AI dipendono dal servizio in cui apri il file, non dall'app locale.

## Verifica e limiti

Sono previsti test del protocollo per versioni, brani cambiati, intervalli sovrapposti, reimportazione, annullamento e Unicode. Comando: `python -m unittest discover -s tests -v`.

Il collaudo dell'interfaccia copre selezione, annotazione, esportazione, importazione, confronto, applicazione e annullamento; il lettore Piper è verificato generando e riproducendo WAV locali, con evidenziazione della frase e pausa. Layout verificato a 1440, 900 e 390 pixel. Il riepilogo della consegna è in `VERIFICA.md`.

Questa è una prima versione funzionante con interfaccia browser, non un installer `.exe` firmato. Importa testo semplice; non importa ancora DOCX/EPUB, formattazione complessa, note a piè di pagina o immagini. Supporta un progetto aperto per cartella dell'app; i progetti completi possono essere esportati e riaperti. Il confronto grafico evidenzia l'intervallo cambiato fra prefisso e suffisso comuni, non ogni singola modifica indipendente all'interno di una lunga riscrittura.

## Fonti dei motori

- Piper: https://github.com/OHF-Voice/piper1-gpl
- Voci italiane: https://huggingface.co/rhasspy/piper-voices
- Qwen3-TTS: https://github.com/QwenLM/Qwen3-TTS

Vedi `TERZE_PARTI.md` per provenienza e licenze.
