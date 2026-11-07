import json
import time
import urllib.error
import urllib.request

import pytest


def post(url: str, text: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    body = json.dumps(
        {
            "model": "m",
            "messages": [
                {"role": "system", "content": "translate"},
                {"role": "user", "content": text},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        url + "/v1/chat/completions", body, {"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def content(data: dict) -> str:
    return data["choices"][0]["message"]["content"]


def test_models(base_url: str) -> None:
    with urllib.request.urlopen(base_url + "/v1/models") as r:
        assert json.load(r)["data"][0]["id"] == "fake-model"


def test_translation_prefix_and_placeholders(base_url: str) -> None:
    text = "Usa ⟦1⟧ con ⟦b⟧cautela⟦/b⟧ è «ok»"
    status, data = post(base_url, text)
    assert status == 200
    assert content(data) == "[EN] " + text


def test_source_tags(base_url: str) -> None:
    _, data = post(base_url, "Translate:\n<source>Ciao</source>")
    assert content(data) == "[EN] Ciao"


def test_error_mode(base_url: str) -> None:
    status, data = post(base_url, "x", {"X-Fake-Mode": "error"})
    assert status == 500 and data["error"]["type"] == "server_error"


def test_slow_mode(base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_LLM_DELAY", "0.3")
    start = time.monotonic()
    status, _ = post(base_url, "x", {"X-Fake-Mode": "slow"})
    assert status == 200 and time.monotonic() - start >= 0.3


def test_glossary_violation_mode(base_url: str) -> None:
    _, data = post(base_url, "offerta", {"X-Fake-Mode": "glossary-violation"})
    assert content(data) == "[EN] offerta offer"


def test_invalid_request(base_url: str) -> None:
    req = urllib.request.Request(base_url + "/v1/chat/completions", b"nope", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400


def test_unknown_mode_falls_back_to_ok(base_url: str) -> None:
    status, data = post(base_url, "x", {"X-Fake-Mode": "bogus"})
    assert status == 200 and content(data) == "[EN] x"


def test_it_speaks_enough_ollama_for_the_launcher(base_url: str) -> None:
    import json
    import urllib.request

    def get(path: str) -> dict[str, object]:
        with urllib.request.urlopen(base_url + path) as r:
            return json.loads(r.read())  # type: ignore[no-any-return]

    assert get("/api/version")["version"]
    request = urllib.request.Request(
        base_url + "/api/pull",
        data=json.dumps({"model": "gemma4:e4b"}).encode(),
        method="POST",
    )
    with urllib.request.urlopen(request) as r:
        events = [json.loads(line) for line in r.read().splitlines()]
    assert events[-1] == {"status": "success"} and events[1]["total"] == 1000
    assert "gemma4:e4b" in [m["name"] for m in get("/api/tags")["models"]]  # type: ignore[attr-defined]
