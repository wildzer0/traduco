"""A project of 300 sections stays quick (M6 acceptance: the tree opens in under a second)."""

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings

CHAPTERS, SECTIONS = 30, 10  # 300 sections
PARAGRAPH = (
    "Il sistema avvia la pompa principale e controlla la pressione del circuito idraulico, "
    "poi registra il valore letto e segnala ogni scostamento rispetto alla soglia prevista. "
)


def build(root: Path) -> None:
    for c in range(1, CHAPTERS + 1):
        chapter = root / "capitoli" / f"{c:02d}-capitolo-{c}"
        chapter.mkdir(parents=True)
        (chapter / "_capitolo.yaml").write_text(f"title: Capitolo {c}\n", encoding="utf-8")
        for s in range(1, SECTIONS + 1):
            body = "\n\n".join(
                PARAGRAPH + f"Paragrafo {p} della sezione {c}.{s}." for p in range(8)
            )
            (chapter / f"{s:02d}-sezione-{s}.md").write_text(
                f"---\ntitle: Sezione {c}.{s}\n---\n\n# Sezione {c}.{s}\n\n{body}\n",
                encoding="utf-8",
            )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    from app.main import create_app

    ws = tmp_path / "ws"
    project = ws / "grande"
    project.mkdir(parents=True)
    (project / "progetto.yaml").write_text(
        "nome: Grande\nlingua_sorgente: it\nlingua_ufficiale: en\n", encoding="utf-8"
    )
    build(project)
    settings = Settings(workspaces_dir=ws, frontend_dist=None, llm_base_url="http://127.0.0.1:9/v1")
    with TestClient(create_app(settings)) as c:
        yield c


def timed[T](call: Callable[[], T]) -> tuple[T, float]:
    start = time.perf_counter()
    result = call()
    return result, time.perf_counter() - start


def test_the_tree_of_300_sections_opens_in_under_a_second(client: TestClient) -> None:
    client.get("/api/projects/grande/tree")  # first call warms imports and caches
    response, seconds = timed(lambda: client.get("/api/projects/grande/tree"))
    nodes = response.json()["nodes"]
    assert sum(len(n["children"]) for n in nodes) == CHAPTERS * SECTIONS
    assert seconds < 1.0, f"the tree took {seconds:.2f} s"


def test_searching_and_checking_the_whole_project_is_quick(client: TestClient) -> None:
    response, seconds = timed(
        lambda: client.get("/api/projects/grande/search", params={"q": "sezione 15.7"})
    )
    assert response.json()["hits"] and seconds < 3.0, f"search took {seconds:.2f} s"
    _, seconds = timed(lambda: client.get("/api/projects/grande/requirements"))
    assert seconds < 3.0, f"requirements scan took {seconds:.2f} s"


def test_reading_one_section_does_not_depend_on_the_project_size(client: TestClient) -> None:
    path = "capitoli/15-capitolo-15/07-sezione-7.md"
    client.get("/api/projects/grande/files", params={"path": path})
    response, seconds = timed(
        lambda: client.get("/api/projects/grande/files", params={"path": path})
    )
    assert response.status_code == 200 and seconds < 0.2, f"read took {seconds:.2f} s"
