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
                        raise LlmError(_error_message(response))
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
        response = await self._request("POST", "chat/completions", json=body)
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmError("unexpected reply from the model server") from exc
        if not isinstance(content, str):
            raise LlmError("unexpected reply from the model server")
        return content

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
