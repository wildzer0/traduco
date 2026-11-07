"""Web and plain formats (RF-85): one self-contained HTML file, EPUB, single Markdown.

The HTML opens from ``file://`` with no server: styles and script are inline, images are embedded,
the index and the search work on the page itself. Raw HTML in the sources is switched off in the
Pandoc input, so a section cannot add a script of its own.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import re
import zipfile
from pathlib import Path

from app.core.export import pandoc as pandoc_mod
from app.core.export.combine import Combined

LABELS = {
    "it": {"search": "Cerca nel documento", "index": "Indice", "none": "Nessun risultato"},
    "en": {"search": "Search the document", "index": "Contents", "none": "No results"},
}

PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg:#fff; --fg:#1d2430; --muted:#5b6575; --line:#d9dee7; --accent:#1f4e79; --mark:#fff2a8; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#14181f; --fg:#e6e9ef; --muted:#9aa4b2; --line:#2b3340; --accent:#7fb2e5; --mark:#5c4b00; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin:0; font:16px/1.6 system-ui, sans-serif; background:var(--bg); color:var(--fg); display:flex; }}
nav {{ position:sticky; top:0; align-self:flex-start; height:100vh; width:300px; flex:none; overflow:auto;
  padding:16px; border-right:1px solid var(--line); }}
nav input {{ width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px;
  background:var(--bg); color:var(--fg); }}
nav h2 {{ font-size:13px; text-transform:uppercase; color:var(--muted); margin:16px 0 4px; }}
nav ul {{ list-style:none; margin:0; padding:0; }}
nav li {{ margin:2px 0; }}
nav li.l2 {{ padding-left:12px; }} nav li.l3 {{ padding-left:24px; }}
nav a {{ color:var(--fg); text-decoration:none; }} nav a:hover, nav a.on {{ color:var(--accent); }}
main {{ flex:1; min-width:0; max-width:860px; padding:24px 32px 96px; }}
h1,h2,h3,h4 {{ line-height:1.25; scroll-margin-top:12px; }}
img {{ max-width:100%; height:auto; }}
table {{ border-collapse:collapse; }} th,td {{ border:1px solid var(--line); padding:4px 8px; }}
pre, code {{ font-family:ui-monospace, monospace; }} pre {{ overflow:auto; padding:8px; background:rgba(127,127,127,.12); }}
blockquote {{ margin:1em 0; padding-left:1em; border-left:3px solid var(--line); color:var(--muted); }}
mark {{ background:var(--mark); color:inherit; }}
.hit {{ display:none; }} #none {{ display:none; color:var(--muted); }}
@media (max-width:760px) {{ body {{ display:block; }} nav {{ position:static; height:auto; width:auto; border:0; }} }}
@media print {{ nav {{ display:none; }} }}
</style>
</head>
<body>
<nav aria-label="{index}">
<input id="q" type="search" placeholder="{search}" aria-label="{search}">
<h2>{index}</h2>
<ul id="toc">{toc}</ul>
</nav>
<main id="doc">
<h1 class="title">{title}</h1>
{body}
<p id="none">{none}</p>
</main>
<script>
(function () {{
  var doc = document.getElementById("doc"), q = document.getElementById("q");
  var blocks = Array.prototype.slice.call(doc.children).filter(function (e) {{ return e.id !== "none" && !e.classList.contains("title"); }});
  var none = document.getElementById("none");
  function clear() {{
    doc.querySelectorAll("mark").forEach(function (m) {{ m.replaceWith(document.createTextNode(m.textContent)); }});
    doc.normalize();
  }}
  function mark(node, re) {{
    var walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT), found = [], n;
    while ((n = walker.nextNode())) if (re.test(n.nodeValue)) found.push(n);
    found.forEach(function (t) {{
      var parts = t.nodeValue.split(re), frag = document.createDocumentFragment();
      parts.forEach(function (p, i) {{
        if (i % 2) {{ var m = document.createElement("mark"); m.textContent = p; frag.appendChild(m); }}
        else frag.appendChild(document.createTextNode(p));
      }});
      t.replaceWith(frag);
    }});
  }}
  q.addEventListener("input", function () {{
    clear();
    var text = q.value.trim(), shown = 0;
    if (!text) {{ blocks.forEach(function (b) {{ b.classList.remove("hit"); b.style.display = ""; }}); none.style.display = "none"; return; }}
    var re = new RegExp("(" + text.replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&") + ")", "i");
    blocks.forEach(function (b) {{
      var ok = re.test(b.textContent);
      b.style.display = ok ? "" : "none";
      if (ok) {{ shown++; mark(b, new RegExp(re.source, "gi")); }}
    }});
    none.style.display = shown ? "none" : "block";
  }});
  var links = Array.prototype.slice.call(document.querySelectorAll("#toc a"));
  function onScroll() {{
    var current = null;
    links.forEach(function (a) {{
      var t = document.getElementById(decodeURIComponent(a.hash.slice(1)));
      if (t && t.getBoundingClientRect().top < 80) current = a;
    }});
    links.forEach(function (a) {{ a.classList.toggle("on", a === current); }});
  }}
  window.addEventListener("scroll", onScroll, {{ passive: true }}); onScroll();
}})();
</script>
</body>
</html>
"""

_HEADING = re.compile(r"<h([1-3])\b[^>]*\bid=\"([^\"]+)\"[^>]*>(.*?)</h\1>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_IMG = re.compile(r'(<img\b[^>]*\bsrc=")([^"]+)(")')


def _embed_images(body: str, work: Path) -> str:
    def inline(match: re.Match[str]) -> str:
        source = match.group(2)
        path = (work / source).resolve()
        if source.startswith(("data:", "http:", "https:")) or work.resolve() not in path.parents:
            return match.group(0)
        if not path.is_file():
            return match.group(0)
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"{match.group(1)}data:{kind};base64,{data}{match.group(3)}"

    return _IMG.sub(inline, body)


def build_html(
    pandoc: Path, combined: Combined, work: Path, output: Path, title: str, lang: str
) -> None:
    source = work / "document.md"
    source.write_text(combined.markdown, encoding="utf-8")
    body = pandoc_mod.convert(
        pandoc, source, None, "html5", resource_dir=work, extra=["--section-divs", "--no-highlight"]
    )
    body = _embed_images(body, work)
    toc = "".join(
        f'<li class="l{level}"><a href="#{html.escape(ident, quote=True)}">'
        f"{html.escape(html.unescape(_TAG.sub('', text)).strip())}</a></li>"
        for level, ident, text in _HEADING.findall(body)
    )
    labels = LABELS.get(lang, LABELS["en"])
    page = PAGE.format(
        lang=html.escape(lang), title=html.escape(title), toc=toc, body=body, **labels
    )
    output.write_text(page, encoding="utf-8")


def build_epub(
    pandoc: Path, combined: Combined, work: Path, output: Path, title: str, lang: str
) -> None:
    source = work / "document.md"
    source.write_text(combined.markdown, encoding="utf-8")
    pandoc_mod.convert(
        pandoc,
        source,
        output,
        "epub3",
        resource_dir=work,
        extra=["--toc", "--toc-depth=3", f"--metadata=title:{title}", f"--metadata=lang:{lang}"],
    )


def build_markdown(combined: Combined, work: Path, output: Path) -> Path:
    """One ``.md``; with images, a ``.zip`` holding the file and its ``img/`` folder."""
    if not combined.assets:
        output = output.with_suffix(".md")
        output.write_text(combined.markdown, encoding="utf-8")
        return output
    output = output.with_suffix(".zip")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.md", combined.markdown)
        for name in combined.assets:
            archive.write(work / name, name)
    return output
