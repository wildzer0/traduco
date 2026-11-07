from app.core.segmentation.assembler import assemble
from app.core.segmentation.segmenter import segment, split_row

DOC = """---
title: Scopo del documento
tono: neutro
---
# Titolo *uno*

Primo paragrafo
con due righe.

- voce a
  continua
- voce b

> citazione
> su due righe

| A | B |
|---|---|
| c | d \\| e |

```python
print("non tradurre")
```

<div>html grezzo</div>

Nota[^1].

[^1]: Testo della nota
    seconda riga.
"""


def keys(text: str) -> dict[str, str]:
    return {s.key: s.source for s in segment(text).segments}


def test_segments_all_kinds_and_skips_code_html() -> None:
    got = keys(DOC)
    assert got == {
        "fm:title": "Scopo del documento",
        "h:0": "Titolo *uno*",
        "p:0": "Primo paragrafo\ncon due righe.",
        "li:0": "voce a\ncontinua",
        "li:1": "voce b",
        "q:0": "citazione\nsu due righe",
        "th:0:0": "A",
        "th:0:1": "B",
        "td:0:0:0": "c",
        "td:0:0:1": "d \\| e",
        "p:1": "Nota[^1].",
        "fn:0": "Testo della nota\nseconda riga.",
    }


def test_identity_assembly_is_exact() -> None:
    doc = segment(DOC)
    assert assemble(doc, {s.key: s.source for s in doc.segments}) == DOC
    assert assemble(doc, {}) == DOC


def test_translation_keeps_structure() -> None:
    doc = segment(DOC)
    targets = {
        "fm:title": "Purpose",
        "h:0": "Title *one*",
        "li:0": "item a\ncontinues",
        "q:0": "quote\non two lines",
        "td:0:0:1": "d | e",
        "fn:0": "Note text\nsecond line.",
    }
    out = assemble(doc, targets)
    assert "title: Purpose\n" in out
    assert "# Title *one*\n" in out
    assert "- item a\n  continues\n" in out
    assert "> quote\n> on two lines\n" in out
    assert "| c | d \\| e |" in out  # pipe re-escaped
    assert "[^1]: Note text\n    second line.\n" in out
    assert '```python\nprint("non tradurre")\n```' in out
    assert "<div>html grezzo</div>" in out


def test_longer_translation_adds_continuation_prefix() -> None:
    doc = segment("- one\n- two\n")
    out = assemble(doc, {"li:0": "uno\ndue\ntre"})
    assert out == "- uno\n  due\n  tre\n- two\n"


def test_quote_extra_lines_keep_marker() -> None:
    out = assemble(segment("> a\n"), {"q:0": "x\ny"})
    assert out == "> x\n> y\n"


def test_split_row_handles_escaped_pipe_and_no_outer_pipes() -> None:
    line = "| a | b \\| c |"
    assert [line[a:b].strip() for a, b in split_row(line)] == ["a", "b \\| c"]
    bare = "x | y"
    assert [bare[a:b].strip() for a, b in split_row(bare)] == ["x", "y"]


def test_empty_cells_are_not_segments() -> None:
    got = keys("| A |  |\n|---|---|\n|  | b |\n")
    assert got == {"th:0:0": "A", "td:0:0:1": "b"}


def test_table_translation_in_place() -> None:
    doc = segment("| A | B |\n|---|---|\n| c | d |\n")
    out = assemble(doc, {"th:0:0": "X", "td:0:0:1": "Y | Z"})
    assert out == "| X | B |\n|---|---|\n| c | Y \\| Z |\n"


def test_title_is_quoted_when_needed() -> None:
    doc = segment("---\ntitle: Ciao\n---\ntesto\n")
    assert assemble(doc, {"fm:title": "A: B"}).startswith('---\ntitle: "A: B"\n---')


def test_nested_list_and_trailing_spaces() -> None:
    text = "1. uno\n   - annidato\n2. due  \n   a capo\n"
    doc = segment(text)
    assert assemble(doc, {s.key: s.source for s in doc.segments}) == text


def test_no_front_matter_no_title() -> None:
    assert "fm:title" not in keys("# Solo titolo\n")
