import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { canonicalize } from "../../lib/markdown/canonical";
import { createDocumentEditor, serializeBody } from "./document-editor";
import { composeDocument, parseDocument } from "./markdown-io";

const ROOT = join(__dirname, "../../../..");
const FIXTURES = join(ROOT, "fixtures/markdown");
const EXAMPLE = join(ROOT, "examples/progetto-esempio/capitoli");

/** Markdown file text -> Document mode -> Markdown file text. */
async function viaDocumentMode(text: string): Promise<string> {
  const { front, body } = parseDocument(text);
  const root = document.createElement("div");
  document.body.appendChild(root);
  const editor = await createDocumentEditor({ root, markdown: body });
  const out = composeDocument(front, serializeBody(editor));
  await editor.destroy();
  root.remove();
  return out;
}

const goldens = readdirSync(FIXTURES)
  .filter((f) => f.endsWith(".out.md"))
  .sort();
const examples = (readdirSync(EXAMPLE, { recursive: true }) as string[])
  .map(String)
  .filter((f) => f.endsWith(".md"))
  .sort();

describe("Markdown -> Document -> Markdown (RF-10c)", () => {
  it.each(goldens)("keeps canonical fixture %s unchanged", async (file) => {
    const text = readFileSync(join(FIXTURES, file), "utf8");
    expect(await viaDocumentMode(text)).toBe(text);
  });

  it.each(examples)("keeps example section %s stable once canonical", async (file) => {
    const canonical = canonicalize(readFileSync(join(EXAMPLE, file), "utf8"));
    expect(await viaDocumentMode(canonical)).toBe(canonical);
  });

  it("switching 10 times between modes never changes the text (M1 acceptance)", async () => {
    let text = canonicalize(
      readFileSync(join(EXAMPLE, "02-installazione/01-requisiti.md"), "utf8"),
    );
    const initial = text;
    for (let i = 0; i < 10; i++) text = await viaDocumentMode(text);
    expect(text).toBe(initial);
  });

  it("covers every element of RF-11 in the fixtures", () => {
    const all = goldens.map((f) => readFileSync(join(FIXTURES, f), "utf8")).join("\n");
    expect(all).toMatch(/^#{1,3} /m); // headings
    expect(all).toMatch(/^- /m); // bullet list
    expect(all).toMatch(/^1\. /m); // ordered list
    expect(all).toMatch(/^\| -+ /m); // pipe table
    expect(all).toMatch(/!\[[^\]]*\]\(/); // image with caption/alt
    expect(all).toMatch(/\[\^\w+\]:/); // footnote
    expect(all).toMatch(/^> /m); // quote
    expect(all).toMatch(/^```/m); // code
  });
});
