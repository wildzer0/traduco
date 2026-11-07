import { type CommandId, DIAGRAM_TEMPLATE, TABLE_TEMPLATE } from "./commands";

/** A text edit plus where to put the selection afterwards (offsets in the *new* document). */
export interface Edit {
  from: number;
  to: number;
  insert: string;
  anchor: number;
  head: number;
}

function lineBounds(doc: string, from: number, to: number): { start: number; end: number } {
  const start = doc.lastIndexOf("\n", from - 1) + 1;
  const nl = doc.indexOf("\n", to);
  return { start, end: nl === -1 ? doc.length : nl };
}

export function wrapInline(doc: string, from: number, to: number, mark: string): Edit {
  const before = doc.slice(from - mark.length, from);
  const after = doc.slice(to, to + mark.length);
  if (before === mark && after === mark && from !== to) {
    // already wrapped: unwrap
    return {
      from: from - mark.length,
      to: to + mark.length,
      insert: doc.slice(from, to),
      anchor: from - mark.length,
      head: to - mark.length,
    };
  }
  const selected = doc.slice(from, to);
  if (selected.startsWith(mark) && selected.endsWith(mark) && selected.length >= mark.length * 2) {
    const inner = selected.slice(mark.length, selected.length - mark.length);
    return { from, to, insert: inner, anchor: from, head: from + inner.length };
  }
  const insert = `${mark}${selected}${mark}`;
  return from === to
    ? { from, to, insert, anchor: from + mark.length, head: from + mark.length }
    : { from, to, insert, anchor: from + mark.length, head: from + mark.length + selected.length };
}

export function setHeading(doc: string, from: number, to: number, level: number): Edit {
  const { start, end } = lineBounds(doc, from, from === to ? from : from);
  const line = doc.slice(start, end);
  const m = /^(#{1,6})\s+/.exec(line);
  const prefix = `${"#".repeat(level)} `;
  const text = m ? line.slice(m[0].length) : line;
  const insert = m && m[1]?.length === level ? text : `${prefix}${text}`; // same level again: back to paragraph
  const caret = start + insert.length;
  return { from: start, to: end, insert, anchor: caret, head: caret };
}

const ANY_LIST = /^(?:[-*+]|\d+[.)])\s+/;

export function toggleLinePrefix(
  doc: string,
  from: number,
  to: number,
  kind: "bullet" | "ordered" | "quote",
): Edit {
  const { start, end } = lineBounds(doc, from, to);
  const lines = doc.slice(start, end).split("\n");
  const own = kind === "bullet" ? /^[-*+]\s+/ : kind === "ordered" ? /^\d+[.)]\s+/ : /^>\s?/;
  const active = lines.every((l) => l.trim() === "" || own.test(l));
  let n = 0;
  const out = lines.map((l) => {
    if (active) return l.replace(own, "");
    if (l.trim() === "") return l;
    n += 1;
    const bare = kind === "quote" ? l : l.replace(ANY_LIST, ""); // switching list kind replaces the marker
    const marker = kind === "bullet" ? "- " : kind === "ordered" ? `${n}. ` : "> ";
    return `${marker}${bare}`;
  });
  const insert = out.join("\n");
  return { from: start, to: end, insert, anchor: start, head: start + insert.length };
}

/** Insert a block (table, code, rule...) on its own lines, separated by blank lines. */
export function insertBlock(
  doc: string,
  at: number,
  block: string,
  caretInBlock?: [number, number],
): Edit {
  const lineStart = doc.lastIndexOf("\n", at - 1) + 1;
  const nl = doc.indexOf("\n", at);
  const lineEnd = nl === -1 ? doc.length : nl;
  const lineIsEmpty = doc.slice(lineStart, lineEnd).trim() === "";
  const from = lineIsEmpty ? lineStart : lineEnd;
  const to = lineIsEmpty ? lineEnd : lineEnd;
  const lead =
    from === 0
      ? ""
      : lineIsEmpty && doc.slice(Math.max(0, from - 2), from) === "\n\n"
        ? ""
        : lineIsEmpty
          ? "\n"
          : "\n\n";
  const tail = to >= doc.length ? "\n" : "\n";
  const insert = `${lead}${block}${tail}`;
  const base = from + lead.length;
  const [a, b] = caretInBlock ?? [block.length, block.length];
  return { from, to, insert, anchor: base + a, head: base + b };
}

export function wrapFence(doc: string, from: number, to: number, lang = ""): Edit {
  const selected = doc.slice(from, to);
  const block = `\`\`\`${lang}\n${selected}\n\`\`\``;
  if (from === to) return insertBlock(doc, from, block, [3 + lang.length + 1, 3 + lang.length + 1]);
  return {
    from,
    to,
    insert: block,
    anchor: from + 3 + lang.length + 1,
    head: from + 3 + lang.length + 1 + selected.length,
  };
}

export function insertLink(doc: string, from: number, to: number): Edit {
  const text = doc.slice(from, to) || "testo";
  const insert = `[${text}](https://)`;
  const urlStart = from + text.length + 3;
  return { from, to, insert, anchor: urlStart + 8, head: urlStart + 8 };
}

/** Footnote marker at the cursor plus its definition at the end of the document. */
export function insertFootnote(doc: string, at: number): Edit[] {
  const used = [...doc.matchAll(/\[\^(\d+)\]/g)].map((m) => Number(m[1]));
  const n = (used.length ? Math.max(...used) : 0) + 1;
  const marker = `[^${n}]`;
  const gap = doc.endsWith("\n\n") ? "" : doc.endsWith("\n") ? "\n" : "\n\n";
  const definition = `${gap}[^${n}]: `;
  if (at === doc.length) {
    const insert = marker + definition;
    return [{ from: at, to: at, insert, anchor: at + insert.length, head: at + insert.length }];
  }
  const caret = doc.length + marker.length + definition.length;
  return [
    { from: at, to: at, insert: marker, anchor: at + marker.length, head: at + marker.length },
    { from: doc.length, to: doc.length, insert: definition, anchor: caret, head: caret },
  ];
}

export function insertImageRef(at: number, src: string, alt: string): Edit {
  const insert = `![${alt}](${src})`;
  return { from: at, to: at, insert, anchor: at + 2, head: at + 2 + alt.length };
}

export function commandEdits(doc: string, from: number, to: number, cmd: CommandId): Edit[] | null {
  switch (cmd) {
    case "bold":
      return [wrapInline(doc, from, to, "**")];
    case "italic":
      return [wrapInline(doc, from, to, "_")];
    case "heading1":
      return [setHeading(doc, from, to, 1)];
    case "heading2":
      return [setHeading(doc, from, to, 2)];
    case "heading3":
      return [setHeading(doc, from, to, 3)];
    case "bulletList":
      return [toggleLinePrefix(doc, from, to, "bullet")];
    case "orderedList":
      return [toggleLinePrefix(doc, from, to, "ordered")];
    case "quote":
      return [toggleLinePrefix(doc, from, to, "quote")];
    case "table":
      return [insertBlock(doc, to, TABLE_TEMPLATE, [2, 11])];
    case "code":
      return [wrapFence(doc, from, to)];
    case "diagram":
      return [insertBlock(doc, to, `\`\`\`mermaid\n${DIAGRAM_TEMPLATE}\n\`\`\``)];
    case "rule":
      return [insertBlock(doc, to, "---")];
    case "link":
      return [insertLink(doc, from, to)];
    case "footnote":
      return insertFootnote(doc, to);
    case "image":
      return null; // handled by the shell: needs a file
  }
}
