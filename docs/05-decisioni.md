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
| Q8 | Tag Ollama dei modelli Gemma 4 in `manifest.toml` (`gemma4:e2b`, `e4b`, `26b-a4b`) | Da verificare sulla libreria Ollama prima di M4b | aperta |
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

