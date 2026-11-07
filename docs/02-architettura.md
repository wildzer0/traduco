# 02 — Architettura

## Panoramica

```
Browser (React)  ──REST + WebSocket──▶  Backend FastAPI  ──HTTP (API OpenAI)──▶  LLM locale (Ollama / llama.cpp / vLLM)
                                          │
                                          ├── Workspace su disco (progetti = cartelle .md + YAML)
                                          ├── SQLite (memoria di traduzione, indice, coda lavori)
                                          └── Processi esterni: Pandoc, LibreOffice headless (facoltativo)
```

L'utente avvia tutto con `start.sh` / `start.cmd`, che preparano l'ambiente in `.runtime/` e lanciano il backend
(che serve anche il frontend già compilato).

- **Monoutente (MVP)**: un solo processo backend, coda di traduzione in-process (asyncio), SQLite.
- **Team (fase 3)**: stessa base di codice; coda su Valkey + worker separati, PostgreSQL, OIDC. Le interfacce
  `JobQueue` e `Store` devono quindi essere astratte fin dall'inizio.

## Struttura della repository

```
traduco/
├── AGENTS.md  CLAUDE.md  README.md  LICENSE
├── start.sh  start.cmd           # avvio con un comando (bootstrap sottile, delega al launcher)
├── Makefile  docker-compose.yml  .env.example
├── launcher/                     # logica di installazione/avvio in Python, multipiattaforma
│   ├── pyproject.toml  bootstrap.ps1
│   ├── launcher/  __main__.py  steps.py  hardware.py  downloads.py  ollama.py  office.py  ui.py
│   ├── manifest.toml             # versioni fissate, URL e SHA-256 di ogni componente per OS/architettura
│   └── tests/
├── .runtime/                     # creata dal launcher, in .gitignore: python, pandoc, node, logs, stato
├── .github/workflows/ci.yml
├── docs/                         # questi documenti
├── backend/
│   ├── pyproject.toml            # uv, ruff, mypy, pytest
│   ├── Dockerfile                # include pandoc, libreoffice-writer-nogui, fonts
│   ├── app/
│   │   ├── main.py               # crea l'app, monta i router e i file statici del frontend
│   │   ├── config.py             # impostazioni (pydantic-settings), percorso workspaces, endpoint LLM
│   │   ├── api/                  # router sottili: validano input e chiamano core
│   │   │   ├── projects.py  files.py  translation.py  glossary.py
│   │   │   ├── templates.py  export.py  importer.py  settings.py  events.py (WebSocket)
│   │   ├── core/                 # logica pura, testabile, senza FastAPI
│   │   │   ├── workspace/        # manifest.py, tree.py, frontmatter.py, ordering.py, assets.py
│   │   │   ├── segmentation/     # segmenter.py, protect.py (segnaposto), assembler.py
│   │   │   ├── translation/      # engine.py, llm_client.py, prompts/*.md, glossary_check.py, store.py, tm.py
│   │   │   ├── templates/        # analyze.py, style_map.py, fill.py, compose.py, wizard.py
│   │   │   ├── export/           # combine.py, pandoc.py, office.py, diagrams.py, filters/*.lua
│   │   │   └── importer/         # docx_to_md.py, align.py, back_translate.py
│   │   ├── jobs/                 # queue.py (interfaccia), memory_queue.py, scheduler.py
│   │   └── schemas/              # modelli Pydantic dell'API
│   └── tests/
│       ├── unit/  integration/
│       └── fixtures/             # progetto-mini/, template-aziendale.docx, docx-revisionato.docx
├── frontend/
│   ├── package.json  vite.config.ts  biome.json  tsconfig.json
│   └── src/
│       ├── app/                  # App.tsx, layout, routing (TanStack Router)
│       ├── features/
│       │   ├── tree/  editor/  preview/  review/  glossary/
│       │   ├── templates/  export/  import/  settings/  command-palette/
│       ├── components/ui/        # componenti base (Radix + Tailwind)
│       ├── lib/                  # api.ts (client tipizzato), ws.ts, shortcuts.ts, i18n.ts
│       ├── i18n/it.json  en.json
│       └── styles/tokens.css
│   └── tests/e2e/                # Playwright
├── tools/
│   ├── fake-llm/                 # server OpenAI-compatibile deterministico per test
│   └── check-licenses.py
└── examples/progetto-esempio/    # workspace dimostrativo completo
```

## Formato del workspace (contratto stabile)

```
manuale-impianto/
├── progetto.yaml
├── glossario.yaml
├── template/
│   ├── manuale.docx
│   └── manuale.yaml              # mappatura stili e campi, generata dall'analisi e modificabile
├── capitoli/
│   ├── 01-introduzione/
│   │   ├── _capitolo.yaml        # facoltativo: title, note, tono
│   │   ├── 01-scopo.md
│   │   ├── 02-ambito.md
│   │   └── img/schema-generale.png
│   └── 02-installazione/
│       ├── 01-requisiti.md
│       └── 02-procedura/         # sottocapitolo
│           └── 01-montaggio.md
├── .traduco/                     # generato; versionabile tranne cache/
│   ├── segmenti/en/capitoli/01-introduzione/01-scopo.json
│   ├── export/                   # snapshot degli export, per l'import delle revisioni
│   ├── cache/                    # immagini dei diagrammi (in .gitignore)
│   └── tm.sqlite                 # memoria di traduzione (in .gitignore; esportabile in TMX)
└── build/                        # output degli export (in .gitignore)
```

### `progetto.yaml`

```yaml
nome: Manuale impianto X
lingua_sorgente: it
lingua_ufficiale: en          # tradotta in tempo reale
lingue_aggiuntive:            # facoltative, tradotte dal sorgente in background
  - codice: de
    tono: formale             # Sie
    base: sorgente            # sorgente | ufficiale (pivot, solo segmenti approvati)
    formato_date: dd.MM.yyyy
tono: formale                 # formale | neutro | informale (per la lingua ufficiale)
template_predefinito: manuale
metadati:                     # disponibili come {{campo}} nei template
  codice_documento: DOC-2026-014
  revisione: "02"
  cliente: ACME Ltd
  autore: Mario Rossi
  data: 2026-11-07
revisioni:                    # per {{REVISIONI}}
  - { rev: "01", data: 2026-09-15, descrizione: Prima emissione }
  - { rev: "02", data: 2026-11-07, descrizione: Aggiornato capitolo 2 }
metadati_da_tradurre: [descrizione]
llm:                          # facoltativo, sovrascrive le impostazioni globali
  modello: gemma4:e4b
```

### Front matter di una sezione

```markdown
---
title: Scopo del documento
tono: neutro                  # facoltativo
contesto: Pubblico di tecnici di manutenzione, frasi brevi.
traduci: true                 # false = la sezione viene esportata così com'è
---
```

### `glossario.yaml`

```yaml
- sorgente: offerta
  destinazione: { en: proposal }
  vietati: { en: [offer] }
  note: Termine contrattuale concordato con il cliente
- sorgente: ACME Pump
  non_tradurre: true
```

### File dei segmenti (`.traduco/segmenti/<lingua>/<percorso>.json`)

```json
{
  "source_file_hash": "sha256:…",
  "segments": [
    {
      "key": "p:3",
      "source_hash": "sha256:…",
      "kind": "paragraph",
      "target": "The purpose of this document is…",
      "origin": "mt",
      "status": "translated",
      "locked": false,
      "pending_target": null,
      "model": "gemma4:e4b",
      "prompt_version": "translate@3",
      "updated_at": "2026-11-07T08:30:00Z"
    }
  ]
}
```

- `origin`: `mt` (modello) · `tm` (memoria) · `manual` (autore) · `import` (da revisione cliente)
- `status`: `queued` · `translated` · `needs_review` · `approved` · `diverged` (modificato direttamente in
  destinazione, sorgente non riallineato per scelta dell'autore)
- Le lingue aggiuntive hanno ciascuna la propria cartella `segmenti/<lingua>/`; se `base: ufficiale`, un segmento
  aggiuntivo registra anche `pivot_hash` (hash del testo ufficiale usato) e diventa `needs_review` quando questo cambia
- `pending_target`: nuova proposta quando il sorgente di un segmento bloccato cambia (RF-24)
- JSON con chiavi ordinate e indentazione 2, per diff Git leggibili

## Pipeline di segmentazione

1. **Parsing** con `markdown-it-py` (plugin: tabelle, note, front matter, attributi) con mappe di riga.
2. **Segmenti** traducibili: titolo, paragrafo, elemento di elenco, cella di tabella, didascalia/alt di immagine,
   nota a piè di pagina, citazione. Non traducibili: codice, blocchi Mermaid, HTML grezzo, front matter (salvo `title`).
3. **Chiave** del segmento: tipo + indice ordinale nel file (`p:3`, `td:2:1:0`). **Riconciliazione** dopo una
   modifica: si allineano i vecchi e nuovi segmenti per `source_hash` (corrispondenza esatta), poi per posizione
   (difflib sulla sequenza di hash); un segmento conserva traduzione e blocco se il suo hash è invariato anche se si
   è spostato.
4. **Protezione**: prima dell'invio al modello, elementi inline non traducibili diventano segnaposto `⟦1⟧ ⟦2⟧`
   (codice inline, URL, link target, `{{campi}}`, voci non_tradurre, formattazione `**`/`_` come coppie
   `⟦b⟧…⟦/b⟧`). Dopo la traduzione si verifica che i segnaposto siano tutti presenti una volta sola e si ripristinano.
5. **Assemblaggio**: il file di destinazione si ricostruisce sostituendo il testo dei segmenti nel sorgente,
   preservando la struttura. Test di proprietà obbligatorio: assemblare con traduzione identità deve restituire un
   Markdown che renderizza in HTML identico al sorgente.

## Motore di traduzione

- **Coda con priorità**: 1) segmento in modifica (debounce 600 ms), 2) segmenti visibili nell'anteprima,
  3) resto del file aperto, 4) ritraduzioni in blocco. Le richieste per un segmento superate da una nuova modifica
  vengono annullate.
- **Prima del modello**: memoria di traduzione (corrispondenza esatta di segmenti approvati con stesso tono).
- **Prompt** (file in `core/translation/prompts/`, versionati con `prompt_version`):
  lingua sorgente e destinazione, tono, contesto della sezione, titolo della sezione, segmento precedente già tradotto,
  voci di glossario presenti nel segmento, regole sui segnaposto, "rispondi solo con la traduzione".
- **Parametri**: temperatura 0,2; `max_tokens` = 3 × lunghezza sorgente; timeout 60 s; 2 richieste parallele
  configurabili.
- **Validazione**: segnaposto integri, glossario rispettato (termine imposto presente quando il sorgente lo contiene,
  nessun termine vietato; confronto case-insensitive su forme singolare/plurale), lunghezza plausibile (0,5–2,5× il
  sorgente). Se fallisce: un nuovo tentativo con istruzione correttiva esplicita; se fallisce ancora →
  `needs_review` con motivo.
- **Istruzione su segmento** (RF-26): prompt di revisione con sorgente, traduzione attuale e istruzione; il
  risultato diventa `manual`+`locked` solo dopo conferma dell'utente.
- **Eventi** via WebSocket `/api/projects/{id}/events`: `segment.updated`, `segment.queued`, `job.progress`,
  `file.changed`, `llm.status`.

## Pipeline dei template

**Analisi** (`templates/analyze.py`, con `python-docx`):
- Elenco degli stili (per `styleId` e nome, perché i nomi sono localizzati: "Titolo 1" = `Heading1`).
- Ricerca dei segnaposto `{{campo}}` in corpo, intestazioni, piè di pagina e caselle di testo, ricostruendo il testo
  quando Word lo spezza in più *run*.
- Posizione del segnaposto `{{CONTENUTO}}` (obbligatorio; se assente l'analisi propone di aggiungerlo dopo la
  copertina) e opzionale `{{REVISIONI}}`, `{{SOMMARIO}}`.
- Proposta di mappatura stili salvata in `template/<nome>.yaml`:

```yaml
contenuto: "{{CONTENUTO}}"
stili:
  titolo_1: Heading1
  titolo_2: Heading2
  corpo: BodyText
  didascalia: Caption
  tabella: AziendaTabella
  elenco_puntato: ListBullet
  codice: SourceCode
numerazione_titoli: true
campi_mancanti_ammessi: false
```

**Export DOCX** (`export/`):
1. `combine.py`: unisce le sezioni nell'ordine, nella lingua scelta, riscrivendo percorsi immagini e link interni
   (ancore uniche per sezione), con un titolo di livello 1 per capitolo.
2. `diagrams.py`: blocchi Mermaid → PNG. Il rendering avviene **nel browser** (mermaid.js) quando il blocco viene
   salvato; l'immagine (SVG + PNG 2×) è inviata al backend e salvata in `.traduco/cache/` per hash del codice.
   All'export, un diagramma senza immagine in cache blocca l'export con un messaggio chiaro (aprire la sezione).
   Le etichette dei diagrammi si traducono come segmenti di tipo `diagram_label`.
3. `pandoc.py`: Markdown → DOCX con `--reference-doc` = template, filtro Lua che applica gli stili mappati
   (`custom-style`) e le didascalie di tabelle/figure.
4. `compose.py`: apre il template, compila `{{campi}}` dai metadati (tradotti se indicati), genera la tabella revisioni,
   inserisce il corpo al posto di `{{CONTENUTO}}` con `docxcompose` (MIT), imposta `w:updateFields` così Word
   aggiorna sommario e numerazioni all'apertura.
5. `office.py`: PDF e ODT con LibreOffice headless a partire dal DOCX finale (fedeltà al template); aggiorna i campi
   prima della conversione con una macro.
6. Salva uno **snapshot** in `.traduco/export/<timestamp>/` (Markdown combinato + mappa segmento → sezione) per l'import.

**Procedura guidata** (`templates/wizard.py`): parte dal reference.docx di Pandoc, applica caratteri, colori, margini,
logo in intestazione, piè di pagina con numero pagina, pagina di copertina con i campi scelti e il segnaposto
`{{CONTENUTO}}`.

## Pipeline di import delle revisioni

1. DOCX → Markdown con Pandoc (`--track-changes=all` per conservare inserimenti/cancellazioni di Word).
2. Rimozione delle parti del template (copertina, tabella revisioni) tramite lo snapshot dell'export.
3. Allineamento con lo snapshot: segmentazione di entrambi e confronto sequenziale (difflib) → elenco di
   segmenti modificati, aggiunti, eliminati, con la sezione di provenienza.
4. Per ogni modifica: retro-traduzione nella lingua sorgente e proposta all'autore (testo sorgente attuale →
   proposta), insieme alla nuova traduzione del cliente da adottare come `import`+`locked`.
5. L'autore accetta o rifiuta ogni proposta; nulla viene applicato senza conferma.

## Editor a due modalità

- **Una sola fonte**: il file `.md` normalizzato. Le due modalità sono viste diverse dello stesso testo; il cambio
  di modalità salva, ricarica il testo nell'altra vista e mantiene la posizione del cursore per blocco.
- **Forma canonica** (fissata in `frontend/src/lib/markdown/canonical.ts` e replicata in un test backend):
  titoli ATX `#`, elenchi con `-`, enfasi `_corsivo_` e `**grassetto**`, tabelle pipe allineate, una riga vuota tra
  blocchi, a capo LF, nessuno spazio finale.
- **Test di round-trip obbligatori** su tutte le fixture: Markdown → Documento → Markdown restituisce lo stesso testo
  canonico; ogni elemento di RF-11 ha un caso di test.
- Elementi non rappresentabili in modalità Documento (HTML grezzo, sintassi sconosciuta) sono mostrati come blocchi
  protetti "Markdown" modificabili come testo, mai scartati.

## Installazione e avvio

### Perché non Docker per l'utente desktop
Docker Desktop su Windows richiede installazione con privilegi, virtualizzazione attiva e, nelle aziende più grandi,
un abbonamento. Il launcher nativo evita tutto questo. Docker resta l'opzione per i server (`docker-compose.yml`).

### Struttura
- `start.sh` (bash, Linux/macOS) e `start.cmd` (Windows, richiama `powershell -NoProfile -ExecutionPolicy Bypass`
  su `launcher/bootstrap.ps1`) sono **bootstrap sottili** (< 40 righe): installano **uv** nella cartella
  `.runtime/uv` se manca (installer ufficiale con `UV_INSTALL_DIR`, nessun privilegio), poi eseguono
  `uv run --project launcher python -m launcher <argomenti>`. uv scarica da sé Python 3.12.
- Tutta la logica sta nel **launcher Python**, unico per tutti i sistemi.

### Passi del launcher (idempotenti, saltati se già fatti)
1. **Controlli preliminari**: sistema operativo e architettura (x64, arm64), spazio su disco, porta libera
   (8000, altrimenti la prima libera fino a 8100), proxy.
2. **Dipendenze backend**: `uv sync` del progetto `backend` nella `.venv` locale.
3. **Pandoc portabile**: scaricato da GitHub Releases nella versione fissata in `manifest.toml`, verificato con
   SHA-256, estratto in `.runtime/pandoc/`.
4. **Frontend**: se `frontend/dist` esiste (pacchetto di rilascio) si usa; altrimenti (clone dei sorgenti) Node.js
   portabile in `.runtime/node/` (versione e SHA-256 fissati), `corepack pnpm install --frozen-lockfile`, build.
5. **Hardware**: RAM totale, GPU NVIDIA (`nvidia-smi`), AMD/Apple Silicon; scelta del modello:

   | Condizione | Modello predefinito |
   | --- | --- |
   | RAM < 12 GB, nessuna GPU | Gemma 4 E2B (avviso: qualità ridotta) |
   | RAM ≥ 12 GB o GPU ≥ 6 GB | Gemma 4 E4B |
   | GPU ≥ 20 GB | Gemma 4 26B A4B |

   I nomi dei tag Ollama stanno in `manifest.toml`, non nel codice.
6. **Ollama**: se c'è già un endpoint configurato e raggiungibile, si usa. Altrimenti si cerca Ollama in esecuzione
   o installato; se manca, si chiede conferma e si installa (Windows: `winget install Ollama.Ollama`, con fallback
   all'installer ufficiale; Linux: script ufficiale, che richiede `sudo`, mostrandolo all'utente; macOS:
   applicazione ufficiale). Rifiutando, l'app parte comunque e la UI mostra come configurare un endpoint.
7. **Modello**: `ollama pull` con barra di avanzamento; lo stato viene salvato per non ripetere il controllo.
8. **LibreOffice**: solo rilevamento (percorsi standard e `soffice` nel PATH). Assente → PDF/ODT disattivati nella UI
   con istruzioni; mai installato automaticamente.
9. **Avvio**: backend con uvicorn, attesa di `/api/health`, apertura del browser, log in `.runtime/logs/`.
   `Ctrl+C` (o chiusura della finestra) ferma tutto in modo pulito; Ollama non viene fermato se era già attivo.

### Opzioni
`--update` (aggiorna dipendenze e frontend), `--model <tag>`, `--port <n>`, `--no-browser`, `--offline`
(nessun download: fallisce con messaggio se manca qualcosa), `--reset` (ricrea `.runtime/`, non tocca i progetti),
`--workspace <cartella>` (dove stanno i progetti; predefinito `~/Traduco`).

### Requisiti di qualità
- Output a passi numerati (`[3/9] Download di Pandoc… 42%`), in italiano o inglese secondo la lingua di sistema.
- Ogni errore ha un codice, un messaggio con la soluzione e il percorso del log.
- Download con ripresa, 3 tentativi, timeout, rispetto di `HTTPS_PROXY`/`HTTP_PROXY`, verifica SHA-256 sempre.
- Nessun privilegio di amministratore, tranne l'installazione di Ollama su conferma.
- **Pacchetto offline** (`make bundle-offline OS=windows|linux`): ZIP con Python, wheel, Pandoc, frontend compilato e,
  facoltativamente, i pesi del modello; il launcher in modalità `--offline` usa solo il contenuto del pacchetto.
- **CI**: job di "avvio pulito" su `ubuntu-latest` e `windows-latest` che esegue lo script con un fake Ollama e
  verifica che `/api/health` risponda.

## API REST (prefisso `/api`)

| Metodo e percorso | Scopo |
| --- | --- |
| `GET/POST /projects` | Elenco progetti, creazione (vuoto o da esempio) |
| `GET/PATCH /projects/{id}` | Leggi/modifica `progetto.yaml` |
| `GET /projects/{id}/tree` | Albero capitoli/sezioni con titoli e stato traduzione |
| `POST /projects/{id}/nodes` · `PATCH` · `DELETE` | Crea, rinomina/sposta/riordina, elimina capitolo o sezione |
| `GET/PUT /projects/{id}/files?path=` | Leggi/salva una sezione (`If-Match` con hash per conflitti) |
| `POST /projects/{id}/assets` | Carica un'immagine nel capitolo |
| `GET /projects/{id}/translation?path=&lang=` | Segmenti tradotti di una sezione |
| `PUT /projects/{id}/segments/{key}?path=&lang=` | Modifica manuale, blocco, stato |
| `POST /projects/{id}/segments/{key}/instruct` | Istruzione in linguaggio naturale |
| `POST /projects/{id}/retranslate` | Ritraduzione di sezione/capitolo/progetto |
| `GET/PUT /projects/{id}/glossary` | Glossario |
| `GET/POST /projects/{id}/templates` · `GET/PUT …/{name}` | Elenco, upload + analisi, mappatura |
| `POST /projects/{id}/templates/wizard` | Crea template guidato |
| `POST /projects/{id}/export` | `{formato, lingua, ambito, template}` → job; download a fine job |
| `POST /projects/{id}/import` | Carica DOCX revisionato → job → proposte |
| `GET/POST /projects/{id}/import/{job}/proposals` | Elenco proposte, accetta/rifiuta |
| `GET/PUT /settings` | Endpoint LLM, modello, parallelismo, LanguageTool |
| `GET /llm/status` | Raggiungibilità e modelli disponibili |
| `WS /projects/{id}/events` | Eventi in tempo reale |

Errori sempre nel formato `{"error": {"code": "…", "message": "…", "details": {…}}}`.

## Stack

| Livello | Scelta | Licenza |
| --- | --- | --- |
| Frontend | React 19, TypeScript, Vite, TanStack Router + Query, Zustand | MIT |
| UI | Tailwind CSS 4, Radix UI, lucide-react, cmdk (palette comandi) | MIT |
| Editor Markdown | CodeMirror 6 + @codemirror/lang-markdown | MIT |
| Editor Documento | Milkdown (ProseMirror + remark, nativo Markdown) con plugin GFM, note, tabelle | MIT |
| Normalizzazione Markdown | remark-stringify con impostazioni fisse, usato da entrambe le modalità al salvataggio | MIT |
| Diagrammi | mermaid.js nel browser | MIT |
| Anteprima | markdown-it (stesse regole del backend) | MIT |
| Drag & drop | dnd-kit | MIT |
| Backend | Python 3.12, FastAPI, Pydantic v2, uvicorn | MIT/BSD |
| Markdown | markdown-it-py + mdit-py-plugins, python-frontmatter, ruamel.yaml | MIT |
| DOCX | python-docx, docxcompose | MIT |
| LLM | httpx verso API compatibile OpenAI | BSD |
| Storage | file system + SQLite (sqlite3 standard) | — |
| File watching | watchfiles | MIT |
| Esterni | Pandoc ≥ 3.5 (portabile, scaricato dal launcher), LibreOffice ≥ 24 (facoltativo) | GPL/MPL, come processi |
| Launcher | Python standard library + `rich` per l'avanzamento; uv per Python e dipendenze | MIT/Apache |
| Test | pytest, hypothesis, vitest, Playwright | MIT/MPL/Apache |
| Modello di riferimento | Gemma 4 E4B (Apache-2.0) su Ollama | Apache-2.0 |
