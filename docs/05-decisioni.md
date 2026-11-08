# 05 — Decisioni (ADR) e domande aperte

Formato: contesto · decisione · conseguenze. Aggiungi nuovi ADR in coda con numero progressivo.

## ADR-001 — Il file system è il database dei documenti
**Contesto**: l'utente vuole documenti come cartelle (capitoli) e file `.md` (sezioni).
**Decisione**: il progetto è una cartella; nessun database contiene il testo dei documenti. Le traduzioni sono file
JSON accanto, in `.traduco/`.
**Conseguenze**: versionabile con Git, modificabile anche fuori dall'app, nessun lock-in. Serve un file watcher e la
gestione dei conflitti.

## ADR-002 — Editor a due modalità sullo stesso Markdown (aggiornato 2026-11-07)
**Contesto**: servono sia chi non conosce il Markdown sia chi lo usa; il sorgente deve restare Markdown pulito.
**Decisione**: modalità Documento (Milkdown, nativo Markdown) e modalità Markdown (CodeMirror 6) sullo stesso file;
salvataggio sempre in forma canonica; anteprima tradotta renderizzata e modificabile per segmento.
**Conseguenze**: round-trip da testare con cura su ogni elemento; i costrutti non supportati dalla modalità
Documento diventano blocchi protetti, mai persi.

## ADR-003 — Monoutente con SQLite e coda in-process per l'MVP
**Contesto**: ridurre la complessità iniziale.
**Decisione**: un processo, SQLite, coda asyncio. Interfacce `Store` e `JobQueue` astratte.
**Conseguenze**: installazione semplice; il passaggio a Team (M7) richiede nuove implementazioni, non riscritture.

## ADR-004 — Template: stili via Pandoc, struttura via composizione
**Contesto**: il `--reference-doc` di Pandoc importa solo gli stili, non copertina né contenuti del template.
**Decisione**: Pandoc genera il corpo con gli stili del template; python-docx + docxcompose compilano i campi e
inseriscono il corpo al segnaposto `{{CONTENUTO}}` del template originale.
**Conseguenze**: i template aziendali vanno preparati con i segnaposto (la UI aiuta). Gli stili si mappano per
`styleId` perché i nomi sono localizzati.

## ADR-005 — PDF e ODT tramite LibreOffice dal DOCX finale
**Contesto**: il PDF deve rispettare il template Word.
**Decisione**: LibreOffice headless converte il DOCX composto. (Sostituisce l'idea iniziale di Typst.)
**Conseguenze**: immagine Docker più grande (~500 MB); fedeltà alta ma non perfetta rispetto a Word.

## ADR-006 — Traduzione per segmento con segnaposto
**Contesto**: i modelli piccoli rovinano Markdown e codice se ricevono il documento intero.
**Decisione**: si traduce un segmento alla volta; inline non traducibili protetti da segnaposto `⟦n⟧` e verificati.
**Conseguenze**: struttura sempre preservata; contesto limitato, compensato da titolo, segmento precedente e note.

## ADR-007 — Modello di riferimento Gemma 4 E4B, backend intercambiabile
**Contesto**: serve un modello piccolo, locale, con licenza commerciale libera.
**Decisione**: default Gemma 4 E4B (Apache-2.0) su Ollama; qualsiasi endpoint OpenAI-compatibile è accettato.
TranslateGemma è supportato ma documentato come soggetto ai Gemma Terms of Use.
**Conseguenze**: nessuna dipendenza dal fornitore; i prompt devono funzionare anche con modelli diversi (test con fake-llm).

## ADR-008 — Pandoc e LibreOffice come processi esterni
**Contesto**: sono GPL/MPL, il progetto è Apache-2.0.
**Decisione**: invocati solo come eseguibili, mai linkati.
**Conseguenze**: compatibilità di licenza; da confermare con un parere legale prima del rilascio pubblico.

## ADR-009 — Lingua ufficiale più lingue aggiuntive, tradotte dal sorgente
**Contesto**: di solito la destinazione è solo l'inglese, ma altre lingue sono utili.
**Decisione**: una lingua ufficiale tradotta in tempo reale; lingue aggiuntive facoltative tradotte **dal sorgente**
in background, con tono, glossario e formati propri. Pivot sulla lingua ufficiale approvata solo come opzione per lingua.
**Conseguenze**: nessun accumulo di errori da traduzione di traduzione; più carico sul modello, gestito dalla coda a
bassa priorità. Realizzazione in M6: l'MVP resta su una lingua, ma la struttura dati è già per lingua.

## ADR-010 — Modifica diretta della traduzione con riallineamento proposto
**Contesto**: chi conosce bene l'inglese vuole poter scrivere direttamente nella lingua ufficiale.
**Decisione**: si scrive nell'anteprima; il segmento diventa manuale e bloccato; il sistema propone la
retro-traduzione per aggiornare il sorgente (Applica/Ignora); se ignorata il segmento è `diverged`.
**Conseguenze**: il sorgente resta la verità ma l'autore non è costretto a passare dall'italiano; le divergenze sono
sempre visibili e filtrabili in Revisione.

## ADR-011 — Avvio con un comando tramite launcher nativo, non Docker
**Contesto**: l'utente non deve pensare a nulla, su Windows e Linux; Docker Desktop richiede privilegi e, nelle
aziende grandi, licenza.
**Decisione**: `start.cmd`/`start.sh` come bootstrap sottili che installano uv; un launcher Python unico gestisce
dipendenze, Pandoc e Node portabili, scelta del modello, Ollama e avvio. Tutto in `.runtime/`, senza privilegi.
Docker Compose resta per i server. Pacchetto offline per reti isolate.
**Conseguenze**: manutenzione di `manifest.toml` (versioni e hash) e test di avvio pulito in CI su due sistemi.

## ADR-012 — Diagrammi resi nel browser
**Contesto**: mermaid-cli richiede Node e Chromium a runtime, troppo pesanti per il launcher.
**Decisione**: mermaid.js nel frontend; immagini salvate in cache dal backend e riusate all'export. (Sostituisce mermaid-cli.)
**Conseguenze**: nessun browser headless da installare; un diagramma mai aperto nell'editor non ha immagine e va
aperto prima dell'export (caso raro, segnalato).

---

## Domande chiuse

| # | Domanda | Decisione |
| --- | --- | --- |
| Q1 | Editor WYSIWYG o Markdown? | Entrambi, sullo stesso file (ADR-002) |
| Q2 | Una o più lingue di destinazione? | Ufficiale + aggiuntive dal sorgente (ADR-009) |
| Q3 | Si può scrivere direttamente nella lingua di destinazione? | Sì, con riallineamento proposto (ADR-010) |
| Q4 | Collaborazione in tempo reale? | No nelle prime fasi; ciclo export/import, eventualmente in M7 |

## Domande aperte

| # | Domanda | Proposta di default | Stato |
| --- | --- | --- | --- |
| Q5 | Quali documenti e template reali usare come banco di prova? | Fixture inventate in M4, sostituite da quelle reali quando disponibili | rimandata |
| Q6 | Nome definitivo del prodotto | "Traduco" provvisorio | rimandata |
| Q7 | Avvio pulito su Windows 11 (`start.cmd`, `bootstrap.ps1`, passaggio di `--opzioni` a PowerShell, Ctrl+C in `cmd`) | Verificare con il job CI `clean-start (windows-latest)` e a mano su una VM | chiusa il 2026-11-07: CI verde su `windows-latest` (avvio da zero, riavvio < 10 s, opzioni passate). Non provato: doppio clic da Esplora risorse e Ctrl+C in `cmd` |
| Q8 | Tag Ollama dei modelli Gemma 4 in `manifest.toml` (`gemma4:e2b`, `e4b`, `26b-a4b`) | Da verificare sulla libreria Ollama prima di M4b | chiusa il 2026-11-07: i tre tag esistono nella libreria Ollama; `e4b` provato dal vivo (6,6 GB, GPU 8 GB). `e2b` e `26b-a4b` non scaricati né provati |
| Q9 | Build dell'immagine Docker (Pandoc, LibreOffice 25 su Debian 13) mai eseguita in locale | Verificare con il job CI `docker` | chiusa il 2026-11-07: job `docker` verde (build, avvio, Pandoc e LibreOffice presenti) |
| Q10 | Fissare le GitHub Actions per SHA e verificare pnpm (corepack) per hash | Prima del rilascio pubblico | rimandata |
| Q11 | Parere legale su licenze (ADR-008, ADR-013, ADR-019) | Prima del rilascio pubblico | rimandata |

## ADR-013 — Font OFL ammessi come asset
**Contesto**: `03-ui.md` impone Inter e IBM Plex Mono, licenza OFL-1.1, che non è nell'elenco di AGENTS.md.
**Decisione**: OFL-1.1 è ammessa **solo per i file font** inclusi nel build (pacchetti `@fontsource/*`), non per librerie di codice.
`tools/check-licenses.py` ha un'eccezione esplicita limitata a questi pacchetti.
**Conseguenze**: nessun CDN; la licenza OFL va riportata in `NOTICE`/documentazione di terze parti al rilascio.

## ADR-014 — Il launcher non è "codice di runtime"
**Contesto**: la regola 1 vieta chiamate di rete esterne a runtime, ma il launcher deve scaricare uv, Node, Pandoc, modelli.
**Decisione**: il launcher è tooling di installazione, vincolato da checksum SHA-256 e `--offline`; l'app (backend e frontend) non
contatta mai la rete esterna.
**Conseguenze**: i download sono confinati in `launcher/` e `downloads.py`; un test impedisce import di client HTTP di rete nel backend.

## ADR-015 — Versioni toolchain fissate in M0
**Decisione**: Python 3.12, Node 24 LTS, pnpm via corepack (`packageManager`), uv fissato nel bootstrap, Pandoc 3.13 (solo nel
manifest in M0, installato dal launcher in M4b). Dipendenze con lockfile (`uv.lock`, `pnpm-lock.yaml`).
Dipendenze UI (Radix, cmdk, lucide, dnd-kit, CodeMirror, Milkdown) aggiunte dalla milestone che le usa.
**Conseguenze**: aggiornamenti di versione = nuovo ADR o nota nel changelog.

## ADR-016 — Fake LLM con sola libreria standard
**Decisione**: `tools/fake-llm` usa `http.server` (zero dipendenze) così il launcher e la CI lo avviano senza installare nulla.
Modalità via `FAKE_LLM_MODE` (`ok|error|slow|glossary-violation`) e override per richiesta con l'header `X-Fake-Mode`.

## ADR-017 — Versioning e rilasci
**Decisione**: SemVer 0.x; tag annotato `vX.Y.0` a ogni milestone completata (M0 = v0.1.0, M1 = v0.2.0, …), voce in
`CHANGELOG.md`. Lavoro su `main`, Conventional Commits in inglese. Il push (anche dei tag) avviene solo su conferma del committente.

## ADR-018 — Frontend M0: scelte minime
**Contesto**: il layout vuoto deve comunque permettere di verificare i18n it/en e tema chiaro/scuro.
**Decisione**: i18n con un piccolo modulo proprio (`lib/i18n.ts`, chiavi piatte nei JSON, test di parità it/en) invece di una libreria;
preferenze (tema, lingua) in Zustand con persistenza `localStorage` tollerante agli errori; un drawer Impostazioni minimale
(lingua dell'interfaccia e tema, come da `03-ui.md`); Glossario e Template nella barra laterale sono disabilitati fino a M3/M4.
`pnpm` 12 genera `pnpm-workspace.yaml` con `minimumReleaseAgeExclude`: è versionato così com'è. Biome 2.6 usa `preset` al posto di `recommended`.
`make e2e` costruisce il frontend e lo serve dal backend (stesso percorso dell'avvio utente).
**Conseguenze**: nessuna dipendenza i18n o UI in più; il drawer verrà esteso, non sostituito, dalle milestone successive.

## ADR-019 — Licenze permissive equivalenti ammesse
**Contesto**: `typing_extensions` (PSF-2.0, richiesta da pydantic a runtime), `isbot` (Unlicense) e `lru-cache` (BlueOak-1.0.0, strumenti di
test) non sono nell'elenco di AGENTS.md pur essendo permissive.
**Decisione**: si aggiungono PSF-2.0, 0BSD, Unlicense, BlueOak-1.0.0, CC0-1.0, Python-2.0. Copyleft (GPL, LGPL, AGPL) resta vietato come dipendenza.
`tools/check-licenses.py` controlla Python e frontend; per espressioni `A OR B` basta una alternativa ammessa.
**Conseguenze**: da confermare insieme al parere legale previsto da ADR-008 prima del rilascio pubblico.

## ADR-020 — Launcher M0: scelte implementative
**Contesto**: `02-architettura.md` descrive il launcher a livello di passi; servono dettagli per renderlo robusto.
**Decisione**:
- Moduli aggiuntivi rispetto all'albero in architettura: `paths.py`, `manifest.py`, `state.py`, `proc.py`, `run.py`
  (`hardware.py`, `ollama.py`, `office.py` arrivano con M4b). I passi sono 5 in M0: controlli, dipendenze backend, Node, frontend, avvio.
- Tutto ciò che il launcher scarica sta in `.runtime/`, inclusa la cache di uv (`.runtime/uv-cache`) e Python (`.runtime/python`).
  Se `uv` è già nel PATH e `.runtime/uv` manca, il bootstrap lo riusa invece di scaricarlo.
- Il backend ha un proprio venv (`backend/.venv`, `UV_PROJECT_ENVIRONMENT` esplicito) e si installa con `uv sync --frozen --no-dev --inexact`,
  così non rimuove i pacchetti di sviluppo in una copia di lavoro.
- Il frontend si ricostruisce se i sorgenti cambiano (hash in `.runtime/state.json`); se mancano i sorgenti (pacchetto di rilascio) si usa `dist`.
  `--update` forza sync e rebuild. `--reset` cancella Node, download, cache corepack, `dist`, `node_modules`, `backend/.venv` e lo stato;
  non tocca uv, Python e il venv del launcher (sono in uso) né i progetti.
- pnpm è scaricato da corepack (registro npm) e non è fissato per hash dal manifest; Node sì.
- La verifica `/api/health` ignora i proxy (richiesta su loopback). Il probe della porta usa `SO_REUSEADDR` su POSIX come uvicorn.
- SIGTERM e Ctrl+Break sono trattati come Ctrl+C: il backend viene sempre fermato.
**Conseguenze**: i comportamenti su Windows (`start.cmd`, `bootstrap.ps1`, Ctrl+C in `cmd`) sono non verificati finché non gira il job CI su `windows-latest`.

## ADR-021 — Immagine Docker su Debian 13 con Pandoc scaricato
**Contesto**: LibreOffice >= 24 (RF-79) e Pandoc >= 3.5 non sono nei repository di Debian 12; Debian 13 ha LibreOffice 25.x ma non Pandoc 3.5+.
**Decisione**: base `python:3.12-slim-trixie`; LibreOffice (`libreoffice-writer-nogui`) da apt; Pandoc scaricato dalle release ufficiali con SHA-256
(stessa versione e hash di `launcher/manifest.toml`, verificati da `launcher/tests/test_consistency.py`). Build multi-stage del frontend con Node 24.
Il compose non fissa l'immagine Ollama (`OLLAMA_IMAGE`, predefinita `latest`).
**Conseguenze**: l'immagine non è stata costruita in locale (Docker assente): la prima verifica reale è il job CI `docker`.
La CI usa tag maggiori delle action (`@v4`, `@v6`), non SHA: da fissare prima del rilascio pubblico.

## ADR-022 — Front matter con parser proprio su ruamel.yaml
**Contesto**: `02-architettura.md` indica `python-frontmatter`, ma serve conservare il corpo byte per byte, commenti e ordine delle chiavi,
e il pacchetto `app.core` è sotto `mypy --strict`.
**Decisione**: `core/workspace/frontmatter.py` (circa 60 righe) usa ruamel.yaml in modalità round-trip; `python-frontmatter` non è una dipendenza.
`progetto.yaml` conserva le chiavi sconosciute (`extra="allow"`) ma, essendo riscritto dal modello, può perdere i commenti YAML.
**Conseguenze**: nessun commento perso nel front matter delle sezioni; nei `progetto.yaml` modificati dall'app i commenti non sono garantiti.

## ADR-023 — API M1: forma delle richieste
**Decisione**: id progetto = nome della cartella in `~/Traduco` (solo `[A-Za-z0-9._-]`; le cartelle con altri nomi non sono elencate).
`PATCH /nodes` esegue una sola operazione: rinomina (`path`+`title`), sposta (`path`+`move:true`+`parent`[+`index`]) o riordina (`parent`+`order`).
`PUT /files` richiede `If-Match` con l'hash restituito da `GET` (428 se assente, 409 `conflict` con `details.current_hash` se non coincide).
`POST /assets` riceve i byte grezzi dell'immagine (`?section=&filename=`) invece di multipart, evitando una dipendenza; `GET /assets` serve solo
immagini sotto `img/` con `Content-Security-Policy: sandbox` e `nosniff`. Il tipo è dedotto dal contenuto; SVG con script è rifiutato.
Il cestino sta in `.traduco/cestino/<timestamp>/<percorso originale>` ed è nel `.gitignore` del progetto.
**Conseguenze**: "Apri cartella esistente" (schermata di benvenuto, `03-ui.md`) richiede un registro di cartelle esterne a `~/Traduco`: non previsto in M1.

## ADR-024 — Eventi di file: watchfiles, hash negli eventi, controllo Origin
**Decisione**: un watcher `watchfiles` per progetto (avviato al primo client WebSocket, fermato all'ultimo), debounce 300 ms, che emette
`file.changed` / `project.changed` / `glossary.changed` con `path`, `change` (`added|modified|deleted`) e, per i `.md`, l'`hash` attuale:
il client ignora gli eventi con l'hash dei propri salvataggi. File nascosti, temporanei (scritture atomiche, rinumerazione) e `build/` non generano eventi.
Il WebSocket rifiuta le connessioni il cui `Origin` non coincide con l'`Host` (i browser non applicano la same-origin policy ai WebSocket).
**Conseguenze**: su WSL e unità di rete `watchfiles` passa al polling e può perdere una modifica fatta nel primo secondo dopo la connessione:
il client deve rileggere albero e file aperto a ogni (ri)connessione. I test ripetono la modifica finché l'evento arriva.

## ADR-025 — Mermaid 11.13 invece della serie 12
**Contesto**: `mermaid` 12.x dipende da `elkjs`, con licenza `EPL-2.0 OR GPL-3.0-or-later`, non ammessa da AGENTS.md. La serie 11.x non la include.
**Decisione**: si fissa `mermaid@11.13.0`. `khroma` (dipendenza di mermaid) ha licenza MIT nel repository ma non nel `package.json`: è ammesso con un override
esplicito in `tools/check-licenses.py`.
**Conseguenze**: nessuna funzione di layout ELK (non usata). Passare a mermaid 12 richiede una decisione sull'EPL-2.0 (licenza copyleft debole, simile alla MPL-2.0).

## ADR-026 — Editor M1: scelte implementative
**Decisione**:
- **Salvataggio**: `Autosaver` (debounce 1 s, un salvataggio alla volta, `If-Match` con l'hash noto). Il testo scritto su disco è sempre normalizzato con
  `canonicalize()`; la vista CodeMirror non viene riscritta mentre l'utente digita. Il file è salvato anche al blur dell'editor, al cambio sezione e a `pagehide`.
- **Modalità**: Markdown mostra l'intero file, front matter compreso; Documento mostra solo il corpo e conserva il front matter. Il cambio di modalità
  salva in forma canonica e riporta il cursore al blocco di primo livello corrispondente (markdown-it per la mappa delle righe).
- **Eventi esterni**: modifica di un file aperto senza testo non salvato → ricarica silenziosa; con testo non salvato (o 409 al salvataggio) → avviso
  "Ricarica / Mantieni la mia versione". Albero e file aperto vengono riletti a ogni (ri)connessione del WebSocket e quando la finestra riprende il focus.
- **Pulsanti della barra strumenti** non prendono il focus (`mousedown` annullato), così selezione e tastiera restano nell'editor.
- **Menu `/`**: voci Titolo 1/2/3, Elenco, Tabella, Immagine, Diagramma, Nota, Citazione, Codice, Interruzione (il documento UI dice "Titolo": qui sono tre livelli).
- L'albero è una lista di pulsanti, non un `role="tree"` ARIA, finché non esiste la navigazione a frecce.
- Le immagini relative (`img/x.png`) sono riscritte nel DOM verso `/api/projects/{id}/assets` senza toccare il Markdown.
**Dipendenza richiesta da uvicorn**: `websockets`. Senza, i WebSocket rispondono 404 nel server reale (il `TestClient` non lo rivela): c'è un test contro un server vero.

## ADR-027 — Anteprima, diagrammi e blocchi protetti in M1
**Decisione**:
- **Anteprima** (colonna destra, "Anteprima · sorgente"): markdown-it con HTML grezzo **disattivato** (escape) e link validati, perché le sezioni possono
  arrivare da repository non fidati; footnote con `markdown-it-footnote`. Ogni blocco di primo livello ha `data-block` con lo stesso indice che l'editor calcola,
  così lo scorrimento dell'editor allinea l'anteprima (da editor a anteprima, non viceversa). Si aggiorna 120 ms dopo l'ultima modifica, senza attendere il salvataggio.
- **Mermaid**: reso nel browser (caricato solo se serve). Etichette in puro testo SVG (`htmlLabels: false`) così l'SVG è rasterizzabile senza `foreignObject`.
  A sezione salvata il browser carica SVG + PNG 2× (tema chiaro) in `PUT /api/projects/{id}/diagrams/{sha256}`, salvati in `.traduco/cache/diagrams/`; hash = SHA-256 del
  codice così come scritto (compreso l'a capo finale). Il server rifiuta SVG con script e PNG non validi. La cache è nel `.gitignore` del progetto.
- **Blocchi protetti**: Milkdown conserva HTML grezzo, commenti, direttive `:::` e tag `{% %}` e li mostra come testo sorgente (`span[data-type=html]`, stile tratteggiato);
  il round-trip non perde nulla (fixture `protected`). La sintassi sconosciuta non-HTML è un paragrafo di testo: non c'è un blocco "Markdown" dedicato.
- I diagrammi non hanno una vista affiancata *nell'editor* (solo nell'anteprima): il codice Mermaid è un normale blocco di codice in entrambe le modalità.
**Conseguenze**: tradurre le etichette dei diagrammi (`diagram_label`) e l'export dei PNG sono compiti di M2/M4.

## ADR-028 — Scheletro di progetto da file di configurazione (RF-09)
**Contesto**: molti documenti devono rispettare una struttura prescritta (es. ECSS: capitoli e paragrafi obbligatori).
**Decisione**: un file YAML `scheletro.yaml` (nella radice del progetto, copiabile e condivisibile) descrive l'albero atteso:
ogni nodo ha `id` stabile, `titolo` (nelle lingue del progetto), `obbligatorio`, `guida` (testo di aiuto, inserito come
commento non esportato nella sezione) e figli. La creazione del progetto genera cartelle e file con i prefissi numerici; la
conformità si verifica per `id` memorizzato nel front matter (`scheletro: <id>`), quindi resta valida se l'utente rinomina o
riordina. L'app non impedisce di deviare dallo scheletro: segnala soltanto. Realizzata in M2b, dopo il motore di traduzione,
perché non dipende dal modello.
**Conseguenze**: il workspace guadagna un campo di front matter facoltativo e un file facoltativo, senza rompere il formato esistente.

## ADR-029 — Motore di traduzione M2: scelte implementative
**Decisione**:
- **Segmentazione** con `markdown-it-py` (+ `mdit-py-plugins`, note a piè di pagina). Ogni segmento ricorda le righe del file, il prefisso del contenitore (`- `, `> `, `[^1]: `) per riga e il suffisso;
  l'assemblaggio riscrive solo quelle righe, quindi tutto il resto del file resta identico byte per byte. Le celle di tabella sono localizzate per (riga, colonna) e il `|` nel testo tradotto viene riscritto come `\|`.
  Chiavi: `h:n`, `p:n`, `li:n`, `q:n`, `fn:n`, `th:t:c`, `td:t:r:c`, `fm:title`; il contatore avanza anche per i segmenti scartati, il frontend ricalcola le stesse chiavi per marcare lo stato sull'anteprima.
- **Segnaposto**: `⟦n⟧` per gli atomi; coppie `⟦n⟧testo⟦/n⟧` con numerazione unica per link, immagini (il testo e l'alt si traducono, l'URL no), grassetto, corsivo, barrato. Sostituisce la sigla `⟦b⟧` del documento di architettura.
  Controllo: ognuno presente una volta, coppie annidate, nessun identificativo inventato; altrimenti un secondo tentativo con istruzione correttiva, poi `needs_review` con il motivo.
- **Riconciliazione**: prima per hash (stesso codice, poi più vicino), poi per posizione solo tra segmenti dello stesso tipo, senza `difflib` (l'ordine basta e non introduce accoppiamenti spuri).
- **Coda**: `asyncio`, 2 lavoratori, priorità 1 modifica · 2 visibili · 3 resto del file · 4 massa. Un nuovo invio con lo stesso id sostituisce il precedente e annulla la richiesta in volo. Se il modello non risponde la coda si ferma, un monitor interroga `/models` ogni 3 s e la riavvia.
- **Traduzione avviata dal salvataggio** (`PUT /files`) e, se il file non ha ancora segmenti aggiornati, dalla lettura di `GET /translation`. Lo store è `.traduco/segmenti/<lingua>/<percorso>.json` con chiavi ordinate; un file illeggibile vale come assente.
- **Segmento bloccato** (già gestito dal motore, l'interfaccia è M3): se il sorgente cambia mantiene il testo e riceve `pending_target` con stato `needs_review`.
- **Anteprima**: due modalità (traduzione predefinita, sorgente con `Ctrl+Shift+P`). La traduzione mostrata è quella assemblata dal server; i segmenti non ancora pronti mostrano il sorgente con bordo animato.
- **e2e**: i test avviano da soli il fake-llm sulla porta 11500 per poterlo spegnere.
**Limiti noti**: validazione di glossario e memoria di traduzione sono M3/M6; una sola lingua (la ufficiale); la modifica non salvata non è tradotta (si traduce al salvataggio, dopo 1 s di pausa).

## ADR-030 — Il companion di scrittura è assistenza esplicita, mai automatica
**Contesto**: l'utente vuole che il modello consigli miglioramenti e correzioni oltre a tradurre.
**Decisione**:
- Stesso motore della traduzione (client, coda, segnaposto, glossario), nuovi prompt versionati `improve@n` e `check@n`; le richieste interattive hanno priorità 1 e passano davanti alla traduzione.
- Nessun suggerimento non richiesto e nessuna applicazione automatica: ogni proposta è una differenza che l'utente accetta, ignora o rigenera. I suggerimenti non sono scritti nei file del progetto finché non sono accettati;
  il controllo di sezione salva solo l'elenco in `.traduco/cache/` (in `.gitignore`).
- Accettare modifica il **sorgente**, quindi segue il normale percorso: salvataggio, riconciliazione, ritraduzione del solo segmento.
- Il testo va solo all'endpoint configurato; se non è locale la UI lo mostra in Impostazioni.
**Conseguenze**: carico sul modello unico (2 richieste in parallelo): le azioni dell'utente rallentano la traduzione in coda, non il contrario. La qualità con modelli piccoli sulla lingua sorgente va verificata prima di promettere correzioni grammaticali affidabili;
per questo il controllo ortografico resta a LanguageTool (RF-16) e il companion si concentra su stile, chiarezza e coerenza.

## ADR-031 — Scheletro di progetto: formato e verifica (attua ADR-028)
**Decisione**:
- **File** `scheletro.yaml`: `nome`, `versione`, `nodi` ricorsivi con `id`, `titolo` (testo o mappa lingua → testo), `obbligatorio` (predefinito sì), `guida`, `nodi`.
  Un nodo con figli è un capitolo, una foglia è una sezione. I nodi di primo livello **devono** avere figli (sono capitoli): evita capitoli con una sola sezione fittizia. Al massimo 3 livelli di capitoli (RF-02).
  Chiavi sconosciute rifiutate. Gli errori riportano riga e motivo (ruamel round-trip per le righe); un file non valido non crea nulla.
- **Marcatura**: ogni capitolo ha `scheletro: <id>` in `_capitolo.yaml`, ogni sezione nel front matter. Il titolo è nella lingua sorgente del progetto. La guida è un commento HTML `<!-- Guida: … -->` nel corpo (non esportato; l'editor lo mostra come blocco protetto).
- **Conformità** (`GET …/skeleton/check`): `missing` · `empty` (solo commenti/spazi, per le obbligatorie) · `misplaced` (padre diverso da quello previsto) · `out_of_order` (fuori dalla sottosequenza crescente più lunga) · `ok`; i nodi senza marca sono `extra`. Le facoltative non fanno mai fallire la conformità.
- **Crea mancanti**: crea i nodi obbligatori assenti sotto il loro padre e rimette i fratelli nell'ordine dello scheletro (rinumera i prefissi, come ogni riordino). Le facoltative solo su richiesta.
- Scheletri forniti con l'app in `examples/scheletri/` (uno stile ECSS abbreviato, **didattico**: va confrontato con la norma originale, che non è inclusa); si può caricare un file proprio alla creazione.
**Limiti**: il riordino rinumera i file, quindi i segmenti tradotti in `.traduco/segmenti/` legati al vecchio percorso si rigenerano; la UI non permette ancora di modificare lo scheletro di un progetto esistente (l'API `PUT …/skeleton` sì).

## ADR-032 — Controllo della traduzione e glossario (M3)
**Decisione**:
- **Stato del segmento** (store JSON, ADR-029): una modifica manuale imposta `origin: manual`, `locked: true`; un segmento bloccato non è mai riscritto da ritraduzioni di sezione, capitolo o progetto né da cambi di tono.
  Se il suo sorgente cambia mantiene il testo dell'autore, passa a `needs_review` e la nuova traduzione del modello è in `pending_target` (Accetta/Ignora). Ignorare riporta a `translated` ma resta bloccato.
- **Modifica diretta e sorgente** (RF-24): dopo aver salvato una correzione, per 10 s l'anteprima offre «Proponi un aggiornamento del sorgente» (ritraduzione inversa verso la lingua sorgente, modificabile) o «Ignora» (stato `diverged`).
  «Applica» riscrive solo quel segmento nel file con la stessa scrittura atomica dell'editor (`If-Match`): lo store è aggiornato *prima* (hash del sorgente nuovo), così la modifica non genera una ritraduzione; l'editor aperto si ricarica dall'evento di file.
- **Istruzioni** (RF-26): prompt `revise@1`; la risposta è solo una proposta, nulla è salvato finché l'utente non la usa (che la rende `manual`+`locked`). «Alternative» chiede 3 varianti in parallelo (temperatura 0,8) e scarta doppioni e testo identico.
- **Glossario** (`glossario.yaml`, riscritto per intero a ogni salvataggio, quindi i commenti non sopravvivono; `sorgente` resta il primo campo): le voci pertinenti entrano nel prompt; «non tradurre» passa anche dai segnaposto.
  Verifica in `core/translation/glossary.py` (il piano diceva `glossary_check.py`): termine imposto presente, vietati assenti, «non tradurre» invariato; confronto senza distinzione di maiuscole, parola intera, con `-s/-es` e vocale finale variabile (offerta/offerte). Una violazione dà un secondo tentativo con l'elenco dei problemi; se persiste: `needs_review` con motivo `glossary: …`, il testo migliore resta visibile.
- **Tono**: del progetto (selettore in alto) e della sezione (menu nell'anteprima, scritto nel front matter `tono`, con la nota `contesto`); cambiarlo ritraduce sezione o progetto, solo i segmenti non bloccati.
- **Modalità** `Ctrl+1/2/3` (Scrittura, Revisione, Concentrazione). La Revisione è una tabella di tutti i segmenti del progetto con filtri; `F8` salta al successivo «da rivedere» anche in un'altra sezione. L'elenco è calcolato leggendo i file e lo store di ogni sezione (nessun indice): da rivalutare nel test di prestazioni di M6.
- La barra delle azioni resta sull'ultimo segmento toccato dal mouse (non si nasconde all'uscita) perché gli eventi di uscita non sono affidabili sulla barra stessa e nei test.
**Limiti**: il menu «Aggiungi al glossario» precompila la parola selezionata come traduzione imposta; il termine sorgente va scritto a mano. Import/export TBX/CSV (RF-44) rimandato a M6. Le scorciatoie `E I L A` valgono solo con il focus sull'anteprima.

## ADR-033 — Impostazioni del modello modificabili dall'app
**Contesto**: senza un server di modelli l'utente vedeva solo «Modello non raggiungibile» e l'unico rimedio erano le variabili d'ambiente (`TRADUCO_LLM_*`).
**Decisione**: `GET/PUT /api/settings` (indirizzo, modello, chiave API) salvano in `<workspaces>/.traduco/settings.yaml` (permessi `600`, può contenere una chiave) e hanno la precedenza sulle variabili d'ambiente.
Il servizio si riconfigura senza riavvio: i lavori in coda e il monitor usano subito il nuovo indirizzo (l'indirizzo è risolto all'esecuzione del lavoro; solo il modello per-progetto è fissato nel lavoro). L'interfaccia ha «Salva e verifica»,
che distingue server irraggiungibile da modello assente e mostra i modelli disponibili. Il banner offline rimanda alle impostazioni. L'API non restituisce mai la chiave, solo `has_api_key`.
**Conseguenze**: l'installazione automatica di Ollama e del modello resta nella M4b (RF-70…79); fino ad allora l'utente installa Ollama da sé.

## ADR-034 — Modelli che ragionano: ragionamento spento e budget di token
**Contesto**: con Gemma 4 E4B su Ollama la traduzione restava in coda e finiva in «da rivedere» (`empty translation`). Il modello «pensa» per circa 450 token prima di rispondere; il nostro limite (3× la lunghezza del sorgente, ≈200 token) si esauriva nel ragionamento e il testo restava vuoto (`finish_reason: length`). Misurato: 1,8 s e testo vuoto contro 0,2 s e traduzione corretta con il ragionamento spento.
**Decisione**: il client invia sempre `reasoning_effort: "none"` (Ollama lo accetta sull'endpoint compatibile OpenAI; `think: false` no). Un server che lo rifiuta con 400/422 citando «reasoning» viene richiamato senza il parametro e il client se lo ricorda.
Se la risposta è vuota perché tagliata dal limite, una sola nuova richiesta con 6× i token. Il minimo di `max_tokens` sale da 64 a 256.
**Conseguenze**: la traduzione di una sezione di esempio (5 segmenti) richiede circa 2 s sulla RTX 5070 Laptop. Le traduzioni fallite prima della correzione restano «da rivedere» finché non si usa «Ritraduci».

## ADR-035 — Companion di scrittura (M3b, attua ADR-030)
**Decisione**:
- **Unità = segmento.** Le azioni (Correggi, Riformula, Più conciso, Più semplice, tono formale/neutro/informale, più un'istruzione libera) lavorano sul sorgente di un segmento, non su una selezione libera:
  evita di mappare selezioni ProseMirror/CodeMirror su byte del file e rende ogni proposta applicabile in modo esatto. Dall'editor, il pulsante «Assistente» agisce sul blocco sotto il cursore (il suo primo segmento); dall'anteprima, la barra al passaggio del mouse e il menu contestuale.
- **Proposta, mai applicazione.** `POST /assist` restituisce `{original, proposal}`; l'interfaccia mostra la differenza per parola (LCS sulle parole, `lib/diff.ts`). `POST /assist/apply` riscrive il solo segmento con la scrittura atomica `If-Match` e chiama la sincronizzazione normale:
  si ritraduce quel solo segmento (un segmento bloccato riceve una proposta, come in M3). Prima di applicare l'editor scrive la digitazione non salvata (`editorBridge.flush`) e dopo chiede di rileggere il file subito (`recheckOpenFile`), senza attendere l'osservatore di file, lento su WSL.
- **Validazione** della proposta (`companion/improve.py`): segnaposto integri (stessa protezione della traduzione), non vuota, lunghezza 0,3–2,5×, e i **termini del glossario** presenti nell'originale restano presenti (un solo tentativo correttivo). Le voci «non tradurre» sono protette.
  La nota di contesto, il tono e la **guida dello scheletro** della sezione entrano nel prompt (`improve@1`).
- **Controllo di sezione** (`POST /check`): una richiesta al modello per segmento (≥ 25 caratteri; due alla volta) con risposta JSON `{category, message, suggestion}`; un JSON illeggibile vale «nessun rilievo»; una correzione che rompe i segnaposto è scartata ma il rilievo resta. In più una richiesta per sezione sulla **copertura della guida** dello scheletro (`guide@1`).
  Le **regole per i requisiti** (`companion/rules.py`: più prescrizioni in una frase, verbi deboli, parole vaghe; italiano e inglese) sono deterministiche e **facoltative** (casella nel pannello) perché la prosa normale le farebbe scattare.
- **Persistenza**: `.traduco/cache/suggestions/<sezione>.json` (nel `.gitignore`); un suggerimento vale finché l'hash del segmento è lo stesso. Nessun suggerimento parte da solo (RF-89).
- **Con il modello spento** pulsanti disattivati e messaggio; l'editor non è toccato.
- **Correzione trasversale**: la coda e il servizio di traduzione erano usati da endpoint `def` di FastAPI, che girano in thread, mentre gli oggetti `asyncio` (eventi, code del WebSocket) non sono thread-safe: `submit/cancel/pause` ed `emit` ora passano sempre dal ciclo degli eventi (`call_soon_threadsafe`). Prima un lavoro inviato da un thread poteva restare fermo finché qualcos'altro non svegliava il ciclo.
**Limiti**: niente selezione libera di testo; in una lista l'assistente dell'editor sceglie la prima voce del blocco; le regole per i requisiti non conoscono gli identificativi dei requisiti (RF-84) né le tracce tra documenti; la qualità dei rilievi dipende dal modello (con Gemma 4 E4B i rilievi di stile sono utili ma a volte generici).

## ADR-036 — Template ed export DOCX (M4, attua ADR-004)
**Decisione**:
- **Analisi** (`templates/analyze.py`): stili per `styleId` e nome (con «personalizzato», livello di struttura, numerazione), segnaposto cercati nel testo unito dei paragrafi (Word li spezza in più *run*) in corpo, intestazioni, piè di pagina e caselle di testo.
  La proposta di mappatura sceglie per ruolo lo stile con punteggio più alto (nome/ID per titolo N, corpo, didascalia, tabella, elenchi, citazione, codice; +3 se personalizzato, +2 se il livello di struttura coincide, +1 se numerato): fra «Titolo 1» di Word e «Azienda Titolo 1» vince quello aziendale. L'utente può cambiare ogni ruolo.
  `template/<nome>.yaml` ha il formato del documento di architettura; `numerazione_titoli` è conservato ma la numerazione dei titoli viene sempre dagli stili del template (nessun numero scritto a mano nel testo).
- **Caricamento**: corpo grezzo (`POST …/templates?filename=`, come le immagini, nessuna dipendenza `python-multipart`); controlli su zip, dimensione e assenza di macro; mai eseguito nulla del file.
- **Unione** (`export/combine.py`): un titolo per capitolo (livello = profondità) e per sezione (livello del capitolo + 1); un primo titolo che ripete il titolo della sezione è scartato, gli altri scendono sotto di esso. Immagini copiate con nomi neutri in una cartella di lavoro; quelle remote o fuori dal progetto sono escluse con un avviso (Pandoc non deve mai usare la rete).
  Diagrammi Mermaid = il PNG in cache: se manca, l'export si ferma e indica la sezione. Link a `.md` → ancore; etichette delle note uniche per sezione.
- **Pandoc** (`commonmark_x` senza HTML grezzo, senza `raw_attribute`, senza `smart`, con `implicit_figures`): una sezione non può iniettare XML nel Word. **Niente filtro Lua**: gli stili si scambiano in Python sul DOCX di Pandoc (ID di stile di Pandoc → ID del template), con più controllo su elenchi e tabelle.
  I paragrafi di elenco passano allo stile di elenco del template; se quello stile ha una propria numerazione la numerazione diretta di Pandoc è tolta (dopo l'unione: `docxcompose` ne ha bisogno mentre fonde).
- **Composizione** (`export/compose.py`): il corpo sostituisce il paragrafo `{{CONTENUTO}}` (che deve essere un paragrafo normale del corpo) con `docxcompose.insert`; `{{SOMMARIO}}` → campo TOC; `{{REVISIONI}}` → tabella con lo stile tabella mappato; didascalie delle figure con campo `SEQ` («Figura 1 – …»);
  `{{campo}}` in tutto il documento; campi senza valore bloccano l'export salvo `campi_mancanti_ammessi`; `w:updateFields` perché Word aggiorni indici e numeri all'apertura (compare la domanda di Word). Senza template si usa il documento predefinito di Pandoc con un avviso.
- **Traduzione**: l'export in lingua ufficiale riallinea e attende le traduzioni mancanti (max 300 s; modello spento → avviso e testo sorgente), traduce titoli dei capitoli (cache `.traduco/cache/titles-<lingua>.json`) e i metadati elencati in `metadati_da_tradurre` (compresa `descrizione` delle revisioni).
- **Lavori**: `POST /export` → job in memoria, `GET /export/{id}` per l'avanzamento, `…/download` a fine lavoro; il browser scarica da solo. Istantanea in `.traduco/export/<istante>/` (`combined.md` + `map.json`) per l'import delle revisioni (M5). `Ctrl+E` ripete l'ultima scelta.
- **Strumenti esterni**: Pandoc è cercato in `$TRADUCO_PANDOC`, `.runtime/pandoc` (`make tools` lo scarica verificando lo SHA-256 del `manifest.toml`), PATH. LibreOffice solo da `$TRADUCO_SOFFICE` o PATH finché il launcher (M4b) non lo installa. In CI Pandoc e LibreOffice sono obbligatori (`TRADUCO_REQUIRE_TOOLS=1`).
**Limiti**: il template di prova è sintetico (non un vero template aziendale); l'apertura in Word non è verificata, solo con python-docx, Pandoc e (in CI) LibreOffice; titoli di Mermaid non tradotti; nessuna didascalia per le tabelle; il sommario è un campo da aggiornare (Word lo chiede, LibreOffice no senza macro); numerazione dei titoli solo se il template la definisce negli stili.

**Aggiunta a ADR-036 (dopo la prima prova reale)**: un progetto può nominare un `template_predefinito` che non c'è nella cartella `template/` (creato da una versione precedente, file cancellato a mano). L'export non fallisce più:
usa l'unico template presente oppure gli stili di Pandoc e lo dice negli avvisi; un template chiesto per nome e assente resta un errore. Il pannello Template ha «Aggiungi il template di esempio» (`POST …/templates/example`).
Altro difetto trovato provando template diversi: `{{REVISIONI}}` dentro una cella di tabella lasciava la cella senza paragrafo finale (Word la considera danneggiata). Ora il paragrafo resta, vuoto. Nuovi test con template costruiti in modo diverso:
documento Word semplice, copertina in tabella con più sezioni e pagina orizzontale, controlli di contenuto, `{{CONTENUTO}}` spezzato in pezzi o dentro una tabella.

## ADR-037 — Launcher completo (M4b, attua RF-70…79)
**Decisione**:
- **Nove passi numerati**: controlli · dipendenze del backend · Pandoc portabile · interfaccia (Node + build solo da sorgenti) · hardware e scelta del modello · Ollama · modello · LibreOffice · avvio. Un server di modelli già configurato e raggiungibile (impostazioni salvate nell'app o `TRADUCO_LLM_BASE_URL`) fa saltare i passi Ollama e modello; l'indirizzo di Ollama stesso scritto `localhost` o `127.0.0.1` non conta come «altro server».
- **Scelta del modello** (`hardware.py`, funzione pura sulla tabella dell'architettura): GPU ≥ 20 GB → `26b-a4b`; RAM ≥ 12 GB o GPU ≥ 6 GB → `e4b`; altrimenti `e2b`. RAM da `/proc/meminfo`, `sysctl`, `GlobalMemoryStatusEx`; GPU NVIDIA da `nvidia-smi`, AMD da sysfs (Linux), Apple Silicon = 65 % della memoria unificata. Priorità: `--model` > modello salvato nelle impostazioni dell'app > scelta per l'hardware. Taglie e tag nel `manifest.toml`.
- **Ollama** (`ollama.py`): rilevato via HTTP (`/api/version`, mai tramite proxy); se è installato ma spento lo avvia il launcher (e lo ferma all'uscita; uno già attivo non si tocca). Installazione **solo su conferma** mostrando il comando: Windows `winget install --id Ollama.Ollama`, macOS `brew install --cask ollama`, Linux lo script ufficiale `curl … | sh` (chiede `sudo`).
  Senza terminale o senza `--yes` la risposta è «no»; il rifiuto è ricordato (`--update` richiede di nuovo) e l'app parte lo stesso. Non c'è ripiego sull'installer scaricato di Windows perché non se ne può fissare l'hash (regola: ogni download è verificato); si indica la pagina ufficiale.
- **Il modello si scarica in sottofondo**, a backend già avviato: il browser si apre subito, l'editor funziona e l'interfaccia mostra la percentuale. Il launcher scrive `.runtime/model.json` (`downloading|ready|error|unavailable`), il backend lo espone in `/api/capabilities`; la coda di traduzione resta ferma finché il modello non c'è (non segna errori) e riparte da sola.
  Spazio insufficiente per il modello → errore E043 nella banda, non fatale. `ollama pull` riprende dopo un'interruzione.
- **Pandoc** nel manifest per le cinque piattaforme, con SHA-256 (scaricato e verificato solo su Linux x64; le altre piattaforme sono nel manifest ma mai eseguite). **LibreOffice** mai installato: rilevato (PATH e posti standard) e passato al backend; senza, PDF/ODT restano disattivati nell'interfaccia con la spiegazione.
- **Opzioni**: oltre a quelle previste, `--yes` (risponde sì alle domande) e `--prepare-only` (installa senza avviare, per il pacchetto offline). `--offline` imposta anche `UV_OFFLINE` negli script di avvio.
- **PDF e ODT** (pulsante «Formato» del pannello Esporta) sono già esportabili con LibreOffice: conversione semplice del DOCX; l'aggiornamento di indici e campi prima della conversione resta in M5.
- **Pacchetto offline** (`make bundle-offline OS=linux|windows [MODEL=tag]`, `tools/bundle-offline.py`): ZIP con programma, `frontend/dist`, esempi e `.runtime/{uv,python,uv-cache,pandoc}`; gli ambienti virtuali non sono trasportabili e si ricreano al primo avvio dalla cache, senza rete. Si costruisce sul sistema di destinazione (lo fa la CI su Ubuntu e Windows e poi lo avvia con `--offline` da un'altra cartella).
  Con `MODEL` aggiunge i file del modello di `~/.ollama/models`, usati se il launcher avvia da sé Ollama (`OLLAMA_MODELS`); con un Ollama già attivo il modello va importato a mano. Lo ZIP Linux contiene collegamenti simbolici: si apre con `unzip`.
- **Cache del browser** (difetto trovato nel frattempo): `index.html` non è più messo in cache e i file con hash nel nome sono immutabili; una pagina vecchia si ricarica da sola se un pezzo non si carica.
**Non verificato**: avvio da zero su VM Windows 11 e Ubuntu 24.04 con il modello vero (la CI usa un finto Ollama su runner Ubuntu e Windows; sul computer di sviluppo ho provato Ollama vero già installato con il modello già scaricato); installazione di Ollama con consenso (testata solo con sostituti); `winget`, `brew`, macOS e arm64; il download di `e2b`/`26b-a4b`; il pacchetto offline con i pesi del modello.


## ADR-038 — PDF/ODT con aggiornamento dei campi, procedura guidata dei template, import dei documenti rivisti (M5)
**Decisione**:
- **Aggiornamento di indice e campi**: LibreOffice esegue una macro Basic (`ConvertUpdating`) installata in un profilo temporaneo; carica il DOCX, aggiorna indici e campi, salva PDF/ODT. La macro parte **solo su un profilo che LibreOffice ha già inizializzato** (verificato con il flusso `lo-probe`, LibreOffice 26.2): prima si lancia `--terminate_after_init`, poi si installa la macro e la si chiama. Se la macro non produce il file si ripiega sulla conversione semplice (con avviso nei diagnostici). `tools/lo-macro-probe.py` e il workflow manuale `lo-probe.yml` restano come strumento di diagnosi.
- **Procedura guidata** (`templates/wizard.py`): parte dal `reference.docx` di Pandoc, quindi tutti gli stili usati dall'export esistono; quattro passi (aspetto, copertina, intestazione/piè di pagina, contenuti), logo PNG/JPEG ≤ 2 MB, caratteri da un elenco fisso, colore esadecimale validato. L'anteprima nell'interfaccia è uno schizzo, non il rendering di Word.
- **Import**: il DOCX è letto direttamente dal suo XML (`importer/docx_text.py`) e non passa da Pandoc: così le tabelle e le revisioni sono esatte (`w:ins`/`moveTo` tenuti, `w:del`/`moveFrom` scartati, con autori). Il confronto è con lo **snapshot** dell'export (`map.json` con `units`), ritrovato dall'identificatore scritto nelle proprietà del documento (altrimenti l'ultimo export, con avviso). Corpo e note si allineano separatamente (`difflib`); i tratti diversi si accoppiano per somiglianza (≥ 0,5) o, tra due unità uguali, in ordine; copertina, indice e tabella delle revisioni (ai bordi) sono ignorati.
- **Proposte** (`.traduco/import/<job>.json`): modificata / aggiunta / eliminata, con testo attuale, testo proposto, testo del cliente, autori, flag `tracked`, `stale` (il sorgente è cambiato dopo l'export, rilevato dall'hash) e `applicable`. Nulla si applica senza «Accetta»; l'autore può correggere il testo proposto.
- **Retro-traduzione**: per un export in lingua ufficiale il modello riscrive il testo del cliente nella lingua sorgente (2 richieste in parallelo). Accettando, la traduzione del cliente è registrata prima di scrivere il sorgente (origine `import`, bloccata), così la sincronizzazione non la ritraduce. Un export in lingua sorgente applica solo il sorgente.
- **Metadati del progetto**: nel pannello Template un modulo per i valori dei `{{campi}}` e per la storia delle revisioni (`progetto.yaml`), perché senza valori i template nuovi non esportano.
**Limiti**: il testo del cliente è semplice (la formattazione inline si perde); aggiunte/eliminazioni di celle di tabella e dei titoli di capitolo non sono applicabili in automatico (il titolo di capitolo modificato sì); un paragrafo con sola immagine non è confrontato; l'apertura in Word dei file importati non è verificata, solo documenti costruiti con python-docx.

## ADR-039 — Emissioni, confronto, tabella dei cambiamenti e commenti (M5b, attua RF-80…83)
**Decisione**:
- **Emissione** = copia congelata: `.traduco/emissioni/<numero>/` con `meta.json` (numero, data, descrizione, albero com'era, tabella dei cambiamenti), `sorgente/` e `ufficiale/` con il Markdown di ogni sezione. File semplici e fuori da `.gitignore`: viaggiano con Git. Il numero accetta lettere, cifre, `.`, `_`, `-` (è anche un nome di cartella). Il testo ufficiale è quello **al momento del congelamento** (traduzioni ancora in coda: testo sorgente per quei segmenti). Congelare aggiunge la riga alla storia delle revisioni di `progetto.yaml` (salvo «nella_tabella»: false). Il file `meta.json` è scritto per ultimo: un congelamento interrotto non lascia un'emissione a metà.
- **Confronto** (`emissions/compare.py`): due lati qualsiasi tra emissioni e `bozza`; sezioni abbinate per percorso, poi per titolo uguale (rinominate o rinumerate); diff **per parola** (`difflib` su token di parole, spazi e punteggiatura) calcolato nel backend così sorgente e ufficiale usano la stessa logica; il frontend mostra inseriti/eliminati e scorre cambio per cambio. Il front matter è escluso, il titolo no. Ripristinare una sezione sovrascrive il file con il testo dell'emissione (con il controllo di concorrenza abituale; è una modifica normale, annullabile da un'altra emissione o da Git).
- **Tabella dei cambiamenti**: una riga per sezione cambiata rispetto all'emissione precedente (o a una indicata); per le sezioni modificate il modello scrive **una frase** nella lingua sorgente da ciò che è stato tolto e aggiunto (`changes@1`, max 120 token, 1800 caratteri di estratto); modello spento o in errore → riga contata («Modificata (N parole aggiunte, M rimosse)») senza aspettare il server per ogni sezione. L'autore corregge le righe; «Usa nella tabella» scrive `Titolo: frase; …` nella descrizione della revisione, che l'export traduce come le altre.
- **Commenti** (`emissions/comments.py`): `.traduco/commenti/<percorso senza .md>.json`, fuori dal testo. Un thread ricorda chiave del segmento, hash del sorgente ed estratto; si ritrova per chiave+hash, poi per hash unico, poi per segmento più simile (≥ 0,6), altrimenti è «perso» ma resta leggibile con l'estratto. Autore = nome digitato (nessun account: ricordato nel browser). Stato aperto/risolto.
**Limiti**: rinominare una sezione sul disco lascia il suo file di commenti col vecchio nome (come i file dei segmenti, che si riallineano per hash); le tabelle e i diagrammi sono confrontati come testo Markdown; non c'è ancora un confronto tra due emissioni dentro l'anteprima affiancata, ma in un pannello a parte; nessun test e2e del nuovo flusso.

## ADR-040 — Modelli di documento software, riferimenti tra requisiti, altri formati di export e snippet (M5c, attua RF-84…86)
**Decisione**:
- **Modelli** ADD, DDD e SRS: tre scheletri in `examples/scheletri/` (titoli it/en, guida per sezione), scritti da zero e ispirati alle prassi comuni (ISO/IEC/IEEE 29148, 1016, 42010) senza riprodurre il testo delle norme. Non cambia il formato di RF-09.
- **Riferimenti tra requisiti** (`trace/requirements.py`): nessuna sintassi nuova. Un identificativo (gruppi di maiuscole/cifre separati da `-` che finiscono con 3+ cifre: `FOO-REQ-00042`) all'inizio di un paragrafo, voce di elenco, titolo o cella **definisce** un requisito; ogni altra menzione è un **riferimento**. Problemi: definito due volte, citato ma non definito, mai citato. Un riferimento è «non definito» solo se la sua famiglia di prefisso (`FOO-REQ-`) ha almeno un requisito definito nel progetto, così `ISO-9001` o `RFC-2119` non danno falsi allarmi. Il controllo è dentro un progetto; tra più documenti (progetti) la tracciabilità non è verificata.
- **Export HTML, EPUB, Markdown** (`export/web.py`), senza template, campi o tabella delle revisioni e **senza snapshot** (non si reimportano): HTML = un solo file con stile e script in linea e immagini incorporate (`data:`), indice a sinistra dai titoli (livelli 1-3), ricerca che filtra e evidenzia, tema chiaro/scuro e stampa; funziona da `file://`. L'HTML grezzo è spento nell'input di Pandoc, quindi una sezione non può aggiungere script. EPUB = `pandoc -t epub3` con titolo e lingua. Markdown = `.md`, o `.zip` con `document.md` e `img/` se ci sono immagini.
- **Snippet** (`snippets/model.py`): `snippet.yaml` con `contatori` (`prefisso`, `cifre`, `inizio`) e `snippet` (`alias`, `descrizione`, `testo`). Macro espanse all'inserimento: `{{contatore:NOME}}`, `{{data}}` (formato della lingua sorgente), `{{titolo}}`, `{{progetto}}`; ogni altro `{{x}}` resta (può essere un campo del template). Contatori in `.traduco/contatori.json` (versionabile), avanzati una volta per uso sotto lock. Il file è validato prima di essere salvato. Tab-stop alla VS Code (`${1:testo}`): in modalità Markdown il primo segnaposto è selezionato dopo l'inserimento; nella modalità Documento il testo predefinito è inserito e basta (nessun salto con Tab).
**Correzione trovata lungo la strada**: l'identificatore scritto nel Word esportato non coincideva con l'id dello snapshot (una variabile era sovrascritta); l'import ripiegava sull'ultimo export. Ora coincidono e un test lo verifica.
**Limiti**: niente salto tra tab-stop successivi; HTML senza revisioni né campi; nessun test e2e dei nuovi pannelli; EPUB non aperto in un lettore vero (controllato come ZIP/XHTML).

## ADR-041 — Motore integrato (llama.cpp) come alternativa a Ollama (attua RF-72)
**Contesto**: chi non può installare Ollama (nessun permesso, policy aziendali) o non ha una scheda grafica restava senza traduzione automatica.
**Decisione**: il launcher sa avviare **`llama-server` di llama.cpp** (licenza MIT) e usarlo come server OpenAI-compatibile, esattamente come Ollama: il backend non cambia, riceve solo `TRADUCO_LLM_BASE_URL`, `TRADUCO_LLM_MODEL` e `TRADUCO_LLM_API_KEY`. Non si lega un modello al processo Python (`llama-cpp-python` richiede compilatore o ruote per piattaforma, e un crash del modello abbatterebbe il backend); un processo separato si ferma e si riavvia da solo.
- **Scarico e verifica**: versione fissata `b12189` nel `manifest.toml` per linux x64/arm64, macOS x64/arm64, Windows x64 (build CPU; quelle macOS includono Metal), con lo SHA-256 pubblicato da GitHub; il file Linux x64 è stato scaricato e il suo hash coincide. Modelli: i GGUF a 4 bit di Gemma 4 **E2B (2,8 GB)** e **E4B (4,6 GB)** di `ggml-org` (Apache-2.0), con SHA-256 dall'API di Hugging Face. Download ripreso e verificato come per tutto il resto (`downloads.py`).
- **Quando si usa**: `--llm builtin` (sempre), `--llm ollama` (mai), `--llm auto` (predefinito: Ollama come prima; se manca e non lo si installa, il launcher **propone** il motore integrato, con il nome e le dimensioni dello scarico; il «no» è ricordato). Con `--offline` si propone solo se è già su disco. Si sceglie E2B su CPU (la velocità conta più della dimensione) ed E4B su un Mac con Metal e 12 GB o più.
- **Avvio**: dopo il backend, in un thread, come per lo scarico con Ollama: l'editor funziona subito, la traduzione resta in attesa (stato `downloading` in `.runtime/model.json`, anche mentre il modello si carica) e riparte da sola a `ready`. Si ferma con l'app. Porta preferita 18434, altrimenti una libera; solo `127.0.0.1`.
- **Sicurezza**: senza chiave `llama-server` risponde a qualunque origine web, quindi una pagina aperta nel browser potrebbe usare il modello. Il launcher genera una **chiave casuale** per avvio, la passa con `--api-key-file` (file `.runtime/llama-key`, permessi 0600; non compare nell'elenco dei processi) e al backend; senza chiave si ottiene 401 (provato in CI). Interfaccia web del server spenta (`--no-webui`).
- **Ragionamento**: `--reasoning off`, in più del `reasoning_effort: "none"` che il client già invia (ADR-034).
**Verificato** (CI, Ubuntu e Windows): lancio reale di `llama-server` con un modello di prova da 38 MB (`stories15M_MOE`, MIT), il backend lo raggiunge con la chiave, `/api/llm/status` risponde online, l'arresto dell'app ferma il server. Il probe manuale `llama-probe.yml` ha mostrato i flag e che `/health` è pubblico, `/v1/models` e la chat richiedono la chiave e accettano `reasoning_effort`.
**Non verificato**: la qualità e la velocità delle traduzioni con Gemma 4 E2B/E4B sul motore integrato (solo il modello di prova è stato eseguito); macOS e Linux arm64 (hash dal sito, binari mai avviati); nessuna accelerazione GPU fuori da Metal (le build Vulkan/CUDA esistono ma non sono scaricate: possibile miglioria); il pacchetto offline non include ancora il motore.

## ADR-042 — Le istruzioni libere riscrivono, non scrivono (RF-26, RF-87, RF-89)
**Contesto**: la casella «Istruzione» (riscrittura della traduzione, RF-26) e il campo «Istruzione (facoltativa)» dell'assistente di scrittura (RF-87) accettano testo libero. Un modello obbediente scriveva qualunque cosa chiesta (la ricetta della carbonara in un manuale tecnico), e la traduzione accettata restava senza corrispondenza nel testo sorgente, senza alcun avviso.
**Decisione**: tre livelli, perché un modello piccolo non rifiuta in modo affidabile da solo.
1. **Prompt** `revise@2` e `improve@2`: il modello *riscrive soltanto*; non aggiunge fatti, passi, esempi, elenchi o titoli; i testi e l'istruzione sono dati (un comando scritto nel testo si ignora); se l'istruzione chiede altro risponde esattamente `[[REFUSED]]`.
2. **Controllo deterministico della risposta** (`translation/guard.py`), qualunque cosa dica il modello: niente paragrafi, voci di elenco o titoli in più rispetto al testo; lunghezza fino a 1,8 volte il testo (soglia non applicata sotto i 20 caratteri); se è più lunga di 1,25 volte, almeno il 30 % delle sue parole deve già comparire nel testo (o nell'originale). Una risposta scartata ha un secondo tentativo con la correzione; se fallisce ancora, l'esito è `off_topic`.
3. **Errore chiaro**: codice `off_topic` (HTTP 422) con un messaggio in italiano e inglese; nulla viene cambiato né salvato.
**Conseguenze**: un'istruzione che chiede davvero di *aggiungere* contenuto («aggiungi un esempio») viene rifiutata: il contenuto nuovo si scrive a mano nel testo. Il controllo non giudica la qualità né sostituisce la revisione dell'autore (la proposta non si applica da sola, RF-89); un'aggiunta breve e verosimile (meno del 25 % più lunga, senza nuove righe) può passare. Il controllo vale anche per un modello molto obbediente, come provato con un finto modello.
**Allineamento con il sorgente**: dopo «Usa questa» di una riscrittura della traduzione compare, come dopo una modifica a mano, l'avviso «il sorgente non corrisponde più alla tua traduzione» con «Proponi un aggiornamento del sorgente» (retro-traduzione) e «Ignora» (il segmento resta segnato come divergente).
**Correzione collegata**: la protezione dei segnaposto accettava enfasi che si incrociavano con una coppia già trovata (`_:*_*` dava `⟦2⟧:⟦1⟧⟦/2⟧⟦/1⟧`, rifiutato poi dalla verifica); ora un'enfasi che taglierebbe un'altra coppia resta testo. Trovato dal test di proprietà.

## ADR-043 — Qualità e rifinitura (M6): memoria di traduzione, lingue aggiuntive, ricerca, tabelle
**Memoria di traduzione** (`translation/tm.py`, RF-29): SQLite in `.traduco/tm.sqlite` (fuori da Git), chiave = coppia di lingue + sorgente con spazi normalizzati. Vi entrano le traduzioni **approvate** e quelle **scritte a mano** (l'autore le considera definitive), mai quelle del solo modello. Un segmento nuovo o modificato il cui sorgente è già in memoria (corrispondenza esatta, maiuscole comprese) è riempito senza chiamare il modello (origine `tm`, stato "tradotto"); una ritraduzione forzata non la usa. Le frasi **simili** (somiglianza di caratteri ≥ 0,75, prefiltro per lunghezza) si propongono dal pulsante del segmento, mai in automatico. TMX 1.4: esportazione completa, importazione senza espansione di entità né rete.
**Glossario CSV/TBX** (`glossary_io.py`, RF-44): CSV una riga per termine e lingua (delimitatore riconosciuto, BOM per Excel), TBX-Basic ridotto (termEntry/langSet, termini vietati con `administrativeStatus`). L'importazione **unisce**: un termine già presente conserva ciò che ha e riceve ciò che manca.
**Lingue aggiuntive** (RF-21b…d): `Project.for_language(code)` dà una *vista* del progetto in cui quella lingua è la destinazione, con il suo tono e formato data; tutta la logica esistente (sincronizzazione, azioni sui segmenti, export, memoria) lavora sulla vista senza duplicazioni. `sync` aggiorna prima la lingua ufficiale e poi le aggiuntive con priorità minima (`PRIORITY_BULK`): non fanno mai attendere la ufficiale. Le richieste sui segmenti accettano `lang`; l'interfaccia ha un selettore con le percentuali (`GET /languages`) e un pannello per aggiungere o togliere lingue. Un export in lingua aggiuntiva è un export "ufficiale" della vista; l'import di un suo documento rivisto riconosce la lingua dallo snapshot. **Pivot** (RF-21e): con `base: ufficiale` una lingua aggiuntiva traduce a partire dalla traduzione ufficiale **approvata** del segmento, non dal sorgente (la vista porta `pivot_lang`; il lavoro riceve il testo ufficiale e `source_language` = ufficiale). Finché il segmento ufficiale non è approvato quello resta in coda con motivo `awaiting_pivot`, senza lavoro e senza far attendere l'export; approvarlo risveglia le lingue pivot. Se il testo ufficiale approvato cambia dopo, la traduzione pivot non si rifà da sola (serve «Ritraduci»). **Revisione per lingua**: `GET /review?lang=` e la tabella di revisione seguono la lingua scelta nel selettore.
**Export bilingue** (RF-64): per sezione una tabella a due colonne con una riga per segmento, passata dalla stessa pipeline (template, indice, campi). Codice, tabelle e diagrammi non vi stanno e l'export lo dice; non produce uno snapshot (non si reimporta).
**Ricerca e palette**: la ricerca nel testo (`GET /search`) scorre sorgente e traduzioni senza indice (i file restano l'unica fonte), ignorando maiuscole e accenti, con limite di risultati; la palette `Ctrl/⌘+K` unisce sezioni, azioni e questi risultati con un punteggio fuzzy; le scorciatoie hanno una sola lista in `lib/shortcuts.ts` (il pannello `?` la legge). Prestazioni: un progetto da 300 sezioni apre l'albero in ben meno di un secondo (test in `tests/perf`).
**Editor di tabelle** (RF-12): in modalità Documento con i comandi di tabella di Milkdown; in modalità Markdown con una riscrittura del blocco a pipe (celle, allineamento e `\|` mantenuti, intestazione sempre prima). Stesso menu per entrambe.
**Riferimenti tra sezioni** (RF-07): già risolti dall'M4 (collegamenti a file `.md` diventano ancore del documento); un frammento `#titolo` porta all'inizio della sezione, non al titolo.
**Non fatto**: anteprima del template in PDF (RF-57).
**Provato nel browser** (Playwright con il finto modello): palette, ricerca, `?`, requisiti, snippet con contatore, commenti, emissioni con confronto e tabella dei cambiamenti, seconda lingua con pivot, memoria di traduzione.

## ADR-044 — Controllo ortografico opzionale con LanguageTool (RF-16)
**Decisione**: spento di default; si attiva con `TRADUCO_LANGUAGETOOL_URL` che punta a un server **dell'autore** (profilo compose `languagetool`, immagine non fissata come per Ollama). È l'unico client di rete oltre a quello del modello: `test_no_network_clients` lo elenca per nome. Solo il sorgente è controllato. Il testo parte come *dati annotati* (parole come testo, sintassi Markdown come markup), così codice, link e campi non sono segnalati e gli scostamenti valgono per il segmento com'è scritto. Una correzione si applica come ogni altra proposta del companion (RF-89): solo su scelta dell'autore.
**Non verificato**: contro un LanguageTool vero (solo un finto server); il formato delle varianti linguistiche (`en-US`, `de-DE`, `pt-PT`) è quello della sua documentazione.

## ADR-045 — Cosa ha mostrato la prima prova con Gemma vera, e cosa ne è seguito
Per la prima volta un documento realistico (generato da `tools/make-big-project.py`, 17 sezioni, 172 segmenti) è passato dal modello vero (`gemma4:e4b` su Ollama, RTX 5070 8 GB) e non solo dal finto modello. Misurato con `tools/benchmark-translation.py`: **172 segmenti in circa 50 secondi (3,4 al secondo)**. Prima delle correzioni: 2 segmenti su 172 vuoti, il glossario non riconosceva i plurali, e la ricetta nella casella Istruzione veniva restituita come testo invariato. Difetti trovati e corretti:
- **Segnaposto buttati via.** Il modello toglieva i marcatori attorno a un grassetto: sempre per un'apertura come «**Attenzione.** …» (anche senza glossario, 8 prove su 8) e per un termine del glossario dentro un grassetto («**messa in servizio**» diventava «commissioning»). Dopo due tentativi il segmento restava **vuoto**. Ora: (1) il prompt `translate@2` dice di tenere i marcatori attorno alla sostituzione; (2) `translator._repair` rimette i marcatori nei tre casi in cui il posto è certo - attorno al termine imposto, attorno alla prima frase di un'apertura che finisce con punteggiatura, attorno all'intero segmento; (3) se non basta, il segmento mostra comunque la traduzione **senza** il grassetto con motivo «formatting lost» e va in revisione, invece di restare vuoto. Mai si inventa un posto incerto.
- **Glossario e flessione.** Il pattern di un termine italiano tollerava il cambio di vocale finale solo nell'ultima parola: «valvole di intercettazione» non trovava «valvola di intercettazione», quindi né il termine imposto né quelli vietati erano controllati (il modello scriveva «shut-off valves»). Ora la tolleranza vale per ogni parola di quattro lettere o più del termine **nella lingua sorgente**; il controllo sul testo tradotto resta esatto.
- **Una proposta uguale al testo non è una proposta.** Quando il modello ignora un'istruzione e restituisce il testo com'è, la casella Istruzione non mostra più un «Usa questa» inutile.
Dopo le correzioni, sullo stesso documento: 172 su 172 tradotti, 0 da rivedere, 52 occorrenze di termini imposti tutte rispettate, nessun termine vietato, ricetta rifiutata con messaggio, riscrittura «più empatico» riuscita.
**Limiti della misura**: un solo modello, una sola macchina, 17 sezioni su 109 possibili; nessuna lettura sistematica della qualità (le coppie di esempio sono nel rapporto, non valutate); l'export Word e le lingue aggiuntive non sono stati provati con il modello vero; il motore integrato (llama.cpp) non è stato provato con le traduzioni.
