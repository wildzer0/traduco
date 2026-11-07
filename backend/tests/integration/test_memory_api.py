"""Translation memory through the HTTP API (RF-29)."""

from fastapi.testclient import TestClient

from tests.integration.test_translation_api import (  # noqa: F401
    FakeLlm,
    llm,
    setup_section,
    tapi,
    view,
    wait_for,
)


def second_section(c: TestClient, pid: str, text: str) -> str:
    sec = c.post(
        f"/api/projects/{pid}/nodes",
        json={"kind": "section", "title": "Tre", "parent": "capitoli/01-uno"},
    ).json()["path"]
    sec = str(sec)
    got = c.get(f"/api/projects/{pid}/files", params={"path": sec}).json()
    r = c.put(
        f"/api/projects/{pid}/files",
        params={"path": sec},
        headers={"If-Match": got["hash"]},
        json={"content": text},
    )
    assert r.status_code == 200, r.text
    return sec


def test_an_approved_sentence_is_reused_without_asking_the_model(
    tapi: TestClient, llm: FakeLlm
) -> None:
    pid, sec, _ = setup_section(tapi, "La pompa parte subito.\n")
    wait_for(lambda: view(tapi, pid, sec)["pending"] == 0)
    done = tapi.put(
        f"/api/projects/{pid}/segments/p:0", params={"path": sec}, json={"action": "approve"}
    )
    assert done.status_code == 200, done.text
    assert tapi.get(f"/api/projects/{pid}/tm").json() == {"units": 1}

    llm.stop()  # from here on a call to the model would fail: the memory must answer
    other = second_section(tapi, pid, "La pompa parte subito.\n")
    wait_for(lambda: view(tapi, pid, other)["segments"] != [])
    row = view(tapi, pid, other)["segments"][0]
    assert row["target"] == "[EN] La pompa parte subito." and row["status"] == "translated"


def test_similar_sentences_are_suggested_and_the_memory_travels_as_tmx(
    tapi: TestClient,
) -> None:
    pid, sec, _ = setup_section(tapi, "Il sistema avvia la pompa principale.\n")
    wait_for(lambda: view(tapi, pid, sec)["pending"] == 0)
    tapi.put(
        f"/api/projects/{pid}/segments/p:0",
        params={"path": sec},
        json={"target": "My own wording."},
    )
    other = second_section(tapi, pid, "Il sistema avvia la pompa di riserva.\n")
    wait_for(lambda: view(tapi, pid, other)["segments"] != [])
    suggestion = tapi.get(
        f"/api/projects/{pid}/tm/suggest", params={"path": other, "key": "p:0"}
    ).json()["matches"]
    assert (
        suggestion
        and suggestion[0]["target"] == "My own wording."
        and 0.75 <= suggestion[0]["score"] < 1
    )

    tmx = tapi.get(f"/api/projects/{pid}/tm/export")
    assert tmx.status_code == 200 and b"<tmx" in tmx.content and b"My own wording." in tmx.content
    back = tapi.post(f"/api/projects/{pid}/tm/import", content=tmx.content)
    assert back.json() == {"added": 1}
    assert tapi.post(f"/api/projects/{pid}/tm/import", content=b"junk").status_code == 422


def test_the_glossary_travels_as_csv_and_tbx(tapi: TestClient) -> None:
    pid, _, _ = setup_section(tapi, "x\n")
    base = f"/api/projects/{pid}/glossary"
    mine = [{"sorgente": "offerta", "destinazione": {"en": "tender"}}]
    assert tapi.put(base, json=mine).status_code == 200
    csv = tapi.get(f"{base}/export")
    assert (
        csv.status_code == 200
        and b"offerta" in csv.content
        and "csv" in csv.headers["content-type"]
    )
    tbx = tapi.get(f"{base}/export", params={"format": "tbx"})
    assert b"<martif" in tbx.content

    extra = (
        "sorgente,lingua,destinazione,vietati,non_tradurre,note\n"
        "offerta,en,proposal,,0,\nnuovo,en,new,,0,\n"
    )
    done = tapi.post(f"{base}/import", content=extra.encode())
    assert done.json() == {"added": 1, "seen": 2, "total": 2}
    kept = {e["sorgente"]: e for e in tapi.get(base).json()}
    assert kept["offerta"]["destinazione"]["en"] == "tender"  # the author's wording is kept
    assert (
        tapi.post(f"{base}/import", params={"format": "tbx"}, content=tbx.content).json()["added"]
        == 0
    )
    assert tapi.post(f"{base}/import", content=b"junk").status_code == 422
