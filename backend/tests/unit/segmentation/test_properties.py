"""Mandatory property test (docs/02): identity translation must not change the rendered HTML."""

from hypothesis import given, settings
from hypothesis import strategies as st
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

from app.core.segmentation.assembler import assemble
from app.core.segmentation.protect import protect, restore
from app.core.segmentation.segmenter import segment

WORD = st.sampled_from(
    [
        "alfa",
        "beta",
        "`code`",
        "**forte**",
        "_enf_",
        "[link](u.md)",
        "![a](i.png)",
        "{{campo}}",
        "x|y",
    ]
)
LINE = st.lists(WORD, min_size=1, max_size=5).map(" ".join)
PARA = st.lists(LINE, min_size=1, max_size=3).map("\n".join)


def blocks() -> st.SearchStrategy[str]:
    heading = st.tuples(st.integers(1, 3), LINE).map(lambda t: "#" * t[0] + " " + t[1])
    bullets = st.lists(LINE, min_size=1, max_size=3).map(lambda ls: "\n".join(f"- {x}" for x in ls))
    numbered = st.lists(LINE, min_size=1, max_size=3).map(
        lambda ls: "\n".join(f"{i}. {x}" for i, x in enumerate(ls, 1))
    )
    quote = PARA.map(lambda p: "\n".join(f"> {x}" for x in p.split("\n")))
    code = st.just("```\nnon tradurre\n```")
    table = st.tuples(
        LINE.map(lambda s: s.replace("|", "/")), LINE.map(lambda s: s.replace("|", "/"))
    ).map(lambda t: f"| {t[0]} | {t[1]} |\n|---|---|\n| {t[1]} | {t[0]} |")
    note = LINE.map(lambda s: f"[^1]: {s}\n    {s}")
    return st.one_of(heading, PARA, bullets, numbered, quote, code, table, note)


DOCS = st.lists(blocks(), min_size=1, max_size=6).map(lambda bs: "\n\n".join(bs) + "\n")
MD = MarkdownIt("commonmark").enable("table").use(footnote_plugin)


@settings(max_examples=300, deadline=None)
@given(DOCS)
def test_identity_translation_renders_identical_html(text: str) -> None:
    doc = segment(text)
    targets = {}
    for seg in doc.segments:
        protected = protect(seg.source)
        targets[seg.key] = restore(protected.text, protected)
    out = assemble(doc, targets)
    assert out == text
    assert MD.render(out) == MD.render(text)


@settings(max_examples=200, deadline=None)
@given(DOCS)
def test_translated_text_keeps_the_block_structure(text: str) -> None:
    """Replacing the words of every segment must not change the sequence of block tokens."""
    doc = segment(text)
    targets = {
        s.key: s.source.replace("alfa", "ALPHA").replace("beta", "BETA") for s in doc.segments
    }
    out = assemble(doc, targets)

    def shape(t: str) -> list[str]:
        return [tok.type for tok in MD.parse(t)]

    assert shape(out) == shape(text)
