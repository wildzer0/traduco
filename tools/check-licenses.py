#!/usr/bin/env python3
"""Fail if a dependency uses a license outside the allowlist (AGENTS.md rule 2, ADR-013, ADR-019).

Run from the backend environment: ``cd backend && uv run python ../tools/check-licenses.py``.
Python packages are read from the active environment; frontend packages from ``pnpm licenses``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED = {
    "MIT", "BSD-2-Clause", "BSD-3-Clause", "BSD", "Apache-2.0", "ISC", "MPL-2.0",
    "PostgreSQL", "Zlib",
    # ADR-019: permissive equivalents already pulled in by required tooling
    "PSF-2.0", "0BSD", "Unlicense", "BlueOak-1.0.0", "CC0-1.0", "Python-2.0",
}  # fmt: skip
# ADR-013: OFL-1.1 only for font assets.
FONT_ONLY = {"OFL-1.1": re.compile(r"^@fontsource/")}
SKIP = {"traduco-backend", "traduco-frontend"}

CLASSIFIERS = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
}
ALIASES = {
    "MIT License": "MIT",
    "Apache 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
}


def expression_ok(expr: str, name: str = "") -> bool:
    """``A OR B`` passes if any side passes; ``A AND B`` needs all sides."""
    expr = expr.strip().strip("()").strip()
    expr = ALIASES.get(expr, expr)
    for part in re.split(r"\s+OR\s+", expr, flags=re.IGNORECASE):
        if all(_single_ok(p, name) for p in re.split(r"\s+AND\s+", part, flags=re.IGNORECASE)):
            return True
    return False


def _single_ok(lic: str, name: str) -> bool:
    lic = ALIASES.get(lic.strip().strip("()"), lic.strip().strip("()"))
    if lic in ALLOWED:
        return True
    pattern = FONT_ONLY.get(lic)
    return bool(pattern and pattern.match(name))


def python_license(meta) -> str:  # type: ignore[no-untyped-def]
    if expr := meta.get("License-Expression"):
        return str(expr)
    for c in meta.get_all("Classifier") or []:
        if c in CLASSIFIERS:
            return CLASSIFIERS[c]
    lic = (meta.get("License") or "").strip()
    return lic if 0 < len(lic) < 60 and "\n" not in lic else "UNKNOWN"


def check_python() -> list[str]:
    bad = []
    for dist in distributions():
        name = dist.metadata["Name"]
        if name.lower() in SKIP:
            continue
        lic = python_license(dist.metadata)
        if not expression_ok(lic, name):
            bad.append(f"python: {name} ({lic})")
    return bad


def check_frontend() -> list[str]:
    out = subprocess.run(
        ["corepack", "pnpm", "licenses", "list", "--json"],
        cwd=ROOT / "frontend", capture_output=True, text=True, check=True,
    )  # fmt: skip
    bad = []
    for lic, packages in json.loads(out.stdout).items():
        for pkg in packages:
            if pkg["name"] not in SKIP and not expression_ok(lic, pkg["name"]):
                bad.append(f"frontend: {pkg['name']} ({lic})")
    return bad


def main() -> int:
    bad = check_python() + check_frontend()
    if bad:
        print("Disallowed licenses:\n  " + "\n  ".join(sorted(bad)), file=sys.stderr)
        return 1
    print("All dependency licenses are within the allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
