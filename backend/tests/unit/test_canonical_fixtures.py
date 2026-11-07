"""Backend check of the canonical Markdown form (docs/02-architettura.md).

``fixtures/markdown/*.out.md`` are produced by ``frontend/src/lib/markdown/canonical.ts`` (golden
files, reviewed by hand). Here we verify that they obey the shared rules, so a change of rules on
one side only is caught.
"""

import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "markdown"
OUTPUTS = sorted(FIXTURES.glob("*.out.md"))


def test_every_input_has_a_golden_output() -> None:
    inputs = {p.name.removesuffix(".in.md") for p in FIXTURES.glob("*.in.md")}
    outputs = {p.name.removesuffix(".out.md") for p in OUTPUTS}
    assert inputs and inputs == outputs


@pytest.mark.parametrize("path", OUTPUTS, ids=lambda p: p.name)
def test_canonical_rules(path: Path) -> None:
    data = path.read_bytes()
    text = data.decode("utf-8")
    assert b"\r" not in data
    if not text:
        return
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "\n\n\n" not in text
    assert not re.search(r"[ \t]+\n", text), "trailing whitespace"
    body = text
    if text.startswith("---\n"):  # front matter is kept verbatim: check only the body
        body = text.split("\n---\n", 1)[1]
    in_fence = False
    for line in body.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        if in_fence or line.startswith("```"):
            continue
        assert not re.match(r"^(=+|-{2,})\s*$", line) or line == "---", f"setext heading: {line!r}"
        assert not line.startswith("~~~"), "fences use backticks"
        assert not re.search(r"(?<!\w)__\w[^_]*\w__(?!\w)", line), f"use ** for strong: {line!r}"
        assert not re.match(r"^\s*\d+\)\s", line), f"ordered lists use '1.': {line!r}"
