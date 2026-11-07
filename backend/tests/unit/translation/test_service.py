import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.core.translation import store
from app.core.translation.llm_client import LlmUnavailable
from app.core.translation.service import LlmConfig, TranslationService
from app.core.workspace.manifest import Project

PROJECT = Project(nome="P", lingua_sorgente="it", lingua_ufficiale="en")


class FakeClient:
    def __init__(self) -> None:
        self.model = "fake"
        self.up = True
        self.calls: list[str] = []

    async def chat(self, messages: list[dict[str, str]], **kw: Any) -> str:
        if not self.up:
            raise LlmUnavailable("down")
        text = messages[-1]["content"].split("<source>")[1].split("</source>")[0]
        self.calls.append(text)
        return "[EN] " + text

    async def models(self) -> list[str]:
        if not self.up:
            raise LlmUnavailable("down")
        return ["fake"]

    async def aclose(self) -> None: ...


@pytest.fixture
async def env(tmp_path: Path):  # type: ignore[no-untyped-def]
    client = FakeClient()
    events: list[dict[str, Any]] = []
    svc = TranslationService(
        LlmConfig("http://x/v1", "fake"),
        lambda root, ev: events.append(ev),
        client_factory=lambda cfg: client,  # type: ignore[arg-type,return-value]
        monitor_seconds=0.05,
    )
    svc.start()
    yield svc, client, events, tmp_path
    await svc.close()


def stored(root: Path, rel: str = "capitoli/01-a/01-s.md") -> dict[str, Any]:
    f = store.load(root, "en", rel)
    assert f is not None
    return {s.key: s for s in f.segments}


async def test_translates_every_segment(env) -> None:  # type: ignore[no-untyped-def]
    svc, client, events, root = env
    svc.sync(root, PROJECT, "capitoli/01-a/01-s.md", "# Titolo\n\nUn paragrafo di prova.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    got = stored(root)
    assert got["h:0"].target == "[EN] Titolo" and got["h:0"].status == "translated"
    assert got["p:0"].target == "[EN] Un paragrafo di prova."
    assert {e["type"] for e in events} >= {"segment.queued", "segment.updated"}


async def test_editing_one_paragraph_translates_only_that_one(env) -> None:  # type: ignore[no-untyped-def]
    svc, client, _, root = env
    rel = "capitoli/01-a/01-s.md"
    svc.sync(root, PROJECT, rel, "Uno.\n\nDue.\n\nTre.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    client.calls.clear()
    svc.sync(root, PROJECT, rel, "Uno.\n\nDue modificato.\n\nTre.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    assert client.calls == ["Due modificato."]
    assert stored(root)["p:1"].target == "[EN] Due modificato."


async def test_moving_a_paragraph_reuses_its_translation(env) -> None:  # type: ignore[no-untyped-def]
    svc, client, _, root = env
    rel = "capitoli/01-a/01-s.md"
    svc.sync(root, PROJECT, rel, "Uno.\n\nDue.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    client.calls.clear()
    svc.sync(root, PROJECT, rel, "Due.\n\nUno.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    assert client.calls == []
    assert stored(root)["p:0"].target == "[EN] Due."


async def test_locked_segment_keeps_target_and_gets_a_proposal(env) -> None:  # type: ignore[no-untyped-def]
    svc, _, _, root = env
    rel = "capitoli/01-a/01-s.md"
    svc.sync(root, PROJECT, rel, "Uno.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    store.update(root, "en", rel, lambda f: setattr(f.segments[0], "locked", True))
    svc.sync(root, PROJECT, rel, "Uno cambiato.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    seg = stored(root)["p:0"]
    assert seg.target == "[EN] Uno." and seg.pending_target == "[EN] Uno cambiato."
    assert seg.status == "needs_review"


async def test_traduci_false_skips_the_section(env) -> None:  # type: ignore[no-untyped-def]
    svc, client, _, root = env
    assert svc.sync(root, PROJECT, "capitoli/a.md", "---\ntraduci: false\n---\nTesto.\n") is None
    assert client.calls == []


async def test_model_offline_then_back_resumes(env) -> None:  # type: ignore[no-untyped-def]
    svc, client, events, root = env
    client.up = False
    svc.sync(root, PROJECT, "capitoli/01-a/01-s.md", "Ciao mondo.\n")
    await asyncio.sleep(0.2)
    assert stored(root)["p:0"].status == "queued"
    assert any(e["type"] == "llm.status" and e["online"] is False for e in events)
    client.up = True
    await asyncio.wait_for(svc.queue.join(), 3)
    assert stored(root)["p:0"].target == "[EN] Ciao mondo."
    assert any(e["type"] == "llm.status" and e["online"] is True for e in events)


async def test_translation_view_assembles_markdown_and_marks_pending(env) -> None:  # type: ignore[no-untyped-def]
    svc, client, _, root = env
    rel = "capitoli/01-a/01-s.md"
    text = "# Titolo\n\nCodice `x` qui.\n"
    svc.sync(root, PROJECT, rel, text)
    await asyncio.wait_for(svc.queue.join(), 3)
    view = svc.translation(root, PROJECT, rel, text)
    assert view["markdown"] == "# [EN] Titolo\n\n[EN] Codice `x` qui.\n"
    assert [s["status"] for s in view["segments"]] == ["translated", "translated"]
    edited = svc.translation(root, PROJECT, rel, "# Titolo\n\nNuovo.\n")
    assert edited["segments"][1]["status"] == "queued"
    assert edited["markdown"].endswith("Nuovo.\n")  # untranslated text shows the source


async def test_force_retranslates_unlocked_only(env) -> None:  # type: ignore[no-untyped-def]
    svc, client, _, root = env
    rel = "capitoli/01-a/01-s.md"
    (root / "capitoli/01-a").mkdir(parents=True)
    (root / rel).write_text("Uno.\n\nDue.\n")
    svc.sync(root, PROJECT, rel, "Uno.\n\nDue.\n")
    await asyncio.wait_for(svc.queue.join(), 3)
    store.update(root, "en", rel, lambda f: setattr(f.segments[0], "locked", True))
    client.calls.clear()
    assert svc.retranslate(root, PROJECT, [rel]) == 1
    await asyncio.wait_for(svc.queue.join(), 3)
    assert client.calls == ["Due."]
