# Motori e modelli utilizzati

Il codice sorgente di BookForge Studio è disponibile in questa cartella. L'avviso di copyright per i contenuti originali è in [LICENSE](LICENSE). I motori e i modelli di terze parti hanno licenze proprie, conservate nei rispettivi pacchetti o repository; tali licenze non sono modificate dall'avviso di copyright dell'applicazione.

- **Piper 1.8.0**, OHF-Voice: motore locale GPL-3.0. Sorgente e licenza: https://github.com/OHF-Voice/piper1-gpl. Dipendenze installate nell'ambiente `.runtime`, comprese ONNX Runtime ed eSpeak NG.
- **Paola medium**, italiano: modello scaricato dal repository `rhasspy/piper-voices`; la relativa MODEL_CARD è conservata accanto al modello in `dati/voci`. Il dataset indicato dalla scheda è `paolapersico1/Voice-Dataset-Italian`, con metadato di licenza CC0-1.0 al momento della verifica. Scheda modello: https://huggingface.co/rhasspy/piper-voices/blob/main/it/it_IT/paola/medium/MODEL_CARD. Dataset: https://huggingface.co/datasets/paolapersico1/Voice-Dataset-Italian.
- **Riccardo x_low**, italiano: modello opzionale dal medesimo repository; MODEL_CARD scaricata con i pesi. Consultare la scheda associata al file effettivamente scaricato.
- **Qwen3-TTS 1.7B CustomVoice**, opzionale: modello e codice pubblicati con licenza Apache-2.0. Sorgente: https://github.com/QwenLM/Qwen3-TTS. Modello: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice. Il programma scarica i file della relativa snapshot, comprese le licenze presenti nel repository.

I testi dimostrativi e l'interfaccia sono stati creati per questa app. Nessuna voce di una persona viene clonata e non è richiesto un campione vocale dell'autore.

Le copie locali dei modelli Piper sono verificate contro gli hash del manifest del distributore durante l'installazione. I log di installazione Studio contengono diagnostica delle dipendenze; i log HTTP dell'app non includono il contenuto del manoscritto.
