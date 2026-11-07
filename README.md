# Traduco (nome provvisorio)

Scrivi la documentazione nella tua lingua. Consegnala nella lingua del progetto.

Traduco è un editor di documentazione open source, self-hosted, che:

- organizza i documenti come **capitoli (cartelle) e sezioni (file Markdown)**
- mostra accanto all'editor l'**anteprima tradotta in tempo reale** nella lingua ufficiale di progetto
- permette di correggere la traduzione, imporre la **terminologia** con un glossario e scegliere il **tono**
- esporta in **DOCX usando i template Word dell'azienda** (copertina, intestazioni, stili), oltre a PDF e ODT
- reimporta il DOCX revisionato dal cliente e mostra le modifiche **nella lingua dell'autore**
- funziona **interamente in locale** con un LLM open (es. Gemma 4) servito da Ollama, llama.cpp o vLLM

## Avvio rapido

**Windows**: doppio clic su `start.cmd`.
**Linux / macOS**: `./start.sh`

Al primo avvio lo script installa tutto ciò che serve nella cartella del programma (Python, Pandoc, il modello di
traduzione adatto al tuo computer) e apre il browser. Dagli avvii successivi parte in pochi secondi.
Nessun diritto di amministratore richiesto, tranne per installare Ollama se non è già presente (ti viene chiesto).

Opzioni: `--update` aggiorna, `--model <nome>` sceglie il modello, `--no-browser`, `--port <n>`, `--offline`
(non scarica nulla), `--reset` ricrea `.runtime/`, `--workspace <cartella>` (dove stanno i progetti), `--yes`
(risponde sì alle domande, ad esempio l'installazione di Ollama).

Il modello si scarica **in sottofondo**: puoi già scrivere mentre l'interfaccia mostra l'avanzamento. Se non vuoi
installare Ollama, l'app parte lo stesso e in Impostazioni puoi indicare un altro server compatibile OpenAI.
Per PDF e ODT serve LibreOffice (non viene installato da solo; il DOCX non lo richiede).

**Senza rete**: `make bundle-offline OS=linux` (o `windows`, sul rispettivo sistema) crea uno ZIP che si avvia con
`--offline`; con `MODEL=gemma4:e4b` include anche il modello se l'hai già scaricato con Ollama.

Per installazioni su server: `docker compose --profile llm up`. Per sviluppare: `make setup && make dev`.

## Documentazione per chi sviluppa

Vedi [AGENTS.md](AGENTS.md) e la cartella [docs/](docs/).

## Licenza

Apache-2.0
