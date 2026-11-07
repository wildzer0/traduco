#!/usr/bin/env python3
"""Regenerate the example project's company template (template/manuale.docx and manuale.yaml).

Run from the repository root:  ``uv run --project backend python tools/make-example-template.py``
The template is synthetic (made by the same factory the tests use); replace it with your own.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.templates.analyze import analyze, propose_mapping  # noqa: E402
from app.core.templates.mapping import save_mapping  # noqa: E402
from tests.support.template_factory import build_company_template  # noqa: E402


def main() -> None:
    project = ROOT / "examples" / "progetto-esempio"
    template = build_company_template(project / "template" / "manuale.docx")
    save_mapping(project, "manuale", propose_mapping(analyze(template)))
    print(f"written: {template} and manuale.yaml")


if __name__ == "__main__":
    main()
