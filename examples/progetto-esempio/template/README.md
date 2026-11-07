I template Word aziendali (`.docx`) e la relativa mappatura degli stili vanno in questa cartella.

`manuale.docx` è un template **sintetico** di esempio (copertina con logo, intestazione con il codice
documento, stili con nomi italiani, tabella con stile personalizzato) e `manuale.yaml` la sua mappatura.
Sostituiscili con il template della tua azienda dall'app (Template → Carica .docx).
Si rigenerano con `uv run --project backend python tools/make-example-template.py`.
