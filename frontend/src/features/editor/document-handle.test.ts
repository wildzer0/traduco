import type { Editor } from "@milkdown/kit/core";
import { editorViewCtx } from "@milkdown/kit/core";
import { TextSelection } from "@milkdown/kit/prose/state";
import { canonicalize } from "../../lib/markdown/canonical";
import type { CommandId } from "./commands";
import { createDocumentEditor, serializeBody } from "./document-editor";
import { createDocumentHandle } from "./document-handle";

async function withEditor(markdown: string, fn: (editor: Editor) => void | Promise<void>) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const editor = await createDocumentEditor({ root, markdown });
  try {
    await fn(editor);
  } finally {
    await editor.destroy();
    root.remove();
  }
}

/** Select text offsets inside the document (positions as seen by ProseMirror). */
function select(editor: Editor, from: number, to = from) {
  const v = editor.ctx.get(editorViewCtx);
  v.dispatch(v.state.tr.setSelection(TextSelection.create(v.state.doc, from, to)));
}

async function apply(markdown: string, cmd: CommandId, from: number, to = from): Promise<string> {
  let out = "";
  await withEditor(markdown, (editor) => {
    select(editor, from, to);
    createDocumentHandle(editor).run(cmd);
    out = canonicalize(serializeBody(editor)); // the shell always saves the canonical form
  });
  return out;
}

describe("Document mode commands", () => {
  it("bold and italic wrap the selection", async () => {
    expect(await apply("un testo qui\n", "bold", 4, 9)).toBe("un **testo** qui\n");
    expect(await apply("un testo qui\n", "italic", 4, 9)).toBe("un _testo_ qui\n");
  });

  it("headings change the block type", async () => {
    expect(await apply("Titolo\n", "heading2", 2)).toBe("## Titolo\n");
  });

  it("lists and quotes wrap the paragraph", async () => {
    expect(await apply("voce\n", "bulletList", 2)).toBe("- voce\n");
    expect(await apply("voce\n", "orderedList", 2)).toBe("1. voce\n");
    expect(await apply("cit\n", "quote", 2)).toBe("> cit\n");
  });

  it("inserts a table, a rule and a diagram block", async () => {
    expect(await apply("a\n", "table", 2)).toContain("| ");
    expect(await apply("a\n\nb\n", "rule", 2)).toContain("---");
    expect(await apply("a\n", "diagram", 2)).toContain("```mermaid\nflowchart LR");
  });

  it("creates a code block", async () => {
    expect(await apply("codice\n", "code", 2)).toContain("```");
  });

  it("makes a link", async () => {
    expect(await apply("vai qui ora\n", "link", 5, 8)).toContain("[qui](https://)");
  });

  it("inserts an image", async () => {
    let out = "";
    await withEditor("testo\n", (editor) => {
      select(editor, 2);
      createDocumentHandle(editor).insertImage("img/a.png", "Schema");
      out = serializeBody(editor);
    });
    expect(out).toContain("![Schema](img/a.png)");
  });

  it("adds the next footnote marker and its definition", async () => {
    const out = await apply("Testo[^1] e altro\n\n[^1]: Nota.\n", "footnote", 15);
    expect(out).toContain("altro[^2]");
    expect(out).toMatch(/^\[\^2\]:/m);
    expect(out).toContain("[^1]: Nota.");
    expect(out).not.toContain("\\[");
  });

  it("reports an edit immediately, long before the debounced markdown arrives", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    const edits: string[] = [];
    const changes: string[] = [];
    const editor = await createDocumentEditor({
      root,
      markdown: "testo\n",
      onEdit: () => edits.push("edit"),
      onChange: (md) => changes.push(md),
    });
    select(editor, 1, 4); // a range: bold on a bare cursor only sets a stored mark
    createDocumentHandle(editor).run("bold");
    expect(edits.length).toBeGreaterThan(0);
    expect(changes).toHaveLength(0); // the text arrives later (milkdown debounces it)
    await editor.destroy();
    root.remove();
  });

  it("reports and restores the top-level block index", async () => {
    await withEditor("# T\n\nuno\n\ndue\n", (editor) => {
      const h = createDocumentHandle(editor);
      h.setBlockIndex(2);
      expect(h.blockIndex()).toBe(2);
      h.setBlockIndex(99);
      expect(h.blockIndex()).toBe(2);
      h.setBlockIndex(0);
      expect(h.blockIndex()).toBe(0);
    });
  });
});
