"""OpenAI-compatible chat client: timeout, retry with backoff, cancellation (ADR-007, ADR-014).

The only module allowed to open network connections (see ``test_no_network_clients``).
Cancel a request by cancelling the asyncio task that awaits it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import httpx


class LlmError(Exception):
    """The server answered, but the request cannot succeed (4xx, malformed reply)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class LlmUnavailable(LlmError):
    """The server cannot be reached or keeps failing (connection, timeout, 5xx)."""


class LlmClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        *,
        timeout: float = 60.0,
        retries: int = 2,
        backoff: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.model = model
        # Reasoning models (Gemma 4, Qwen 3…) spend their token budget "thinking" and then answer
        # with nothing: translation does not need it. Servers that do not know the setting
        # refuse it once and it is left out from then on.
        self._send_reasoning_off = True
        self._retries = retries
        self._backoff = backoff
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = await self._http.request(method, url, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last = exc
            else:
                if response.status_code < 500:
                    if response.status_code >= 400:
                        raise LlmError(_error_message(response), response.status_code)
                    return response
                last = LlmError(_error_message(response))
            if attempt < self._retries:
                await asyncio.sleep(self._backoff * 2**attempt)
        raise LlmUnavailable(str(last) or type(last).__name__) from last

    async def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        grown = False
        for _ in range(4):
            if self._send_reasoning_off:
                body["reasoning_effort"] = "none"
            else:
                body.pop("reasoning_effort", None)
            try:
                response = await self._request("POST", "chat/completions", json=body)
            except LlmUnavailable:
                raise
            except LlmError as exc:
                if (
                    self._send_reasoning_off
                    and exc.status in (400, 422)
                    and "reasoning" in str(exc).lower()
                ):
                    self._send_reasoning_off = False  # this server does not know the setting
                    continue
                raise
            try:
                choice = response.json()["choices"][0]
                content = choice["message"]["content"]
                finished = choice.get("finish_reason")
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise LlmError("unexpected reply from the model server") from exc
            if not isinstance(content, str):
                raise LlmError("unexpected reply from the model server")
            if (
                not content.strip()
                and finished == "length"
                and body.get("max_tokens")
                and not grown
            ):
                # a model that reasons anyway used the whole budget: give it room, once
                body["max_tokens"] = int(body["max_tokens"]) * 6
                grown = True
                continue
            return content
        raise LlmError("the model returned no text")

    async def models(self) -> list[str]:
        """Model ids offered by the server; raises :class:`LlmUnavailable` if unreachable."""
        response = await self._request("GET", "models")
        try:
            return [str(m["id"]) for m in response.json()["data"]]
        except (ValueError, KeyError, TypeError) as exc:
            raise LlmError("unexpected reply from the model server") from exc


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {response.status_code}"
