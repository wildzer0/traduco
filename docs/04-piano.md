# 04 — Piano di sviluppo

Lavora in ordine. Ogni milestone termina quando **tutti** i criteri di accettazione sono coperti da test verdi.
Spunta i task (`- [x]`) nello stesso commit che li completa.

---

## M0 — Fondamenta

- [x] Struttura della repo come in `02-architettura.md`, licenza Apache-2.0
- [x] Backend: progetto uv, FastAPI con `/api/health`, configurazione con pydantic-settings, ruff + mypy + pytest
- [x] Frontend: Vite + React + TS strict, Tailwind, Biome, vitest, layout vuoto a tre colonne, i18n it/en, tema chiaro/scuro
- [x] `tools/fake-llm`: server OpenAI-compatibile (`/v1/chat/completions`, `/v1/models`) che restituisce
      `"[EN] " + testo`, preservando i segnaposto; modalità configurabili per simulare errori, lentezza, glossario violato
- [x] `Makefile` con `setup`, `dev`, `test`, `e2e`, `lint`, `licenses`
- [x] `docker-compose.yml`: servizio `app` (backend che serve il frontend buildato, Pandoc, LibreOffice),
      servizio `ollama` sotto profilo `llm` (build non ancora provata: Docker non disponibile nell'ambiente di sviluppo, la prova è nel job CI `docker`)
- [x] CI GitHub Actions: lint, test, build immagine, verifica licenze (workflow non ancora eseguito: serve il primo push)
- [x] `examples/progetto-esempio` con 2 capitoli, 5 sezioni, una tabella, un'immagine, un diagramma, glossario di 5 voci
- [x] `start.sh`, `start.cmd`, `launcher/bootstrap.ps1`: bootstrap uv in `.runtime/uv`, poi `python -m launcher`
      (`start.sh` provato su Linux da zero; `start.cmd`/`bootstrap.ps1` non ancora eseguiti su Windows: verifica demandata alla CI)
- [x] Launcher, prima versione: controlli preliminari, `uv sync`, build frontend con Node portabile, porta libera,
      avvio backend, attesa health, apertura browser, log, arresto pulito
- [x] `launcher/manifest.toml` con versioni e SHA-256; `downloads.py` con ripresa, retry, proxy, verifica hash
- [x] Job CI "avvio pulito" su Ubuntu e Windows (`tools/ci-clean-start.py`; provato in locale su Linux, Windows solo in CI)

**Accettazione**: `make setup && make test` verde su macchina pulita; su una VM Windows 11 e una Ubuntu senza nulla
installato, un doppio clic su `start.cmd` / `./start.sh` apre il browser sul layout vuoto senza chiedere privilegi;
il secondo avvio impiega meno di 10 s; il fake-llm risponde a una richiesta di prova.

## M1 — Workspace ed editor (RF-01…06, 10, 11, 15)

- [x] `core/workspace`: lettura/scrittura `progetto.yaml`, albero capitoli/sezioni, ordinamento per prefisso, titoli da front matter
- [x] Operazioni: crea, rinomina, sposta, riordina (rinumerazione atomica dei prefissi), elimina (nel cestino `.traduco/cestino`)
- [x] Upload immagini in `img/` del capitolo
- [x] API projects, nodes, files, assets con controllo conflitti via hash (`If-Match`)
- [x] File watcher: modifiche esterne notificate via WebSocket
- [x] Frontend: albero con drag & drop, barra strumenti, menu `/`, autosalvataggio, barra di stato
- [x] Forma canonica del Markdown (`canonical.ts`) e test di round-trip su tutte le fixture
- [x] Modalità Markdown (CodeMirror) e modalità Documento (Milkdown) sullo stesso file, interruttore `Ctrl+/`
- [x] Blocchi protetti per Markdown non rappresentabile in modalità Documento
- [x] Rendering Mermaid nel browser e salvataggio immagini in `.traduco/cache/`
- [x] Anteprima del sorgente renderizzato (markdown-it) con scorrimento sincronizzato

**Accettazione**: creare un progetto, 2 capitoli e 3 sezioni dalla UI produce la struttura su disco attesa;
riordinare via drag & drop rinumera i file; un'immagine incollata compare in `img/` e in anteprima; passare
10 volte da Documento a Markdown non cambia il file su disco; e2e verde.

## M2 — Motore di traduzione (RF-20…22, 28, 30)

- [x] `segmenter.py`: segmenti per tutti i tipi elencati in architettura, con chiavi e hash
- [x] `protect.py`: segnaposto per inline non traducibili e formattazione; ripristino con verifica
- [x] `assembler.py`: ricostruzione del Markdown tradotto; **test di proprietà** (hypothesis) identità → stesso HTML
- [x] Riconciliazione segmenti dopo modifica (hash, poi posizione)
- [x] `llm_client.py` OpenAI-compatibile con timeout, retry, annullamento
- [x] `store.py`: file JSON dei segmenti, scrittura atomica, chiavi ordinate
- [x] Coda con priorità e annullamento delle richieste superate
- [x] Prompt `translate@1` con tono, contesto, segmento precedente
- [x] Eventi WebSocket `segment.*`, `llm.status`
- [x] Frontend: anteprima tradotta, stato per segmento, indicatore modello, banner modello offline
- [x] Ritraduzione di sezione/capitolo/progetto

**Accettazione**: scrivendo un paragrafo, l'anteprima mostra la traduzione (fake-llm) entro 1 s dal debounce;
modificare un paragrafo ritraduce solo quello; codice, URL e `{{campi}}` restano identici; spegnendo il
fake-llm l'editor continua a funzionare e la traduzione riprende alla riaccensione.

## M2b — Scheletro di progetto (RF-09)

- [x] Formato `scheletro.yaml` (modello pydantic, validazione, esempio ECSS-E-ST-10-06C abbreviato in `examples/scheletri/`)
- [x] `core/skeleton`: generazione di capitoli/sezioni (con titolo e testo guida) da uno scheletro; scheletro salvato nel progetto
- [x] Verifica di conformità: mancanti, extra, fuori ordine, obbligatorie vuote; API `GET /projects/{id}/skeleton/check`
- [x] UI: "Nuovo progetto da scheletro", indicatore di conformità nell'albero (sezioni mancanti segnate)

**Accettazione**: creare un progetto da uno scheletro produce la struttura su disco attesa; eliminare una sezione
obbligatoria la segnala come mancante; un file di scheletro non valido dà un errore con riga e motivo.

## M3 — Controllo della traduzione e glossario (RF-23…27, 40…43)

- [x] Modifica manuale in linea → `manual` + `locked`
- [x] Sorgente cambiato su segmento bloccato → `needs_review` + `pending_target`, UI Accetta/Ignora
- [x] Tono per progetto e per sezione; cambio tono → ritraduzione dei soli segmenti non bloccati
- [x] Istruzione su segmento con conferma; suggerimenti rapidi; alternative (3 varianti)
- [x] `glossario.yaml`: lettura/scrittura, pannello UI, aggiunta dal menu contestuale
- [x] `glossary_check.py`: imposti, vietati, non_tradurre; secondo tentativo correttivo; motivo in `needs_review`
- [x] Voci di glossario pertinenti inserite nel prompt
- [x] Modalità Revisione con filtri e approvazione; `F8` al successivo da rivedere
- [x] Modifica diretta in anteprima → proposta di aggiornamento del sorgente (Applica/Ignora), stato `diverged`

**Accettazione**: con il fake-llm in modalità "viola glossario" il segmento finisce in `needs_review` con motivo;
una correzione manuale sopravvive a ritraduzione di progetto e cambio di tono; e2e del flusso modifica → blocco →
modifica sorgente → proposta.

## M3b — Companion di scrittura (RF-87…89)

Dopo M3: riusa la coda, la protezione dei segnaposto, il glossario e l'interfaccia Accetta/Ignora della M3.

- [x] Prompt `improve@1` (correggi, riformula, conciso, semplice, tono) e `check@1` con validazione dei segnaposto e della lunghezza
- [x] Endpoint `POST /projects/{id}/assist` (azione, segmento o selezione) e `POST …/check` (sezione); priorità 1 nella coda, nessun salvataggio automatico
- [x] Interfaccia: menu sulla selezione e sul segmento, diff per parola, Accetta/Ignora/Rigenera, scorciatoie
- [x] Controllo della sezione: pannello dei suggerimenti ancorati ai segmenti (condivide il modello dei commenti di RF-83)
- [x] La guida dello scheletro (RF-09) e il glossario entrano nel prompt; regole per i requisiti (RF-84)
- [x] Accettare un suggerimento modifica il sorgente e ritraduce solo quel segmento (nessun ciclo)

**Accettazione**: un suggerimento non cambia il file finché non è accettato; i segnaposto (codice, link, `{{campi}}`) restano intatti;
accettare ritraduce un solo segmento; con il modello spento le azioni sono disattivate con un messaggio e l'editor non si blocca.

## M4 — Template ed export DOCX (RF-50…53, 56, 60…62)

- [x] `analyze.py`: stili per styleId e nome, segnaposto anche spezzati in run, intestazioni/piè/caselle di testo
- [x] Proposta automatica di mappatura stili; `template/<nome>.yaml`
- [x] UI caricamento template, schermata di analisi e mappatura, template predefinito
- [x] `combine.py`: unione sezioni nell'ordine, riscrittura percorsi immagini e link interni
- [x] `pandoc.py`; stili e didascalie applicati in Python sul DOCX di Pandoc (invece del filtro Lua, vedi ADR-036)
- [x] `compose.py`: compilazione campi, inserimento corpo a `{{CONTENUTO}}`, `updateFields`
- [x] Diagrammi Mermaid → PNG con cache
- [x] Export di sezione/capitolo/progetto, job con avanzamento e download
- [x] Snapshot dell'export in `.traduco/export/`
- [x] Fixture: un template aziendale realistico (copertina con logo, intestazione con codice documento, stili con
      nomi italiani, tabella con stile personalizzato)

**Accettazione** (test con python-docx sul file prodotto): nessun `{{…}}` residuo; copertina e intestazioni del
template presenti; titoli con gli stili mappati; tabelle con lo stile tabella mappato; immagini e didascalie
presenti; il file si apre senza errori in LibreOffice (conversione a PDF riuscita).

## M4b — Launcher completo (RF-70…79)

- [x] `hardware.py`: RAM, GPU (NVIDIA, AMD, Apple Silicon) e scelta del modello dalla tabella in architettura
- [x] `ollama.py`: rilevamento, installazione su conferma (winget / script ufficiale / app macOS), pull con avanzamento
- [x] Pandoc portabile per Windows x64, Linux x64/arm64, macOS
- [x] Rilevamento LibreOffice e flag di capacità esposto al frontend (`/api/capabilities`)
- [x] Opzioni `--update`, `--model`, `--port`, `--no-browser`, `--offline`, `--reset`, `--workspace`
- [x] Messaggi di errore con codice e soluzione, in italiano e inglese
- [x] `make bundle-offline` per Windows e Linux
- [x] Schermata di benvenuto e stato "modello in download" nella UI

**Accettazione**: su VM pulite Windows 11 e Ubuntu 24.04 il primo avvio installa tutto e traduce un paragrafo
dell'esempio con il modello reale; con la rete scollegata il pacchetto offline parte e traduce; rifiutando
l'installazione di Ollama l'app parte e spiega come configurare un endpoint.

## M5 — PDF/ODT, revisioni, wizard template (RF-54, 55, 63, 65, 66)

- [x] `office.py`: PDF e ODT via LibreOffice headless con aggiornamento campi
- [x] Tabella revisioni da `progetto.yaml`
- [x] Procedura guidata di creazione template in 4 passi
- [x] Import DOCX: lettura diretta dell'XML con tracked changes (ADR-038), rimozione parti del template, allineamento con snapshot
- [x] Retro-traduzione delle modifiche e schermata proposte (Accetta/Rifiuta/Modifica)
- [x] Fixture: DOCX revisionato con modifiche dirette e revisioni Word

**Accettazione**: un DOCX esportato, modificato in 3 punti (anche con revisioni attive) e reimportato produce
esattamente 3 proposte nella sezione corretta, nella lingua sorgente; accettarle aggiorna sorgente e traduzione
bloccata.

## M5b — Emissioni, confronto e commenti di revisione (RF-80…83)

- [x] Emissioni: snapshot congelati in `.traduco/emissioni/`, storico, ripristino di una sezione da un'emissione (RF-80)
- [x] Confronto visuale per parola, sorgente e tradotto, con navigazione cambio per cambio (RF-82)
- [x] Tabella dei cambiamenti generata dal modello dal confronto, modificabile, in `{{REVISIONI}}` (RF-81)
- [x] Commenti di revisione per segmento con thread e stato (RF-83)

**Accettazione**: due emissioni consecutive producono una tabella dei cambiamenti con una riga per sezione modificata;
un commento resta ancorato al suo segmento dopo modifiche del testo vicino.

## M5c — Documentazione software, altri formati, snippet (RF-84…86)

- [x] Modelli di scheletro ADD/DDD/SRS e controllo dei riferimenti tra requisiti (RF-84)
- [x] Export HTML statico, Markdown unico, EPUB (RF-85)
- [x] Snippet con alias, tab-stop e contatori nel menu `/` e in `snippet.yaml` (RF-86)

**Accettazione**: l'export HTML si apre da `file://` senza server; uno snippet con contatore inserisce `FOO-REQ-00042` e
al secondo inserimento `…00043`, anche dopo il riavvio.

## M6 — Qualità e rifinitura (RF-07, 12, 13, 16, 29, 44, 57, 64)

- [ ] Lingue aggiuntive (RF-21b…e): cartelle segmenti per lingua, coda a bassa priorità, tono/glossario/formati per
      lingua, opzione pivot sulla lingua ufficiale approvata, percentuali nel selettore lingua
- [ ] Memoria di traduzione SQLite: esatte e simili, export/import TMX
- [ ] Riferimenti incrociati tra sezioni risolti in export
- [ ] Editor visuale tabelle
- [ ] LanguageTool opzionale (servizio Docker facoltativo)
- [ ] Palette comandi completa, `?` con scorciatoie, ricerca nel progetto
- [ ] Export bilingue a due colonne
- [ ] Test di prestazioni: progetto con 300 sezioni generate
- [ ] Guida utente in `docs/guida-utente.md`

**Accettazione**: requisiti S elencati coperti da test; progetto da 300 sezioni apre l'albero in < 1 s e l'editor
resta fluido.

## M7 — Team (fase successiva, RNF-09)

- [ ] Astrazioni `Store` e `JobQueue` con implementazioni PostgreSQL e Valkey
- [ ] Autenticazione OIDC (Keycloak in compose), ruoli: autore, revisore, amministratore
- [ ] Blocco di una sezione mentre un utente la modifica; presenza degli utenti
- [ ] Log di audit su approvazioni ed export
- [ ] Profilo compose `team` con vLLM

**Accettazione**: due utenti sullo stesso progetto non sovrascrivono il lavoro l'uno dell'altro; ogni
approvazione riporta l'autore nel log.
