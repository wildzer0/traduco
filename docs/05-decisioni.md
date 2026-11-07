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
