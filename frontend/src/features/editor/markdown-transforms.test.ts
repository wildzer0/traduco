import { canonicalize } from "../../lib/markdown/canonical";
import type { CommandId } from "./commands";
import { commandEdits, type Edit } from "./markdown-transforms";

/** Apply edits (all expressed against the original document) and return text + caret. */
function run(doc: string, from: number, to: number, cmd: CommandId) {
  const edits = commandEdits(doc, from, to, cmd) as Edit[];
  let out = doc;
  for (const e of [...edits].sort((a, b) => b.from - a.from))
    out = out.slice(0, e.from) + e.insert + out.slice(e.to);
  const last = edits[edits.length - 1] as Edit;
  return {
    text: out,
    anchor: last.anchor,
    head: last.head,
    selected: out.slice(last.anchor, last.head),
  };
}

describe("inline formatting", () => {
  it("wraps a selection in bold and keeps it selected", () => {
    const r = run("un testo qui", 3, 8, "bold");
    expect(r.text).toBe("un **testo** qui");
    expect(r.selected).toBe("testo");
  });

  it("unwraps when the selection is already bold (markers outside or inside it)", () => {
    expect(run("un **testo** qui", 5, 10, "bold").text).toBe("un testo qui");
    expect(run("un **testo** qui", 3, 12, "bold").text).toBe("un testo qui");
  });

  it("inserts a marker pair with the caret between when nothing is selected", () => {
    const r = run("ab", 1, 1, "italic");
    expect(r.text).toBe("a__b");
    expect(r.anchor).toBe(2);
  });

  it("italic uses underscores (canonical form)", () => {
    expect(run("x", 0, 1, "italic").text).toBe("_x_");
  });
});

describe("headings", () => {
  it("sets, changes and toggles the level of the current line", () => {
    expect(run("Titolo", 2, 2, "heading2").text).toBe("## Titolo");
    expect(run("# Titolo", 2, 2, "heading3").text).toBe("### Titolo");
    expect(run("## Titolo", 4, 4, "heading2").text).toBe("Titolo");
  });

  it("only touches the line with the cursor", () => {
    expect(run("uno\ndue\ntre", 5, 5, "heading1").text).toBe("uno\n# due\ntre");
  });
});

describe("line prefixes", () => {
  it("makes a bullet list of the selected lines and toggles it off", () => {
    const on = run("uno\ndue\ntre", 0, 11, "bulletList").text;
    expect(on).toBe("- uno\n- due\n- tre");
    expect(run(on, 0, on.length, "bulletList").text).toBe("uno\ndue\ntre");
  });

  it("numbers ordered lists and skips blank lines", () => {
    expect(run("a\n\nb", 0, 4, "orderedList").text).toBe("1. a\n\n2. b");
  });

  it("quotes lines", () => {
    expect(run("a\nb", 0, 3, "quote").text).toBe("> a\n> b");
  });

  it("switching list kinds replaces the marker", () => {
    expect(run("1. a\n2. b", 0, 9, "bulletList").text).toBe(
      "- 1. a\n- 2. b".replace(/- \d\. /g, "- "),
    );
  });
});

describe("blocks", () => {
  it("inserts a table after the current paragraph, separated by blank lines", () => {
    const r = run("Prima\nDopo", 2, 2, "table");
    expect(r.text.startsWith("Prima\n\n| Colonna 1 | Colonna 2 |\n| --- | --- |\n|  |  |\n")).toBe(
      true,
    );
    expect(canonicalize(r.text)).toContain("| Colonna 1 | Colonna 2 |");
  });

  it("inserts a table into an empty document and on an empty line", () => {
    expect(run("", 0, 0, "table").text).toBe("| Colonna 1 | Colonna 2 |\n| --- | --- |\n|  |  |\n");
    expect(run("Testo\n\n", 7, 7, "table").text.startsWith("Testo\n\n| Colonna 1")).toBe(true);
  });

  it("wraps a selection in a code fence", () => {
    const r = run("a\ncodice\nb", 2, 8, "code");
    expect(r.text).toBe("a\n```\ncodice\n```\nb");
    expect(r.selected).toBe("codice");
  });

  it("inserts an empty code fence with the caret inside", () => {
    const r = run("", 0, 0, "code");
    expect(r.text).toBe("```\n\n```\n");
    expect(r.anchor).toBe(4);
  });

  it("inserts a mermaid diagram block", () => {
    expect(run("", 0, 0, "diagram").text).toBe(
      "```mermaid\nflowchart LR\n  A[Inizio] --> B[Fine]\n```\n",
    );
  });

  it("inserts a horizontal rule", () => {
    expect(run("a", 1, 1, "rule").text).toBe("a\n\n---\n");
  });
});

describe("links and footnotes", () => {
  it("wraps the selection in a link and selects the URL placeholder", () => {
    const r = run("vai qui ora", 4, 7, "link");
    expect(r.text).toBe("vai [qui](https://) ora");
  });

  it("creates the next free footnote with its definition at the end", () => {
    const r = run("Testo[^1] e altro\n\n[^1]: Nota.\n", 17, 17, "footnote");
    expect(r.text).toBe("Testo[^1] e altro[^2]\n\n[^1]: Nota.\n\n[^2]: ");
    expect(r.anchor).toBe(r.text.length);
  });

  it("starts at 1 and handles documents without trailing newline", () => {
    expect(run("Ciao", 4, 4, "footnote").text).toBe("Ciao[^1]\n\n[^1]: ");
  });
});

describe("results stay canonical", () => {
  it.each([
    "bold",
    "italic",
    "heading2",
    "bulletList",
    "orderedList",
    "quote",
    "table",
    "code",
    "rule",
    "diagram",
    "footnote",
    "link",
  ] as CommandId[])(
    "%s output is a fixed point of canonicalize (apart from empty placeholders)",
    (cmd) => {
      const out = run("Uno due\ntre quattro", 0, 7, cmd).text;
      const once = canonicalize(out);
      expect(canonicalize(once)).toBe(once);
    },
  );

  it("image is left to the shell", () => {
    expect(commandEdits("x", 0, 0, "image")).toBeNull();
  });
});
