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
