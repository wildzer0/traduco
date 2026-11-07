import asyncio

import httpx
import pytest

from app.core.translation.llm_client import LlmClient, LlmError, LlmUnavailable


def client(handler, **kw) -> LlmClient:  # type: ignore[no-untyped-def]
    return LlmClient(
        "http://llm.test/v1", "m", backoff=0, transport=httpx.MockTransport(handler), **kw
    )


def ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_chat_returns_content_and_sends_model() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return ok("ciao")

    assert await client(handler).chat([{"role": "user", "content": "x"}], max_tokens=5) == "ciao"
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert b'"model":"m"' in seen["body"]  # type: ignore[operator]


async def test_retries_server_errors_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500) if calls < 3 else ok("fine")

    assert await client(handler).chat([]) == "fine"
    assert calls == 3


async def test_gives_up_as_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(LlmUnavailable):
        await client(handler).chat([])


async def test_client_errors_are_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": {"message": "bad model"}})

    with pytest.raises(LlmError, match="bad model") as info:
        await client(handler).chat([])
    assert not isinstance(info.value, LlmUnavailable)
    assert calls == 1


async def test_models_lists_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})

    assert await client(handler).models() == ["a", "b"]


async def test_request_can_be_cancelled() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10)
        return ok("late")

    task = asyncio.create_task(client(handler).chat([]))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# --- reasoning models (Gemma 4 on Ollama answered with an empty text) ---------------------------

import json  # noqa: E402


async def test_reasoning_is_switched_off_by_default() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read()))
        return ok("fine")

    await client(handler).chat([{"role": "user", "content": "x"}])
    assert bodies[0]["reasoning_effort"] == "none"


async def test_a_server_that_refuses_the_setting_is_asked_once_more_without_it() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        bodies.append(body)
        if "reasoning_effort" in body:
            return httpx.Response(
                400, json={"error": {"message": "Unsupported parameter: 'reasoning_effort'"}}
            )
        return ok("fine")

    c = client(handler)
    assert await c.chat([]) == "fine"
    assert await c.chat([]) == "fine"
    assert ["reasoning_effort" in b for b in bodies] == [True, False, False]  # remembered


async def test_an_unrelated_client_error_does_not_disable_the_setting() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"message": "model 'x' not found"}})

    c = client(handler)
    with pytest.raises(LlmError, match="not found"):
        await c.chat([])
    assert c._send_reasoning_off is True


async def test_empty_answer_cut_by_the_token_limit_is_retried_with_more_room() -> None:
    limits: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        limit = json.loads(request.read())["max_tokens"]
        limits.append(limit)
        if limit < 1000:
            return httpx.Response(
                200, json={"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
            )
        return ok("translated")

    assert await client(handler).chat([], max_tokens=213) == "translated"
    assert limits == [213, 1278]


async def test_an_answer_that_stays_empty_is_returned_empty_after_one_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, json={"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
        )

    assert await client(handler).chat([], max_tokens=100) == ""  # the translator rejects it
    assert calls == 2
