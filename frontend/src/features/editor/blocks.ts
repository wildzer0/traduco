import MarkdownIt from "markdown-it";

const md = new MarkdownIt({ html: true });

/** Start line (0-based) of each top-level block of ``body``. */
export function blockStartLines(body: string): number[] {
  const starts: number[] = [];
  for (const token of md.parse(body, {})) {
    if (token.level === 0 && token.map && token.nesting >= 0 && token.type !== "inline") {
      const first = token.map[0];
      if (starts[starts.length - 1] !== first) starts.push(first);
    }
  }
  return starts;
}

/** Index of the top-level block that contains ``line`` (0-based). */
export function blockIndexAtLine(body: string, line: number): number {
  const starts = blockStartLines(body);
  let index = 0;
  starts.forEach((s, i) => {
    if (s <= line) index = i;
  });
  return index;
}

export function lineOfBlock(body: string, index: number): number {
  const starts = blockStartLines(body);
  return starts[Math.max(0, Math.min(index, starts.length - 1))] ?? 0;
}
