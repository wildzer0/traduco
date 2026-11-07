import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import pytest

from app.core.spellcheck import languagetool
from app.core.workspace.errors import WorkspaceError


def test_markdown_syntax_becomes_markup_and_offsets_stay_the_same() -> None:
    source = "Premi **Invio** e vedi `codice` in [guida](http://x.it) {{campo}}."
    parts = languagetool.annotate(source)
    assert "".join(p.get("text", "") + p.get("markup", "") for p in parts) == source
    markup = [p["markup"] for p in parts if "markup" in p]
    assert "**" in markup and "`codice`" in markup and "{{campo}}" in markup
    assert all("Invio" not in m and "guida" not in m for m in markup)


class Fake:
    """A stand-in for LanguageTool's HTTP API."""

    def __init__(self) -> None:
        self.requests: list[dict[str, list[str]]] = []
        self.status = 200


@pytest.fixture
def server() -> Iterator[tuple[str, Fake]]:
    fake = Fake()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a: object) -> None:
            pass

        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"[]")

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"])).decode()
            fake.requests.append(parse_qs(body))
            text = "".join(
                p.get("text", "") + p.get("markup", "")
                for p in json.loads(fake.requests[-1]["data"][0])["annotation"]
            )
            at = text.find("qual'è")
            matches = (
                [
                    {
                        "message": "Errore di ortografia",
                        "offset": at,
                        "length": 6,
                        "replacements": [{"value": "qual è"}],
                        "rule": {"id": "IT_RULE", "issueType": "misspelling"},
                    }
                ]
                if at >= 0
                else []
            )
            data = json.dumps({"matches": matches}).encode()
            self.send_response(fake.status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    httpd = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", fake
    httpd.shutdown()


async def test_issues_come_back_with_offset_message_and_replacements(
    server: tuple[str, Fake],
) -> None:
    url, fake = server
    issues = await languagetool.check(url, "it", "Dimmi **qual'è** la pompa.")
    assert issues == [
        {
            "offset": 8, "length": 6, "message": "Errore di ortografia", "rule": "IT_RULE",
            "category": "misspelling", "replacements": ["qual è"],
        }
    ]  # fmt: skip
    assert fake.requests[0]["language"] == ["it"]
    assert await languagetool.check(url, "en", "Nothing wrong here") == []
    assert fake.requests[1]["language"] == ["en-US"]
    assert await languagetool.check(url, "it", "  ") == []


async def test_availability_and_errors(server: tuple[str, Fake]) -> None:
    url, fake = server
    assert await languagetool.available(url) and not await languagetool.available("")
    assert not await languagetool.available("http://127.0.0.1:9")
    fake.status = 400
    with pytest.raises(WorkspaceError, match="refused"):
        await languagetool.check(url, "xx", "testo")
    with pytest.raises(WorkspaceError):
        await languagetool.check("ftp://example.org", "it", "testo")
