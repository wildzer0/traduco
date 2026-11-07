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
