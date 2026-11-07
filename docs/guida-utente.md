# Guida utente di Traduco

Traduco serve a scrivere un documento nella tua lingua e ottenere, in tempo reale, la versione tradotta
nella lingua ufficiale (per esempio l'inglese), con il glossario, il tono e il template Word della tua azienda.
Funziona **sul tuo computer**: nessun testo esce se il modello di traduzione è locale.

## 1. Avvio

- **Linux / macOS**: `./start.sh` · **Windows**: doppio clic su `start.cmd`.
- Al primo avvio lo script installa tutto da solo (Python, Pandoc, il modello adatto al computer) e apre il browser.
  Dagli avvii successivi parte in pochi secondi. Non servono permessi di amministratore.
- Il modello si scarica **in sottofondo**: puoi già scrivere. In alto a destra vedi se il modello è attivo.

**Quale motore per il modello?**

| Situazione | Cosa fare |
| --- | --- |
| Hai (o puoi installare) Ollama | Niente: Traduco lo usa. |
| Non puoi o non vuoi installare Ollama, o non hai una scheda grafica | `./start.sh --llm builtin`: scarica un piccolo programma (llama.cpp) e il modello Gemma 4 E2B (circa 3 GB). Sul solo processore è più lento. |
| Hai un altro server compatibile OpenAI (rete, cloud) | Impostazioni → indirizzo del server. Se è un servizio esterno, i testi escono dal tuo computer. |
| Nessun modello | L'app funziona lo stesso: scrivi, organizzi, esporti nella lingua sorgente. La traduzione resta in attesa. |

Opzioni utili: `--update`, `--model <nome>`, `--no-browser`, `--port <n>`, `--offline`, `--reset`,
`--workspace <cartella>`, `--yes`, `--llm builtin|ollama|auto`.

## 2. Progetti, capitoli, sezioni

- Un **progetto** è una cartella (di norma `~/Traduco/<nome>`) con `progetto.yaml`, i capitoli e i tuoi file Markdown.
  Funziona bene con Git: i file sono testo semplice.
- Crea un progetto dalla schermata iniziale, anche da uno **scheletro** (struttura prescritta da una norma o da un modello:
  specifica dei requisiti SRS, progetto architetturale ADD, progetto di dettaglio DDD, stile ECSS). L'albero a sinistra mostra
  capitoli e sezioni; trascina per riordinare. Lo scheletro segnala sezioni mancanti o fuori ordine.
- Ogni **sezione** è un file `.md`. Il titolo è nel front matter o nel primo titolo.

## 3. Scrivere

- Due modi, con il pulsante in alto nell'editor: **Documento** (si vede il testo formattato) e **Markdown** (si vede il testo
  semplice). Il contenuto è lo stesso.
- Barra degli strumenti: titoli, grassetto, corsivo, elenchi, **tabelle** (il menu con l'icona della tabella aggiunge o toglie
  righe e colonne e allinea la colonna sotto il cursore), immagini (anche incollate), codice, note a piè di pagina,
  **diagrammi Mermaid** (disegnati nell'anteprima e nell'export).
- Digita `/` per il menu rapido: comandi di formattazione e i tuoi **snippet** (vedi sotto).
- Il salvataggio è automatico. Se il file cambia fuori da Traduco (per esempio con Git), l'editor lo ricarica quando non hai
  modifiche in sospeso.
- Modalità: **Scrittura**, **Revisione**, **Concentrazione** (`Ctrl/⌘ + 1/2/3`).

## 4. La traduzione

A destra vedi l'**anteprima tradotta**, aggiornata mentre scrivi. Il testo è diviso in **segmenti** (paragrafi, voci di
elenco…): cambia un paragrafo e solo quello viene tradotto di nuovo.

Passando il mouse su un paragrafo tradotto compare una barra:

| Pulsante | Cosa fa |
| --- | --- |
| Assistente di scrittura | Corregge, riformula, accorcia, semplifica o cambia tono **il testo sorgente**. Vedi la differenza e la applichi tu. |
| Modifica (E) | Scrivi a mano la traduzione. Il segmento si **blocca**: non verrà più sovrascritto. |
| Istruzione (I) | Chiedi al modello di **riscrivere la traduzione** (più formale, più conciso…). Vedi la proposta e la usi tu. Riscrive soltanto: richieste di aggiungere contenuto nuovo vengono rifiutate. |
| Memoria di traduzione | Frasi simili già approvate, con la percentuale di somiglianza. |
| Blocca (L) / Approva (A) | Blocca il segmento; segnalo come rivisto. |

Se cambi la traduzione a mano, il sorgente non corrisponde più: Traduco ti offre di **proporre un aggiornamento del sorgente**
(retro-traduzione) oppure di ignorare (il segmento resta segnato come "Modificato in destinazione").

Altri strumenti:

- **Tono** del progetto (formale, neutro, informale), cambiabile per sezione.
- **Nota di contesto** per sezione: aiuta il modello.
- **Ritraduci** sezione, capitolo o progetto.
- Il **mostra sorgente** (`Ctrl/⌘ + Shift + P`) alterna traduzione e testo originale.

### Glossario

Pulsante **Glossario** nella barra a sinistra: per ogni termine una traduzione **imposta**, termini **vietati** e l'opzione "non
tradurre" (sigle, nomi di prodotto). Se il modello viola il glossario il segmento finisce in "da rivedere" con il motivo.
Puoi **importare ed esportare** il glossario in CSV e TBX; l'importazione unisce le voci e non sovrascrive le tue.

### Memoria di traduzione

Le traduzioni che **approvi** o scrivi a mano finiscono nella memoria (`.traduco/tm.sqlite`, non nel Git). La stessa frase,
in un'altra sezione, viene riempita subito senza chiamare il modello; le frasi simili sono suggerite dal pulsante
"Memoria di traduzione". Esporta o importa la memoria in **TMX** dalla palette comandi.

### Revisione

`F8` salta al prossimo segmento da rivedere; la modalità **Revisione** (`Ctrl/⌘ + 2`) li elenca con il motivo (glossario,
modello non raggiungibile, sorgente cambiato su un segmento bloccato…). Prima di esportare Traduco ti dice quanti ce ne sono.

### Più lingue

Il menu con il globo, sopra l'anteprima, mostra le lingue di destinazione e **a che punto** è la traduzione di ciascuna.
**Lingue del progetto…** aggiunge lingue aggiuntive (tedesco, francese…): si traducono **dal sorgente** in sottofondo, dopo la
lingua ufficiale, ciascuna con il proprio tono e formato di data. Ogni lingua ha le sue correzioni, il suo glossario
(`destinazione` per lingua) e la sua memoria. La scelta del tono e della base "ufficiale come pivot" è nel
`progetto.yaml`; il pivot non è ancora attivo.

### Controllo della sezione e ortografia

L'icona con la lista di controllo (barra dell'editor) esegue il **controllo della sezione**: errori, ambiguità, incoerenze,
aderenza allo scheletro; con l'opzione "requisiti" anche una sola prescrizione per frase, uso di "shall", parole vaghe.
Ogni proposta si applica o si ignora. Se hai un server **LanguageTool** tuo (`docker compose --profile languagetool up` e
`TRADUCO_LANGUAGETOOL_URL`), nello stesso pannello compare il **controllo ortografico e grammaticale** del sorgente.

## 5. Cercare e muoversi

- `Ctrl/⌘ + K`: **palette comandi**. Scrivi poche lettere per aprire una sezione o eseguire un'azione (esporta, importa,
  glossario, template, emissioni, tono, lingua, ritraduci…).
- `Ctrl/⌘ + Shift + F`: **cerca nel testo del progetto**, nel sorgente e nelle traduzioni (senza badare a maiuscole e accenti).
- `Alt + ↑ / ↓`: sezione precedente / successiva. `?`: elenco di tutte le scorciatoie.

## 6. Esportare

Pulsante **Esporta** (o `Ctrl/⌘ + E` per ripetere l'ultima scelta). Scegli cosa (sezione, capitolo, progetto), la lingua e il
formato:

| Formato | Note |
| --- | --- |
| **Word (.docx)** | Usa il tuo **template**: copertina, intestazioni, indice, tabella delle revisioni, stili. |
| **PDF, ODT** | Servono LibreOffice installato; indice e campi sono aggiornati. |
| **Pagina web (.html)** | Un solo file con indice, ricerca e immagini incluse: si apre con un doppio clic, senza server. |
| **E-book (.epub)**, **Markdown** | Markdown diventa uno zip se ci sono immagini. |
| **Due colonne** | Lingua sorgente a sinistra, traduzione a destra, per chi deve confrontarle. Codice e tabelle non sono inclusi. |

La lingua può essere la **ufficiale**, il **sorgente** o una lingua **aggiuntiva**.

### Template

Pulsante **Template**: carica un `.docx` della tua azienda con i segnaposto `{{CONTENUTO}}`, `{{SOMMARIO}}`, `{{REVISIONI}}`
e i campi `{{nome_campo}}`, e collega i ruoli (titolo 1, corpo, tabella…) ai suoi stili. Senza un template puoi **crearne uno**
con la procedura guidata in 4 passi (aspetto, copertina, intestazione e piè di pagina, contenuti). I valori dei campi e la
**storia delle revisioni** si compilano nello stesso pannello.

## 7. Il documento torna dal cliente

**Esporta → Importa un documento rivisto…** Carica il Word restituito (anche con le revisioni di Word attive). Traduco lo
confronta con l'export da cui deriva e propone **cosa è cambiato**, sezione per sezione, nella lingua sorgente. Per ogni
proposta: **Accetta**, **Rifiuta** o correggi il testo. Accettando, il testo del cliente resta come traduzione bloccata.
Aggiunte o eliminazioni dentro le tabelle vanno fatte a mano.

## 8. Emissioni, confronto e commenti

- **Emissioni**: "congela" il documento con un numero e una data (copia di entrambe le lingue, in `.traduco/emissioni/`,
  adatta a Git). Ripristina una sezione da un'emissione precedente.
- **Confronto**: tra due emissioni, o con la bozza, parola per parola, in sorgente o in traduzione; si passa da un cambio al
  successivo.
- **Tabella dei cambiamenti**: il modello scrive una riga per sezione cambiata rispetto all'emissione precedente; la correggi
  e la usi nella tabella delle revisioni del documento.
- **Commenti**: thread su un segmento, aperti o risolti, salvati accanto al documento (non nel testo) e legati al segmento
  anche se il testo vicino cambia.

## 9. Requisiti e snippet

- **Requisiti**: un identificativo come `FOO-REQ-00042` all'inizio di un paragrafo definisce un requisito; citarlo altrove è
  un riferimento. Il pannello segnala definizioni doppie, riferimenti a requisiti inesistenti e requisiti mai citati.
- **Snippet**: file `snippet.yaml` del progetto (si modifica da `/` → "Modifica gli snippet…"). Esempio:

  ```yaml
  contatori:
    REQ: { prefisso: "FOO-REQ-", cifre: 5 }
  snippet:
    - alias: req
      descrizione: Nuovo requisito
      testo: "**{{contatore:REQ}}** Il sistema deve ${1:fare qualcosa}."
  ```

  Digita `/req`: inserisce `FOO-REQ-00001`, la volta dopo `…00002`, anche dopo un riavvio (i contatori sono in
  `.traduco/contatori.json`). Macro disponibili: `{{contatore:NOME}}`, `{{data}}`, `{{titolo}}`, `{{progetto}}`.

## 10. Se qualcosa non va

| Sintomo | Che fare |
| --- | --- |
| "Modello non raggiungibile" | Controlla Impostazioni → indirizzo del server; con Ollama verifica che sia in esecuzione. Scrivere continua a funzionare. |
| La traduzione è lenta | Sul solo processore è normale: usa un modello più piccolo (`--model`) o un server con scheda grafica. |
| PDF/ODT non disponibili | Installa LibreOffice (libreoffice.org) e riavvia Traduco. |
| "Diagramma non valido" | Controlla la sintassi Mermaid; l'errore indica la riga. Dopo un aggiornamento ricarica la pagina. |
| L'export dice che mancano dei campi | Compila i campi nel pannello Template (o attiva "campi mancanti ammessi"). |
| Un errore con codice `E0xx` all'avvio | Il messaggio dice cosa fare; i dettagli sono in `.runtime/logs/`. |

I tuoi progetti non vengono mai toccati da `--reset`, che ricrea soltanto la cartella `.runtime/`.
