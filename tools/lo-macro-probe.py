#!/usr/bin/env python3
"""Find out which way of running a LibreOffice Basic macro headlessly works on this machine.

Used by the manual workflow lo-probe.yml while developing the PDF/ODT export;
prints a report and never fails. Run it with the backend environment.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.export import office  # noqa: E402
from tests.support.template_factory import build_company_template  # noqa: E402


def run(cmd: list[str], timeout: int = 120) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    return (
        f"exit {r.returncode} stdout={r.stdout.strip()[:300]!r} stderr={r.stderr.strip()[:300]!r}"
    )


def toc_state(odt: Path) -> str:
    with zipfile.ZipFile(odt) as z:
        content = z.read("content.xml").decode()
    return (
        "hint-still-there"
        if ("Update the field" in content or "Aggiorna il campo" in content)
        else "updated-or-empty"
    )


def main() -> None:
    soffice = office.find_soffice()
    print("soffice:", soffice)
    print(run([str(soffice), "--version"]))
    print(
        run(
            ["sh", "-c", "dpkg -l | grep -i -E 'libreoffice|ure' | awk '{print $2}' | tr '\\n' ' '"]
        )
    )
    work = Path(tempfile.mkdtemp(prefix="probe-"))
    docx = build_company_template(work / "t.docx")
    base = [str(soffice), "--headless", "--norestore", "--nolockcheck"]
    for init_first in (False, True):
        for style, quoted in (("quoted", True), ("plain", False)):
            profile = Path(tempfile.mkdtemp(prefix="profile-"))
            env = f"-env:UserInstallation={profile.as_uri()}"
            if init_first:
                print(f"[init={init_first}] init:", run([*base, env, "--terminate_after_init"]))
            office._install_macro(profile)
            out = work / f"o-{init_first}-{style}.odt"
            args = [docx.resolve().as_uri(), out.resolve().as_uri(), "writer8"]
            call = (
                "macro:///Standard.Module1.ConvertUpdating("
                + ",".join(f'"{a}"' if quoted else a for a in args)
                + ")"
            )
            result = run([*base, env, call])
            print(
                f"[init={init_first} {style}] {result} -> file={out.is_file()}",
                toc_state(out) if out.is_file() else "",
            )
            print(
                "   profile basic dir:",
                sorted(p.name for p in (profile / "user" / "basic").rglob("*")),
            )
    print("work dir listing:", sorted(p.name for p in work.iterdir()))


if __name__ == "__main__":
    main()
