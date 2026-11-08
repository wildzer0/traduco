import { createRenderer } from "./render";

const render = createRenderer({ projectId: "demo", sectionPath: "capitoli/01-a/01-s.md" });

describe("preview renderer", () => {
  it("leaves a place for the rows of a CSV attachment and links the other attachments", () => {
    const html = render("![Dati](allegati/dati.csv)\n\n[Manuale](allegati/man.pdf)\n");
    expect(html).toContain('<div class="csv-table" data-csv="dati.csv" data-title="Dati">');
    expect(html).toContain('href="/api/projects/demo/attachments/man.pdf"');
  });

  it("numbers top-level blocks like the editor does", () => {
    const html = render("# T\n\npar\n\n- a\n- b\n\n| x |\n| - |\n| 1 |\n");
    expect(html).toMatch(/<h1 data-block="0"/);
    expect(html).toMatch(/<p data-block="1"/);
    expect(html).toContain('<ul data-block="2">');
    expect(html).toContain('<table data-block="3">');
  });

  it("tags translatable blocks with the key the backend gives their segment", () => {
    const html = render(
      "# T\n\npar\n\n- a\n- b\n\n> q\n\n| x | y |\n| - | - |\n| 1 | 2 |\n\nNota[^1]\n\n[^1]: nota\n",
    );
    for (const key of [
      "h:0",
      "p:0",
      "li:0",
      "li:1",
      "q:0",
      "th:0:0",
      "th:0:1",
      "td:0:0:0",
      "td:0:0:1",
      "p:1",
      "fn:0",
    ]) {
      expect(html, key).toContain(`data-seg="${key}"`);
    }
  });

  it("escapes raw HTML instead of emitting it", () => {
    const html = render(
      "<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\ntesto <b>x</b>",
    );
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<b>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("does not turn javascript: and data: URLs into links", () => {
    const html = render("[x](javascript:alert(1)) [y](data:text/html;base64,AA) [z](vbscript:x)");
    expect(html).not.toMatch(/href="(javascript|data|vbscript):/i);
  });

  it("opens external links in a new tab safely, leaves relative links alone", () => {
    const html = render("[a](https://example.com) [b](../02-x/01-y.md#h)");
    expect(html).toContain('href="https://example.com" target="_blank" rel="noopener noreferrer"');
    expect(html).toContain('<a href="../02-x/01-y.md#h">b</a>');
  });

  it("resolves relative images through the assets API, keeps absolute ones", () => {
    const html = render("![Schema](img/a.png) ![Ext](https://x.org/b.png)");
    expect(html).toContain('src="/api/projects/demo/assets?path=capitoli%2F01-a%2Fimg%2Fa.png"');
    expect(html).toContain('alt="Schema"');
    expect(html).toContain('src="https://x.org/b.png"');
  });

  it("renders footnotes", () => {
    const html = render("Testo[^1]\n\n[^1]: Nota.\n");
    expect(html).toContain("footnote-ref");
    expect(html).toContain("Nota.");
  });

  it("turns mermaid fences into diagram placeholders and keeps other code intact", () => {
    const html = render(
      "```mermaid\nflowchart LR\n  A --> B\n```\n\n```js\nconst a = '<b>';\n```\n",
    );
    expect(html).toContain(
      'class="mermaid-block" data-block="0" data-code="flowchart LR\n  A --&gt; B\n"',
    );
    expect(html).toContain("const a = '&lt;b&gt;';");
  });

  it("renders tables, quotes, lists and task-free text without throwing on odd input", () => {
    expect(() => render("")).not.toThrow();
    expect(() => render("|\n|-|\n```\n[^x]:")).not.toThrow();
  });
});
