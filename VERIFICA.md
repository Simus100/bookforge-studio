# Collaudo · 10 novembre 2026

La prima versione è stata collaudata su Windows x64 con Python 3.12 e CPU a 8 thread. Non è stato usato un manoscritto dell'utente: tutte le verifiche editoriali usano il testo dimostrativo incluso o dati temporanei isolati.

## Revisione e persistenza

14 test del protocollo e del salvataggio: ciclo completo, importazione ripetuta, rifiuto di applicazioni ripetute, conservazione del testo fino all'approvazione, spostamento degli intervalli non toccati, conflitto su brano modificato, richieste sovrapposte, modifiche non sovrapposte, eliminazione esplicita e annullamento, importazione atomica, libro o pacchetto errato, richieste duplicate, finestre non aggiornate, Unicode, backup/ripristino e segmentazione di frasi molto lunghe.

5 test HTTP controllano autenticazione delle scritture, origine delle richieste, intestazione Host, accesso ai soli file pubblici previsti e lettura dello stato.

Comando: `.runtime\Scripts\python.exe -m unittest discover -s tests -v`.

## Interfaccia

Un collaudo automatizzato con Chromium ha percorso la selezione reale nel DOM, la creazione dell'annotazione, il download del pacchetto, l'importazione del JSON di risposta, la visualizzazione delle differenze, l'approvazione e l'annullamento. Verificato che il manoscritto non cambi alla sola importazione della proposta. Verificata la reimportazione senza duplicazioni.

Verificati i layout a 1440×1000, 900×800 e 390×844 pixel, senza scorrimento orizzontale della pagina. Verificati modalità lettura, WAV locale, avvio della riproduzione, evidenziazione della frase, pausa e annotazione della frase corrente. Nessun errore JavaScript e nessuna richiesta browser verso domini esterni nel percorso collaudato.

`docs/screenshots/revisione-chiara.png` mostra una proposta dimostrativa nell'interfaccia; le relative annotazioni di prova non sono presenti nel progetto consegnato. `docs/screenshots/modalita-scura.png` mostra il tema scuro. Il selettore dei temi è stato verificato in entrambe le direzioni, con persistenza dopo la ricarica, moduli di editing coerenti e layout mobile senza scorrimento orizzontale.

## Audio locale

Paola medium e Riccardo x_low sono stati scaricati dal repository ufficiale delle voci, verificati con il manifest e usati per generare WAV reali. Modelli e audio sono in `dati/voci` e `dati/audio`.

Su tre brevi campioni per voce, il rapporto fra tempo di generazione e durata audio, con motore già caricato, è stato:

| Voce | Secondi di calcolo per secondo di audio |
|---|---:|
| Paola | 0,102–0,107 |
| Riccardo | 0,071–0,074 |

Il primo caricamento del modello ha richiesto circa 13–18 secondi nell'ambiente di prova. I campioni non sono un benchmark rappresentativo di tutti i computer o di interi libri, e non misurano la qualità percepita della voce. La riproduzione successiva riusa il modello residente e i segmenti nella cache.

## Da verificare su hardware adatto

Il profilo Qwen3-TTS Studio include installazione isolata, download dei pesi, caricamento offline, voce fissa e worker residente su CUDA. Non è stato installato o eseguito su GPU in questa sessione. Non viene presentato come un motore già collaudato qui. Il suo installer effettua una sintesi reale in italiano prima di renderlo selezionabile.

Non è stato effettuato un test di qualità con l'autore, un lettore professionista o un intero romanzo. Il confezionamento come installer `.exe`, l'importazione di DOCX/EPUB e l'allineamento di audio generato per paragrafi sono sviluppi successivi, non funzioni presenti in questa prima versione.
