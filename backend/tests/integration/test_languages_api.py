"""Additional languages: translated from the source, in the background."""

from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from tests.integration.test_export_api import example, llm, run_export, xapi  # noqa: F401
from tests.integration.test_translation_api import view, wait_for

SECTION = "capitoli/01-introduzione/01-scopo.md"


def add_german(c: TestClient, pid: str) -> None:
    r = c.patch(
        f"/api/projects/{pid}",
        json={
            "lingue_aggiuntive": [
                {"codice": "de", "tono": "informale", "formato_date": "dd.MM.yyyy"}
            ]
        },
    )
    assert r.status_code == 200, r.text


def lang_view(c: TestClient, pid: str, lang: str) -> dict:  # type: ignore[type-arg]
    return c.get(f"/api/projects/{pid}/translation", params={"path": SECTION, "lang": lang}).json()  # type: ignore[no-any-return]


def test_an_additional_language_is_translated_from_the_source_with_its_own_store(
    xapi: TestClient, tmp_path: Path
) -> None:
    pid = example(xapi)
    add_german(xapi, pid)
    wait_for(lambda: lang_view(xapi, pid, "de")["pending"] == 0, timeout=20)
    german = lang_view(xapi, pid, "de")
    assert german["lang"] == "de" and german["segments"] and german["tone"] is None
    assert all(s["target"] for s in german["segments"])
    assert (tmp_path / "ws" / pid / ".traduco" / "segmenti" / "de" / "capitoli").is_dir()
    # the official language is untouched and still there
    assert (
        lang_view(xapi, pid, "en")["lang"] == "en"
        if False
        else view(xapi, pid, SECTION)["lang"] == "en"
    )
    assert (
        xapi.get(
            f"/api/projects/{pid}/translation", params={"path": SECTION, "lang": "fr"}
        ).status_code
        == 404
    )


def test_languages_report_how_far_each_one_is_translated(xapi: TestClient) -> None:
    pid = example(xapi)
    add_german(xapi, pid)
    wait_for(lambda: lang_view(xapi, pid, "de")["pending"] == 0, timeout=20)
    rows = {r["code"]: r for r in xapi.get(f"/api/projects/{pid}/languages").json()}
    assert rows["it"]["role"] == "source" and rows["en"]["role"] == "official"
    assert rows["de"]["role"] == "additional" and rows["de"]["tono"] == "informale"
    assert rows["de"]["total"] == rows["it"]["total"] > 0
    assert 0 <= rows["de"]["percent"] <= 100


def test_a_segment_of_an_additional_language_can_be_corrected_on_its_own(xapi: TestClient) -> None:
    pid = example(xapi)
    add_german(xapi, pid)
    wait_for(lambda: lang_view(xapi, pid, "de")["pending"] == 0, timeout=20)
    key = lang_view(xapi, pid, "de")["segments"][1]["key"]
    done = xapi.put(
        f"/api/projects/{pid}/segments/{key}",
        params={"path": SECTION, "lang": "de"},
        json={"target": "Meine eigene Formulierung."},
    )
    assert done.status_code == 200 and done.json()["target"] == "Meine eigene Formulierung."
    english = next(s for s in view(xapi, pid, SECTION)["segments"] if s["key"] == key)
    assert english["target"] != "Meine eigene Formulierung."


def test_exporting_in_an_additional_language(xapi: TestClient, tmp_path: Path) -> None:
    from tests.integration.test_export_api import draw_diagrams

    pid = example(xapi)
    draw_diagrams(xapi, pid, tmp_path / "ws")
    add_german(xapi, pid)
    status = run_export(xapi, pid, scope="project", language="de")
    assert status["state"] == "done", status
    assert "-de-" in status["filename"]
    out = tmp_path / "de.docx"
    out.write_bytes(xapi.get(f"/api/projects/{pid}/export/{status['id']}/download").content)
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "[EN]" in text  # the fake model's marker: translated text, not the source
    bad = run_export(xapi, pid, scope="project", language="fr")
    assert bad["state"] == "failed" and bad["error"]["code"] == "invalid_language"
