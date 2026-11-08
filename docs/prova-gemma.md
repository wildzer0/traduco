# Provare Traduco con un documento grande e Gemma

Scopo: vedere come se la cava il modello vero su un documento realistico, misurando **tempo, qualità e rispetto del
glossario**, con Ollama e con il motore integrato. Finora Traduco è stato provato soprattutto con un finto modello: questa
prova serve a colmare quel buco.

## 1. Crea il documento

```bash
python3 tools/make-big-project.py                  # ~110 sezioni, ~21 000 parole, ~1 850 segmenti
python3 tools/make-big-project.py --sections 50    # più piccolo: ~750 segmenti
python3 tools/make-big-project.py --sections 17 --out ~/Traduco/manuale-prova   # per provare lo strumento
```

Crea `~/Traduco/manuale-grande` (cambia con `--out`; `--force` lo sostituisce). Il testo è un manuale italiano di una
stazione di pompaggio fittizia, generato da modelli di frase con un seme fisso: **lo stesso comando dà sempre lo stesso
documento**, quindi due prove si possono confrontare.

Contiene apposta ciò che mette in difficoltà un modello:

| Cosa | Perché |
| --- | --- |
| Termini del glossario con traduzione imposta e termini vietati ("pompa di mandata" → *discharge pump*, non *delivery pump*) | Si misura quante volte il modello ignora il glossario. |
| Nomi da non tradurre (`ACME Pump`, `SP-200`, `Supervisore`) | Devono restare identici. |
| Unità e numeri (`m³/h`, `±5 %`, `7,1 mm/s`, `N·m`) | Il separatore decimale e le unità non devono rompersi. |
| Procedure numerate, avvertenze in citazione, tabelle di dati e di allarmi | Struttura Markdown da conservare. |
| Codice in linea, campi `{{…}}`, note a piè di pagina, link tra sezioni | Segnaposto da proteggere. |
| Identificativi `SP-REQ-nnnnn` e riferimenti incrociati | Non vanno alterati; il pannello Requisiti li controlla. |
| Frasi che tornano identiche in molte sezioni | Mettono alla prova la **memoria di traduzione**. |
| Due diagrammi Mermaid (in "Schema di funzionamento" e in un "Allarmi e anomalie") | Per l'export vanno disegnati: apri quelle sezioni una volta. |

## 2. Avvia Traduco con il modello da provare

- **Ollama**: `./start.sh` (o `./start.sh --model gemma4:e4b`).
- **Motore integrato**: `./start.sh --llm builtin` (scarica circa 3 GB la prima volta).

Poi controlla in alto a destra che il modello sia attivo.

## 3. Misura

```bash
python3 tools/benchmark-translation.py --project manuale-grande
```

Lo script ritraduce tutto il progetto (i segmenti bloccati restano), segue l'avanzamento ogni 5 secondi e scrive
`benchmark-report.md`. Opzioni utili: `--url` (se non è la porta 8000), `--lang de` (una lingua aggiuntiva),
`--no-retranslate` (misura solo ciò che è già tradotto), `--sample 20`, `--timeout 7200`.

**Misura di riferimento** (sviluppatore, GPU RTX 5070 da 8 GB, Ollama, `gemma4:e4b`, versione da 17 sezioni = 172
segmenti e ~2 150 parole): **circa 50 secondi, 3,4 segmenti al secondo**, 0 segmenti da rivedere, 52 occorrenze di
termini imposti dal glossario tutte rispettate, nessun termine vietato. Il documento intero (~1 850 segmenti) dovrebbe
richiedere una decina di minuti con quella scheda; sul solo processore molto di più. Sono numeri di una sola macchina e di
un solo modello: i tuoi possono essere diversi, ed è proprio ciò che la prova serve a scoprire. Comincia dalla versione
da 50 sezioni.

### Cosa guarda il rapporto

- **Velocità**: segmenti al secondo e parole al minuto.
- **Esito**: quanti segmenti sono "tradotti" e quanti "da rivedere", con il motivo (glossario violato, segnaposto
  rotto, risposta vuota…).
- **Sospetti**: segmenti rimasti **identici al sorgente**, **troppo corti** o **troppo lunghi** (di solito: traduzione
  saltata, riassunta o inventata).
- **Casella Istruzione**: lo script chiede di *scrivere la ricetta della carbonara* (deve essere **rifiutato**) e di
  *rendere il testo più empatico* (deve produrre una proposta).
- **Campione da leggere**: coppie sorgente/traduzione casuali e i primi segmenti da rivedere.

## 4. Cosa fare a mano (10 minuti)

Il numero dice poco senza la lettura. Apri due o tre sezioni e controlla:

1. **Glossario**: "pompa di mandata" è sempre *discharge pump*? "collaudo" è *acceptance test*, mai *testing*?
2. **Nomi e codici**: `ACME Pump`, `SP-200`, `SP-REQ-…`, `P1100` sono identici al sorgente?
3. **Numeri e unità**: `7,1 mm/s` diventa `7.1 mm/s` (corretto in inglese) oppure si rompe?
4. **Tabelle e liste**: stesse righe e colonne? Le procedure restano numerate?
5. **Registro**: "Attenzione." → *Warning.* / *Caution.* coerente? Il tono è formale?
6. **Ripetizioni**: la stessa frase in due sezioni dà la stessa traduzione? (Approvane una e guarda se l'altra si riempie
   da sola: è la memoria di traduzione.)
7. **Export**: Esporta → Word (apri prima le due sezioni con i diagrammi). Il documento si apre, l'indice si aggiorna,
   i link tra sezioni funzionano?

Prova anche:

- una **lingua aggiuntiva** (menu col globo → Lingue del progetto… → `de`), con e senza "parti dalla traduzione ufficiale
  approvata", e `--lang de` nello script;
- la **casella Istruzione** su un paragrafo, con una richiesta lecita ("più conciso") e una fuori tema;
- il **documento che torna dal cliente**: esporta in Word, modifica tre paragrafi (uno con le revisioni attive),
  importalo da Esporta → Importa un documento rivisto…

## 5. Confronto tra motori

Per confrontare Ollama e motore integrato (o due modelli) usa lo **stesso** documento (stesso `--sections` e `--seed`) e
salva i rapporti con nomi diversi:

```bash
python3 tools/benchmark-translation.py --project manuale-grande --out rapporto-ollama-e4b.md
# riavvia con --llm builtin
python3 tools/benchmark-translation.py --project manuale-grande --out rapporto-builtin-e2b.md
```

Conta soprattutto: segmenti da rivedere, violazioni del glossario, identici al sorgente, e il tempo.

## 6. Quando qualcosa va storto

| Sintomo | Probabile causa |
| --- | --- |
| Lo script dice "the model server is not reachable" | Ollama o il motore integrato non sono attivi: guarda la barra in alto in Traduco. |
| Moltissimi "da rivedere" per glossario | Il modello ignora le regole: è un dato della prova, riportalo. |
| Segmenti vuoti o "empty translation" | Un modello che ragiona ha esaurito il budget: vedi ADR-034 (Traduco chiede già il ragionamento spento). |
| Molto lento | Normale sul solo processore; prova la versione piccola del documento o un modello più piccolo. |
| L'export dice che mancano dei diagrammi | Apri le sezioni "Schema di funzionamento" e il primo "Allarmi e anomalie". |

Se trovi qualcosa che non va, tieni il `benchmark-report.md` e i file in `.runtime/logs/`: dicono quasi sempre cosa è successo.
