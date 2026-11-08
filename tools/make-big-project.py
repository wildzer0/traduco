#!/usr/bin/env python3
"""Generate a large, realistic Traduco project to try the translation model on real material.

The project is an Italian technical manual for a fictional pumping station ("Stazione di pompaggio
SP-200"), made of the things a real manual has and that make a model's life hard: terms with an
imposed translation and forbidden ones, brand names that must stay as they are, units and numbers,
tables, numbered procedures, warnings, requirement identifiers with cross-references, footnotes,
inline code, links between sections, a Mermaid diagram, and sentences that come back again and again
(for the translation memory). The text is generated from templates with a fixed seed: the same
options always give the same project, so two runs of the model can be compared.

    python3 tools/make-big-project.py                 # ~110 sections, ~25 000 words, in ~/Traduco
    python3 tools/make-big-project.py --sections 50   # a smaller one
    python3 tools/make-big-project.py --out /tmp/x --force

Standard library only.
"""

from __future__ import annotations

import argparse
import random
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXED_SECTIONS = 12  # chapters that do not depend on the number of components
PER_COMPONENT_CHAPTERS = 5

# --- the plant -------------------------------------------------------------------------------

KINDS = [
    # name, code prefix, what it does, where it sits
    (
        "pompa di mandata",
        "P1",
        "porta l'acqua dal serbatoio di accumulo alla rete di distribuzione",
        "nel locale macchine",
    ),
    (
        "pompa di riserva",
        "P2",
        "subentra alla pompa di mandata in caso di guasto o di manutenzione",
        "nel locale macchine",
    ),
    (
        "valvola di intercettazione",
        "V1",
        "isola il tratto di tubazione su cui si interviene",
        "sulla linea di mandata",
    ),
    (
        "valvola di non ritorno",
        "V2",
        "impedisce il flusso inverso quando la pompa si ferma",
        "a valle di ogni pompa",
    ),
    (
        "sensore di pressione",
        "PT",
        "misura la pressione di mandata e la invia al quadro elettrico",
        "sul collettore",
    ),
    (
        "misuratore di portata",
        "FT",
        "misura la portata istantanea e il volume totale erogato",
        "sul collettore",
    ),
    (
        "inverter",
        "VF",
        "regola la velocità del motore in funzione della pressione richiesta",
        "nel quadro elettrico",
    ),
    (
        "quadro elettrico",
        "QE",
        "alimenta e protegge le utenze e ospita il sistema di controllo",
        "nel locale tecnico",
    ),
    (
        "serbatoio di accumulo",
        "SA",
        "garantisce la riserva d'acqua e smorza le variazioni di pressione",
        "all'esterno dell'edificio",
    ),
    (
        "filtro a cestello",
        "F1",
        "trattiene le impurità prima che raggiungano la pompa",
        "sulla linea di aspirazione",
    ),
    (
        "giunto antivibrante",
        "GV",
        "riduce la trasmissione delle vibrazioni alle tubazioni",
        "tra pompa e collettore",
    ),
    (
        "trasmettitore di livello",
        "LT",
        "segnala il livello del serbatoio e protegge la pompa dal funzionamento a secco",
        "nel serbatoio",
    ),
]

CHAPTERS_FIXED = [
    (
        "Introduzione",
        [
            "Scopo del manuale",
            "A chi si rivolge",
            "Come leggere questo documento",
            "Convenzioni e simboli",
        ],
    ),
    (
        "Descrizione generale",
        ["Descrizione della stazione", "Schema di funzionamento", "Elenco dei componenti"],
    ),
    (
        "Sicurezza",
        [
            "Regole generali di sicurezza",
            "Dispositivi di protezione individuale",
            "Lavori sugli impianti elettrici",
            "Gestione delle emergenze",
        ],
    ),
]
CHAPTERS_PER_COMPONENT = [
    ("Installazione", "Installazione della {name} {code}"),
    ("Messa in servizio", "Messa in servizio della {name} {code}"),
    ("Manutenzione", "Manutenzione ordinaria della {name} {code}"),
    ("Diagnostica e allarmi", "Allarmi e anomalie della {name} {code}"),
    ("Specifiche tecniche", "Dati tecnici della {name} {code}"),
]
CHAPTERS_CLOSING = [
    ("Appendici", ["Glossario dei termini", "Norme di riferimento", "Registro degli interventi"]),
]

GLOSSARY = [
    {
        "sorgente": "pompa di mandata",
        "destinazione": {"en": "discharge pump"},
        "vietati": {"en": ["delivery pump"]},
    },
    {
        "sorgente": "pompa di riserva",
        "destinazione": {"en": "standby pump"},
        "vietati": {"en": ["spare pump", "reserve pump"]},
    },
    {
        "sorgente": "valvola di intercettazione",
        "destinazione": {"en": "isolation valve"},
        "vietati": {"en": ["shut-off valve"]},
    },
    {
        "sorgente": "valvola di non ritorno",
        "destinazione": {"en": "check valve"},
        "vietati": {"en": ["non-return valve"]},
    },
    {
        "sorgente": "quadro elettrico",
        "destinazione": {"en": "electrical panel"},
        "vietati": {"en": ["switchboard", "control board"]},
    },
    {
        "sorgente": "messa in servizio",
        "destinazione": {"en": "commissioning"},
        "vietati": {"en": ["start-up"]},
    },
    {
        "sorgente": "collaudo",
        "destinazione": {"en": "acceptance test"},
        "vietati": {"en": ["testing"]},
    },
    {
        "sorgente": "serbatoio di accumulo",
        "destinazione": {"en": "storage tank"},
        "vietati": {"en": ["accumulation tank"]},
    },
    {"sorgente": "portata", "destinazione": {"en": "flow rate"}, "vietati": {"en": ["capacity"]}},
    {"sorgente": "mandata", "destinazione": {"en": "discharge"}, "vietati": {"en": ["delivery"]}},
    {"sorgente": "aspirazione", "destinazione": {"en": "suction"}, "vietati": {"en": ["intake"]}},
    {
        "sorgente": "offerta",
        "destinazione": {"en": "proposal"},
        "vietati": {"en": ["offer"]},
        "note": "Termine contrattuale",
    },
    {
        "sorgente": "manutentore",
        "destinazione": {"en": "maintenance technician"},
        "vietati": {"en": ["maintainer"]},
    },
    {"sorgente": "SP-200", "non_tradurre": True},
    {"sorgente": "ACME Pump", "non_tradurre": True},
    {"sorgente": "Supervisore", "non_tradurre": True, "note": "Nome del software di controllo"},
]

STANDARD_SENTENCES = [
    "Al termine dell'operazione registrare l'intervento nel registro di manutenzione.",
    "Usare sempre i dispositivi di protezione individuale previsti dal regolamento aziendale.",
    "In caso di dubbio interrompere il lavoro e contattare il responsabile dell'impianto.",
    "Non modificare i parametri di taratura senza l'autorizzazione scritta del costruttore.",
]

NORMS = [
    "EN 809:1998 - Pompe e gruppi di pompaggio per liquidi - Requisiti di sicurezza comuni.",
    "EN 60204-1 - Sicurezza del macchinario - Equipaggiamento elettrico delle macchine.",
    "EN ISO 9906 - Pompe rotodinamiche - Prove di accettazione idraulica.",
]


@dataclass
class Component:
    name: str
    code: str
    does: str
    where: str
    flow: int
    pressure: float
    power: float
    mass: int

    @property
    def label(self) -> str:
        return f"{self.name} {self.code}"


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:48]


def components(count: int, rng: random.Random) -> list[Component]:
    out: list[Component] = []
    for i in range(count):
        name, prefix, does, where = KINDS[i % len(KINDS)]
        out.append(
            Component(
                name,
                f"{prefix}{i // len(KINDS) + 1}{i % len(KINDS):02d}"[:6],
                does,
                where,
                flow=rng.choice([30, 45, 60, 80, 120, 160, 240]),
                pressure=rng.choice([2.5, 4.0, 6.0, 8.0, 10.0, 16.0]),
                power=rng.choice([0.75, 1.5, 3.0, 5.5, 7.5, 11.0, 15.0]),
                mass=rng.choice([18, 24, 35, 52, 78, 120, 190]),
            )
        )
    return out


# --- text blocks -----------------------------------------------------------------------------


class Writer:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.requirement = 0
        self.footnote = 0
        self.known: list[int] = []

    def req(self, text: str) -> str:
        self.requirement += 1
        self.known.append(self.requirement)
        return f"SP-REQ-{self.requirement:05d} {text}"

    def cite(self) -> str:
        return f"SP-REQ-{self.rng.choice(self.known):05d}" if self.known else "SP-REQ-00001"

    def standard(self) -> str:
        return self.rng.choice(STANDARD_SENTENCES)

    def intro(self, c: Component) -> str:
        return (
            f"La {c.label} {c.does}. È installata {c.where} della stazione **SP-200** "
            f"e lavora a una portata nominale di {c.flow} m³/h con una pressione di esercizio di "
            f"{str(c.pressure).replace('.', ',')} bar. Per le caratteristiche complete consultare "
            f"il capitolo sui dati tecnici."
        )

    def warning(self, c: Component) -> str:
        return (
            f"> **Attenzione.** Prima di intervenire sulla {c.label} sezionare l'alimentazione "
            f"elettrica e verificare l'assenza di tensione. {self.standard()}"
        )

    def steps(self, c: Component, kind: str) -> str:
        lists = {
            "install": [
                f"Verificare che il basamento sia in piano e capace di sostenere {c.mass} kg.",
                f"Posizionare la {c.name} rispettando le distanze minime indicate nel disegno di installazione.",
                "Collegare le tubazioni evitando tensioni sulle flange e interponendo, dove previsto, il giunto antivibrante.",
                "Serrare i bulloni in croce con la coppia riportata nella tabella dei dati tecnici.",
                "Eseguire il collegamento elettrico seguendo lo schema del **quadro elettrico** e verificare il senso di rotazione.",
                "Compilare la scheda di installazione e farla firmare dal responsabile dei lavori.",
            ],
            "commission": [
                "Controllare che tutte le valvole di intercettazione siano nella posizione indicata nella lista di verifica.",
                f"Riempire la {c.name} e sfiatare l'aria dalla parte alta del corpo.",
                "Avviare il **Supervisore** e selezionare la modalità manuale.",
                f"Avviare la {c.name} per pochi secondi e controllare assorbimento, rumore e vibrazioni.",
                "Portare lentamente la velocità al valore nominale osservando la pressione di mandata.",
                "Eseguire il **collaudo** secondo la procedura e registrare i valori misurati.",
                "Passare in modalità automatica e confermare la consegna dell'impianto al cliente.",
            ],
            "maintain": [
                f"Fermare la {c.name} e metterla in sicurezza secondo la procedura di blocco.",
                "Pulire le superfici esterne e controllare l'assenza di perdite.",
                "Verificare il serraggio dei bulloni e lo stato dei giunti.",
                "Controllare l'usura delle tenute meccaniche e sostituirle se la perdita supera il limite consentito.",
                "Lubrificare i cuscinetti con il grasso prescritto dal costruttore.",
                "Rimettere in servizio e verificare i valori di pressione e di corrente.",
            ],
        }
        items = lists[kind][: self.rng.randint(5, len(lists[kind]))]
        return "\n".join(f"{n}. {text}" for n, text in enumerate(items, 1))

    def table(self, c: Component) -> str:
        rows = [
            ("Portata nominale", str(c.flow), "m³/h"),
            ("Pressione di esercizio", str(c.pressure).replace(".", ","), "bar"),
            ("Potenza nominale", str(c.power).replace(".", ","), "kW"),
            ("Tensione di alimentazione", "400", "V"),
            ("Grado di protezione", "IP55", "-"),
            ("Massa", str(c.mass), "kg"),
        ]
        lines = ["| Parametro | Valore | Unità |", "| --- | ---: | --- |"]
        lines += [f"| {a} | {b} | {u} |" for a, b, u in rows]
        return "\n".join(lines)

    def requirements(self, c: Component, count: int = 3) -> str:
        pool = [
            f"La {c.label} deve mantenere la pressione di mandata entro ±5 % del valore impostato.",
            f"La {c.label} deve segnalare al **Supervisore** ogni anomalia entro 2 secondi.",
            f"Il manutentore deve poter isolare la {c.label} senza fermare l'intera stazione, come previsto da {self.cite()}.",
            f"L'arresto di emergenza della {c.label} deve portare l'impianto in condizione di sicurezza in meno di 3 secondi.",
            f"La {c.label} deve funzionare con temperature ambiente comprese tra 5 e 40 °C.",
        ]
        self.rng.shuffle(pool)
        return "\n\n".join(self.req(text) for text in pool[:count])

    def alarm_table(self, c: Component) -> str:
        rows = [
            (
                "A101",
                "Pressione di mandata bassa",
                "Verificare la presenza d'acqua e lo stato della valvola di intercettazione.",
            ),
            (
                "A102",
                "Pressione di mandata alta",
                "Controllare la taratura e che la linea non sia ostruita.",
            ),
            ("A110", "Sovraccarico del motore", "Ridurre la velocità e controllare i cuscinetti."),
            (
                "A120",
                "Funzionamento a secco",
                "Fermare la pompa e verificare il livello del serbatoio.",
            ),
            ("A130", "Perdita dalla tenuta", "Programmare la sostituzione della tenuta meccanica."),
        ]
        lines = ["| Codice | Significato | Azione consigliata |", "| --- | --- | --- |"]
        lines += [f"| `{a}` | {b} | {d} |" for a, b, d in rows[: self.rng.randint(3, 5)]]
        return "\n".join(lines)

    def footnote_ref(self) -> tuple[str, str]:
        self.footnote += 1
        norm = self.rng.choice(NORMS)
        return (
            f"Le prove devono essere eseguite secondo la norma di riferimento[^{self.footnote}].",
            f"[^{self.footnote}]: {norm}",
        )


MERMAID_FLOW = """```mermaid
flowchart LR
  A[Serbatoio di accumulo] --> B[Filtro a cestello]
  B --> C[Pompa di mandata]
  C --> D[Valvola di non ritorno]
  D --> E[Rete di distribuzione]
  F[Trasmettitore di livello] -.-> G[Quadro elettrico]
  G -.-> C
```"""

MERMAID_ALARM = """```mermaid
sequenceDiagram
  participant S as Sensore
  participant Q as Quadro elettrico
  participant U as Supervisore
  S->>Q: Valore fuori soglia
  Q->>U: Allarme con codice
  U->>U: Registra l'evento
```"""


# --- sections --------------------------------------------------------------------------------


def fixed_section(w: Writer, title: str, chapter_dir: str, comps: list[Component]) -> str:
    c = comps[0]
    blocks = [f"# {title}"]
    if title == "Scopo del manuale":
        blocks += [
            "Questo manuale descrive l'installazione, la **messa in servizio**, l'uso e la manutenzione della stazione di pompaggio **SP-200**, "
            "prodotta da **ACME Pump**. Il codice di questo documento è {{codice_documento}}, revisione {{revisione}}.",
            "Il manuale fa parte della documentazione consegnata con l'**offerta** e deve essere conservato in prossimità dell'impianto per tutta la sua vita utile.",
            w.standard(),
        ]
    elif title == "Schema di funzionamento":
        blocks += [
            "L'acqua viene prelevata dal serbatoio di accumulo, attraversa il filtro e raggiunge la **pompa di mandata**; a valle della pompa la valvola di non ritorno impedisce il flusso inverso.",
            MERMAID_FLOW,
            "Il livello del serbatoio e la pressione di mandata sono letti da due trasmettitori e inviati al quadro elettrico, che regola la velocità della pompa.",
        ]
    elif title == "Elenco dei componenti":
        lines = ["| Codice | Componente | Posizione |", "| --- | --- | --- |"]
        lines += [f"| `{k.code}` | {k.name} | {k.where} |" for k in comps[: min(len(comps), 14)]]
        blocks += [
            "I componenti principali della stazione sono elencati nella tabella seguente.",
            "\n".join(lines),
        ]
    elif "emergenze" in title:
        blocks += [
            "In caso di emergenza premere il pulsante di arresto sul **quadro elettrico**: tutte le pompe si fermano e le valvole di intercettazione si chiudono.",
            w.req(
                "L'arresto di emergenza deve essere raggiungibile in meno di 10 secondi da qualsiasi punto del locale macchine."
            ),
            w.standard(),
        ]
    elif "Glossario" in title:
        blocks += [
            "Questo capitolo raccoglie i termini usati nel manuale. Il **collaudo** è la prova con cui si verifica che l'impianto rispetti i valori concordati; la **portata** è il volume d'acqua erogato nell'unità di tempo.",
            "La **mandata** è il lato della pompa verso la rete; l'**aspirazione** è il lato verso il serbatoio.",
        ]
    elif "Norme" in title:
        blocks += [
            "Il progetto e le prove fanno riferimento alle norme seguenti.",
            "\n".join(f"- {n}" for n in NORMS),
        ]
    else:
        blocks += [w.intro(c), w.warning(c), w.standard()]
        if "protezione" in title:
            blocks += [
                "Gli operatori devono indossare:",
                "- scarpe antinfortunistiche con puntale rinforzato;\n- guanti resistenti agli oli;\n- occhiali di protezione durante le operazioni di spurgo;\n- cuffie nei locali in cui il rumore supera gli 85 dB(A).",
            ]
    return "\n\n".join(blocks) + "\n"


def component_section(w: Writer, chapter: str, c: Component, title: str) -> str:
    blocks = [f"# {title}", w.intro(c)]
    if chapter == "Installazione":
        blocks += [
            w.warning(c),
            "Procedere come indicato di seguito.",
            w.steps(c, "install"),
            w.requirements(c, 2),
            w.standard(),
        ]
        link = "Per le regole di sicurezza vedere [Regole generali di sicurezza](../03-sicurezza/01-regole-generali-di-sicurezza.md)."
        blocks.append(link)
    elif chapter == "Messa in servizio":
        sentence, note = w.footnote_ref()
        blocks += [
            "La **messa in servizio** deve essere eseguita da personale addestrato, con l'impianto privo di perdite.",
            w.steps(c, "commission"),
            sentence,
            w.requirements(c, 2),
            w.standard(),
            note,
        ]
    elif chapter == "Manutenzione":
        blocks += [
            "La manutenzione ordinaria si esegue a intervalli regolari: ogni 500 ore di funzionamento il **manutentore** controlla le tenute, ogni 4000 ore sostituisce i cuscinetti.",
            w.warning(c),
            w.steps(c, "maintain"),
            w.standard(),
            "Il codice parametro per la soglia di vibrazione è `VIB_MAX` e il suo valore predefinito è 7,1 mm/s.",
        ]
    elif chapter == "Diagnostica e allarmi":
        blocks += [
            "Il **Supervisore** segnala le anomalie con un codice e un messaggio; la tabella seguente riporta quelle più frequenti.",
            w.alarm_table(c),
            "Quando un allarme non rientra da solo, annotare il codice, fermare la macchina e seguire l'azione consigliata.",
        ]
        if c.code == "P1100":  # one section only: a diagram is drawn when its section is opened
            blocks += [MERMAID_ALARM]
        blocks += [w.requirements(c, 2), w.standard()]
    else:  # Specifiche tecniche
        blocks += [
            "I dati seguenti sono validi per le condizioni nominali di funzionamento e possono variare entro le tolleranze indicate dalla norma.",
            w.table(c),
            f"La coppia di serraggio dei bulloni delle flange è di {w.rng.choice([25, 40, 60, 80])} N·m. La temperatura massima del fluido è di 60 °C.",
            w.requirements(c, 1),
        ]
    return "\n\n".join(blocks) + "\n"


# --- the project -----------------------------------------------------------------------------


def front_matter(title: str) -> str:
    return f'---\ntitle: "{title}"\n---\n\n'


def yaml_dump(entries: list[dict[str, object]]) -> str:
    out: list[str] = []
    for e in entries:
        out.append(f"- sorgente: {e['sorgente']}")
        if e.get("destinazione"):
            out.append(
                "  destinazione: { "
                + ", ".join(f"{k}: {v}" for k, v in e["destinazione"].items())
                + " }"
            )  # type: ignore[union-attr]
        if e.get("vietati"):
            out.append(
                "  vietati: { "
                + ", ".join(f"{k}: [{', '.join(v)}]" for k, v in e["vietati"].items())
                + " }"
            )  # type: ignore[union-attr]
        if e.get("non_tradurre"):
            out.append("  non_tradurre: true")
        if e.get("note"):
            out.append(f"  note: {e['note']}")
    return "\n".join(out) + "\n"


def build(out: Path, sections: int, seed: int) -> dict[str, int]:
    rng = random.Random(seed)
    per = max(1, (sections - FIXED_SECTIONS) // PER_COMPONENT_CHAPTERS)
    comps = components(per, rng)
    w = Writer(rng)
    (out / "capitoli").mkdir(parents=True)
    stats = {"sections": 0, "words": 0}
    number = 0

    def write_section(chapter_dir: Path, index: int, title: str, body: str) -> None:
        text = front_matter(title) + body
        (chapter_dir / f"{index:02d}-{slug(title)}.md").write_text(text, encoding="utf-8")
        stats["sections"] += 1
        stats["words"] += len(re.findall(r"\w+", body))

    def chapter(title: str) -> Path:
        nonlocal number
        number += 1
        folder = out / "capitoli" / f"{number:02d}-{slug(title)}"
        folder.mkdir()
        (folder / "_capitolo.yaml").write_text(f"title: {title}\n", encoding="utf-8")
        return folder

    for title, names in CHAPTERS_FIXED:
        folder = chapter(title)
        for i, name in enumerate(names, 1):
            write_section(folder, i, name, fixed_section(w, name, folder.name, comps))
    for title, pattern in CHAPTERS_PER_COMPONENT:
        folder = chapter(title)
        for i, c in enumerate(comps, 1):
            name = pattern.format(name=c.name, code=c.code)
            write_section(folder, i, name, component_section(w, title, c, name))
    for title, names in CHAPTERS_CLOSING:
        folder = chapter(title)
        for i, name in enumerate(names, 1):
            write_section(folder, i, name, fixed_section(w, name, folder.name, comps))

    (out / "glossario.yaml").write_text(yaml_dump(GLOSSARY), encoding="utf-8")
    (out / "progetto.yaml").write_text(
        "nome: Manuale stazione di pompaggio SP-200 (documento di prova grande)\n"
        "lingua_sorgente: it\nlingua_ufficiale: en\ntono: formale\ntemplate_predefinito: manuale\n"
        'metadati:\n  codice_documento: SP200-MAN-001\n  revisione: "01"\n  cliente: ACME Ltd\n'
        "  autore: Mario Rossi\n  data: 2026-11-08\n"
        'revisioni:\n  - { rev: "01", data: 2026-11-08, descrizione: Prima emissione }\n'
        "metadati_da_tradurre: [nome]\n",
        encoding="utf-8",
    )
    (out / ".gitignore").write_text(
        "# Generated by Traduco\n.traduco/cache/\n.traduco/cestino/\n.traduco/tm.sqlite\nbuild/\n",
        encoding="utf-8",
    )
    template = REPO / "examples" / "progetto-esempio" / "template"
    if template.is_dir():
        shutil.copytree(template, out / "template", ignore=shutil.ignore_patterns("README.md"))
    stats["requirements"] = w.requirement
    stats["components"] = per
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--sections", type=int, default=110, help="approximate number of sections (default 110)"
    )
    parser.add_argument("--out", type=Path, default=Path.home() / "Traduco" / "manuale-grande")
    parser.add_argument("--seed", type=int, default=2026, help="same seed, same project")
    parser.add_argument("--force", action="store_true", help="replace the folder if it exists")
    args = parser.parse_args()
    if args.sections < FIXED_SECTIONS + PER_COMPONENT_CHAPTERS:
        parser.error(f"at least {FIXED_SECTIONS + PER_COMPONENT_CHAPTERS} sections")
    if args.out.exists():
        if not args.force:
            print(f"{args.out} exists: use --force to replace it", file=sys.stderr)
            return 1
        shutil.rmtree(args.out)
    stats = build(args.out, args.sections, args.seed)
    print(
        f"{args.out}: {stats['sections']} sections, {stats['words']} words, "
        f"{stats['components']} components, {stats['requirements']} requirements"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
