import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { canonicalize, splitFrontMatter } from "./canonical";

const FIXTURES = join(__dirname, "../../../../fixtures/markdown");
const inputs = readdirSync(FIXTURES)
  .filter((f) => f.endsWith(".in.md"))
  .sort();

describe("canonical form: golden files", () => {
  it.each(inputs)("%s", (file) => {
    const input = readFileSync(join(FIXTURES, file), "utf8");
    const outPath = join(FIXTURES, file.replace(".in.md", ".out.md"));
    const actual = canonicalize(input);
    if (process.env.UPDATE_GOLDEN === "1") writeFileSync(outPath, actual);
    expect(existsSync(outPath), `missing ${outPath}; run UPDATE_GOLDEN=1 and review it`).toBe(true);
    expect(actual).toBe(readFileSync(outPath, "utf8"));
  });
});

describe("canonical form: invariants", () => {
  const sources = [
    ...inputs.map((f) => readFileSync(join(FIXTURES, f), "utf8")),
    ...readdirSync(join(FIXTURES, "../../examples/progetto-esempio/capitoli"), {
      recursive: true,
    })
      .map(String)
      .filter((f) => f.endsWith(".md"))
      .map((f) =>
        readFileSync(join(FIXTURES, "../../examples/progetto-esempio/capitoli", f), "utf8"),
      ),
  ];

  it("is idempotent on every fixture and on the example project", () => {
    for (const text of sources) {
      const once = canonicalize(text);
      expect(canonicalize(once)).toBe(once);
    }
  });

  it("uses LF only, no trailing spaces, at most one blank line, one final newline", () => {
    for (const text of sources) {
      const out = canonicalize(text);
      expect(out).not.toContain("\r");
      expect(out).not.toMatch(/[ \t]+\n/);
      expect(out).not.toMatch(/\n\n\n/);
      if (out) expect(out).toMatch(/[^\n]\n$/);
    }
  });

  it("keeps a real CRLF fixture (see .gitattributes)", () => {
    expect(readFileSync(join(FIXTURES, "crlf.in.md"), "utf8")).toContain("\r\n");
  });

  it("treats CRLF and LF input as the same document", () => {
    const lf = "# T\n\nUno\n\n- a\n- b\n";
    expect(canonicalize(lf.replace(/\n/g, "\r\n"))).toBe(canonicalize(lf));
  });

  it("never alters text inside code fences or inline code", () => {
    const code = "```\n*  not emphasis  *\n  indented   \n```\n";
    expect(canonicalize(code)).toBe(code);
    expect(canonicalize("`a   *b*   c`\n")).toBe("`a   *b*   c`\n");
  });

  it("keeps placeholders and protected tokens intact", () => {
    const text = "{{codice_documento}} ⟦1⟧ ⟦b⟧x⟦/b⟧\n";
    expect(canonicalize(text)).toBe(text);
  });

  it("returns an empty string for an empty document", () => {
    expect(canonicalize("")).toBe("");
    expect(canonicalize("\n\n  \n")).toBe("");
  });
});

describe("splitFrontMatter", () => {
  it("separates metadata from the body", () => {
    expect(splitFrontMatter("---\ntitle: A\n---\nCorpo\n")).toEqual({
      front: "---\ntitle: A\n---\n",
      body: "Corpo\n",
    });
  });

  it("does not mistake a thematic break for metadata", () => {
    const text = "---\nnessuna chiusura\n";
    expect(splitFrontMatter(text)).toEqual({ front: "", body: text });
  });

  it("handles a file that is only metadata", () => {
    expect(splitFrontMatter("---\ntitle: A\n---")).toEqual({
      front: "---\ntitle: A\n---\n",
      body: "",
    });
  });
});
