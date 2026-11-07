# AGENTS.md — Istruzioni per l'agent di sviluppo

Questo file è il punto di ingresso per qualunque agent (Claude Code, Codex, ecc.) che sviluppa il progetto.
`CLAUDE.md` contiene solo un rimando a questo file.

## Cos'è il progetto

**Traduco** (nome provvisorio) è una web app open source, per uso aziendale, che permette di scrivere documentazione
nella propria lingua madre (es. italiano) e di ottenere in tempo reale la versione nella lingua ufficiale di progetto
(es. inglese), con controllo su terminologia e tono, ed export in DOCX basato sui template Word dell'azienda.
Tutto gira in locale: la traduzione usa un LLM locale tramite API compatibile OpenAI (Ollama, llama.cpp, vLLM).

## Ordine di lettura dei documenti

1. `docs/01-requisiti.md` — cosa deve fare il prodotto (requisiti numerati RF/RNF)
2. `docs/02-architettura.md` — come è fatto: componenti, formato del workspace, pipeline, API
3. `docs/03-ui.md` — come deve apparire e comportarsi l'interfaccia
4. `docs/04-piano.md` — milestone ordinate con task e criteri di accettazione: **è la tua lista di lavoro**
5. `docs/05-decisioni.md` — decisioni già prese (ADR) e domande aperte

Prima di iniziare una milestone rileggi la sezione corrispondente di requisiti e architettura.

## Come lavorare

- Procedi **una milestone alla volta**, nell'ordine di `docs/04-piano.md`. Non iniziare la successiva finché i criteri
  di accettazione della corrente non sono verificati da test.
- Spunta i task completati in `docs/04-piano.md` (`- [x]`) nello stesso commit che li completa.
- Per il codice del core (segmentazione, assemblaggio, glossario, template, import) scrivi **prima i test**.
- Ogni scelta tecnica non già coperta da `docs/05-decisioni.md` va registrata lì come nuovo ADR (breve: contesto,
  decisione, conseguenze). Se una decisione contraddice un documento, aggiorna il documento.
- Se sei bloccato da un'ambiguità di prodotto, scegli l'opzione più semplice e reversibile, registrala in
  "Domande aperte" di `docs/05-decisioni.md` e prosegui.
- Usa il server LLM finto (`tools/fake-llm`) per test e sviluppo: nessun test deve richiedere un modello reale.

## Comandi

| Comando | Effetto |
| --- | --- |
| `./start.sh` · `start.cmd` | **Avvio per l'utente finale** (Linux/macOS · Windows): installa tutto ciò che manca e apre l'app. Vedi `docs/02-architettura.md` § Installazione e avvio |
| `make setup` | Installa dipendenze backend (uv) e frontend (pnpm) |
| `make dev` | Avvia backend (porta 8000), frontend (5173) e fake-llm (11500) |
| `make test` | Test backend (pytest) e frontend (vitest) |
| `make e2e` | Test end-to-end (Playwright) con fake-llm |
| `make lint` | ruff + mypy (backend), biome + tsc (frontend) |
| `make licenses` | Verifica licenze delle dipendenze (fallisce se fuori lista) |
| `docker compose up` | Avvio completo, incluso Ollama opzionale (profilo `llm`) |

Se un comando non esiste ancora, crealo nel `Makefile` durante la milestone M0.

## Regole non negoziabili

1. **Nessuna chiamata di rete esterna** nel codice di runtime, salvo l'endpoint LLM configurato dall'utente.
   Niente telemetria, CDN, font remoti: tutti gli asset sono inclusi nel build.
2. **Licenze**: dipendenze solo MIT, BSD, Apache-2.0, ISC, MPL-2.0, PostgreSQL, Zlib (più equivalenti permissive: PSF-2.0, 0BSD, Unlicense, BlueOak-1.0.0, CC0-1.0, vedi ADR-019;
   OFL-1.1 solo per i file font, ADR-013). Software GPL/LGPL (Pandoc,
   LibreOffice) solo come **eseguibili esterni** invocati via processo, mai importati come librerie.
   Il progetto è rilasciato sotto Apache-2.0.
3. **Il sorgente è la verità**: i file `.md` nella lingua sorgente non vengono mai modificati dal motore di traduzione.
   Le traduzioni vivono in `.traduco/` (vedi architettura).
4. **Le correzioni manuali sono sacre**: un segmento bloccato non viene mai sovrascritto automaticamente.
5. **Il file del workspace deve restare leggibile e versionabile con Git**: formati testuali (Markdown, YAML, JSON
   formattato con chiavi ordinate), niente binari tranne immagini e template `.docx`.
6. **UI minimale**: segui `docs/03-ui.md`. Non aggiungere pannelli, pulsanti o impostazioni non previsti senza
   registrarlo come ADR.
7. **Avvio con un solo comando**: `start.sh` e `start.cmd` devono funzionare su una macchina pulita senza diritti di
   amministratore (tranne per installare Ollama, previa conferma). Ogni nuova dipendenza di runtime va aggiunta al
   launcher nello stesso commit, e il test di avvio pulito in CI (Linux e Windows) deve restare verde.

## Convenzioni di codice

- Codice, nomi, commenti e messaggi di commit in **inglese**. Testi dell'interfaccia solo tramite file i18n
  (`frontend/src/i18n/it.json`, `en.json`), mai stringhe hardcoded.
- Backend: Python 3.12, FastAPI, Pydantic v2, type hints ovunque, `mypy --strict` sul pacchetto `app.core`.
- Frontend: TypeScript strict, React 19, componenti funzionali, stato server con TanStack Query, stato UI con Zustand.
- Commit in stile Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`), piccoli e coerenti.
- Nessun file oltre ~400 righe: spezza in moduli.

## Definition of Done (per ogni task)

- Codice + test che coprono il caso nominale e almeno un caso limite
- `make lint` e `make test` verdi
- Documentazione aggiornata se cambia un comportamento, un formato o un'API
- Per task di UI: verificato con test e2e o, in mancanza, descritto come verificarlo a mano nel commit
