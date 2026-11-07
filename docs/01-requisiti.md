# 01 — Requisiti

Priorità: **M** = indispensabile per l'MVP · **S** = importante · **C** = desiderabile.
La milestone in cui ogni requisito viene realizzato è indicata in `04-piano.md`.

## Obiettivo

Permettere a un autore di scrivere documentazione nella propria lingua madre e di produrre, senza tradurre a mano,
un documento nella lingua ufficiale di progetto, conforme ai template Word aziendali e con terminologia coerente.

## Utenti

| Ruolo | Cosa fa |
| --- | --- |
| Autore | Scrive nella sua lingua, rivede l'anteprima tradotta, corregge termini e tono, esporta |
| Revisore | Rivede la traduzione segmento per segmento e la approva |
| Responsabile terminologia | Mantiene glossario e regole di stile del progetto |
| Amministratore | Installa l'app, configura il modello, carica i template aziendali |

## Requisiti funzionali

### Workspace e struttura del documento

| ID | Requisito | Priorità |
| --- | --- | --- |
| RF-01 | Un **progetto** è una cartella su disco con un file `progetto.yaml` | M |
| RF-02 | I **capitoli** sono cartelle, le **sezioni** sono file `.md`; ammessi sottocapitoli fino a 2 livelli | M |
| RF-03 | L'ordine è dato dal prefisso numerico (`01-`, `02-`); la UI permette riordino via drag & drop rinumerando i file | M |
| RF-04 | Il titolo mostrato è il campo `title` del front matter, o in mancanza il primo titolo del file, o il nome del file | M |
| RF-05 | Creazione, rinomina, spostamento ed eliminazione di capitoli e sezioni dalla UI | M |
| RF-06 | Immagini salvate nella cartella `img/` del capitolo; incolla da appunti e trascinamento creano il file automaticamente | M |
| RF-07 | Riferimenti incrociati tra sezioni e capitoli (`[vedi](../02-architettura/01-moduli.md#database)`) risolti in export | S |
| RF-08 | Il progetto è un normale repository Git: l'app mostra lo stato (modificato/pulito) e permette commit con messaggio | C |
| RF-09 | **Scheletro di progetto da file di configurazione** (`scheletro.yaml`): elenco di capitoli e sezioni attesi (es. struttura prescritta da una norma come ECSS), con titolo, ordine, note guida e obbligatorietà; creazione di un progetto dallo scheletro e verifica di conformità (sezioni mancanti, extra, fuori ordine) | S |

### Editor

| ID | Requisito | Priorità |
| --- | --- | --- |
| RF-10 | Due modalità sullo **stesso file .md**: **Documento** (visuale, come un word processor, per chi non conosce il Markdown) e **Markdown** (testo con evidenziazione); passaggio con un clic senza perdita di contenuto | M |
| RF-10b | Entrambe le modalità hanno barra strumenti essenziale e menu `/`; la modalità scelta è ricordata per utente | M |
| RF-10c | Il Markdown salvato è normalizzato in forma canonica, così passare da una modalità all'altra non genera differenze spurie in Git | M |
| RF-11 | Supporto a: titoli, elenchi, tabelle (pipe e griglia), immagini con didascalia, note a piè di pagina, citazioni, codice | M |
| RF-12 | Editor visuale di tabelle (aggiungi riga/colonna, allineamento) che scrive Markdown valido | S |
| RF-13 | Diagrammi da codice Mermaid, resi come immagine in anteprima ed export | S |
| RF-14 | Grafici da dati (CSV o tabella) con specifica Vega-Lite, resi come immagine | C |
| RF-15 | Salvataggio automatico (debounce 1 s) e indicatore di stato | M |
| RF-16 | Controllo ortografico e grammaticale della lingua sorgente (LanguageTool self-hosted, opzionale) | S |

### Traduzione

| ID | Requisito | Priorità |
| --- | --- | --- |
| RF-20 | Anteprima tradotta affiancata, aggiornata per segmento mentre si scrive | M |
| RF-21 | Lingua sorgente per progetto; una **lingua ufficiale** obbligatoria (es. inglese) | M |
| RF-21b | **Lingue aggiuntive** facoltative (es. tedesco, francese), tradotte **sempre dal sorgente**, non dalla lingua ufficiale | S |
| RF-21c | La lingua ufficiale si traduce in tempo reale; le aggiuntive in background a bassa priorità o su richiesta | S |
| RF-21d | Per ogni lingua: tono proprio (es. *Sie*/*du* in tedesco), voci di glossario proprie, formato di date e numeri | S |
| RF-21e | Opzione per lingua: usare come base la lingua ufficiale **approvata** (pivot) quando la coppia diretta rende peggio | C |
| RF-22 | Si traduce solo il testo: codice, URL, formule, segnaposto `{{...}}` e termini "non tradurre" restano intatti | M |
| RF-23 | Correzione manuale di un segmento tradotto, che diventa **bloccato** e non viene più sovrascritto | M |
| RF-24 | Se cambia il sorgente di un segmento bloccato, il segmento diventa **da rivedere** e propone la nuova traduzione senza applicarla | M |
| RF-25 | Tono per progetto, sovrascrivibile per sezione: formale, neutro, informale | M |
| RF-26 | Istruzione in linguaggio naturale su un segmento ("più conciso", "usa *deliverable*") | S |
| RF-27 | Nota di contesto per il traduttore nel front matter della sezione (es. "pubblico: tecnici di manutenzione") | S |
| RF-28 | Stato per segmento: in traduzione, tradotto, da rivedere, approvato | M |
| RF-29 | Memoria di traduzione: segmenti approvati riusati per corrispondenza esatta; suggeriti per corrispondenza simile | S |
| RF-30 | Ritraduzione in blocco di una sezione, di un capitolo o del progetto (rispettando i blocchi) | M |
| RF-31 | Chi conosce la lingua di destinazione può scrivere direttamente nell'anteprima: il segmento diventa manuale e bloccato | M |
| RF-32 | Dopo una modifica diretta, il sistema propone l'aggiornamento del sorgente (retro-traduzione) come suggerimento non bloccante: Applica / Ignora; "Ignora" lascia il segmento segnato come *divergente* | S |

### Glossario

| ID | Requisito | Priorità |
| --- | --- | --- |
| RF-40 | Glossario di progetto in `glossario.yaml`: termine sorgente, termine imposto, termini vietati, note | M |
| RF-41 | Voci "non tradurre" (nomi prodotto, sigle) | M |
| RF-42 | Verifica automatica dopo ogni traduzione; in caso di violazione un secondo tentativo, poi segnalazione | M |
| RF-43 | Aggiunta di una voce dal menu contestuale selezionando una parola nell'anteprima | S |
| RF-44 | Import/export glossario in TBX e CSV | C |

### Template aziendali

| ID | Requisito | Priorità |
| --- | --- | --- |
| RF-50 | Caricamento di un template `.docx` aziendale (copertina, intestazioni, piè di pagina, stili, logo) | M |
| RF-51 | Analisi automatica del template: elenco stili disponibili, segnaposto `{{campo}}`, posizione del contenuto `{{CONTENUTO}}` | M |
| RF-52 | Mappatura stili: titoli 1-6, corpo, didascalia, tabella, elenchi, citazione, codice → stili del template, con proposta automatica | M |
| RF-53 | Campi del template compilati dai metadati di `progetto.yaml` (codice documento, revisione, cliente, data…) | M |
| RF-54 | Tabella delle revisioni generata da `progetto.yaml` se il template contiene il segnaposto `{{REVISIONI}}` | S |
| RF-55 | Creazione di un template dall'app con procedura guidata: carattere, colori, margini, logo, intestazione, piè di pagina, campi copertina | S |
| RF-56 | Più template per progetto (es. "Manuale", "Specifica"), uno predefinito | S |
| RF-57 | Anteprima di come appare il template prima dell'export (PDF della prima pagina) | C |

### Export e import

| ID | Requisito | Priorità |
| --- | --- | --- |
| RF-60 | Export DOCX nella lingua di destinazione, di una sezione, un capitolo o l'intero progetto | M |
| RF-61 | Tabelle, immagini, didascalie, note e sommario come elementi Word nativi | M |
| RF-62 | Numerazione di titoli, figure e tabelle secondo il template | S |
| RF-63 | Export PDF e ODT fedeli al template | S |
| RF-64 | Export nella lingua sorgente (stessa pipeline) e bilingue a due colonne | C |
| RF-65 | Import di un DOCX revisionato: confronto con l'ultimo export, revisioni di Word (tracked changes) incluse | S |
| RF-66 | Le modifiche importate sono mostrate all'autore **nella sua lingua** come proposte da accettare o rifiutare | S |
| RF-67 | Import di un DOCX esistente come nuovo progetto (conversione in capitoli/sezioni per titolo 1 e 2) | C |

### Installazione e avvio

| ID | Requisito | Priorità |
| --- | --- | --- |
| RF-70 | Avvio con **un solo comando**: doppio clic su `start.cmd` (Windows 10/11) o `./start.sh` (Linux, macOS) | M |
| RF-71 | Il primo avvio installa da solo ciò che manca, senza diritti di amministratore, nella cartella `.runtime/` del programma | M |
| RF-72 | Rilevamento dell'hardware (RAM, GPU) e scelta automatica del modello più adatto, modificabile dopo | M |
| RF-73 | Installazione di Ollama solo previa conferma dell'utente, se non già presente | M |
| RF-74 | Avanzamento chiaro durante il primo avvio (passi numerati, download con percentuale, tempo stimato) | M |
| RF-75 | Avvii successivi in meno di 10 secondi; apertura automatica del browser sulla porta libera trovata | M |
| RF-76 | Errori comprensibili con la soluzione suggerita (es. "Spazio su disco insufficiente: servono 6 GB") e log in `.runtime/logs` | M |
| RF-77 | Rispetto del proxy aziendale (`HTTPS_PROXY`) durante i download | S |
| RF-78 | Pacchetto **offline** per reti senza Internet: ZIP con dipendenze e modello inclusi | S |
| RF-79 | LibreOffice (per PDF/ODT) rilevato se presente; se assente, la UI disattiva PDF/ODT e spiega come aggiungerlo | S |

## Requisiti non funzionali

| ID | Requisito |
| --- | --- |
| RNF-01 | Funzionamento completo offline; nessun dato inviato a servizi esterni se non all'endpoint LLM configurato |
| RNF-02 | Uso desktop senza Docker tramite `start.sh`/`start.cmd`; Docker Compose come alternativa per installazioni su server |
| RNF-03 | Licenza Apache-2.0; dipendenze con licenze permissive (vedi AGENTS.md) |
| RNF-04 | L'editor non si blocca mai in attesa della traduzione; un paragrafo tradotto entro 3 s con un modello 4B su GPU consumer |
| RNF-05 | Backend LLM intercambiabile via API compatibile OpenAI; URL, modello e parametri configurabili dalla UI |
| RNF-06 | Traduzioni riproducibili: temperatura bassa e registrazione di modello e versione del prompt per ogni segmento |
| RNF-07 | Formati del workspace testuali e versionabili con Git |
| RNF-08 | Interfaccia in italiano e inglese; navigabile da tastiera; tema chiaro e scuro |
| RNF-09 | MVP monoutente (localhost); in fase Team: autenticazione OIDC, ruoli, più utenti sullo stesso server |
| RNF-10 | Progetti fino a 300 sezioni e 1.000 pagine esportate senza degrado percepibile dell'editor |
