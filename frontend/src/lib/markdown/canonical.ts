import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkStringify from "remark-stringify";
import { unified } from "unified";

/**
 * Canonical Markdown form (docs/02-architettura.md, RF-10c). Both editor modes save through this
 * function so switching mode never produces spurious Git diffs. Rules:
 * ATX headings, `-` bullets, `_em_`, `**strong**`, aligned pipe tables, fenced code, `---` rules,
 * one blank line between blocks, LF line endings, no trailing spaces, exactly one final newline.
 * The YAML front matter is kept verbatim (only line endings are normalised).
 *
 * Keep in sync with `fixtures/markdown/*.out.md`, which the backend test also checks.
 */
const processor = unified()
  .use(remarkParse)
  .use(remarkGfm, { tablePipeAlign: true })
  .use(remarkStringify, {
    bullet: "-",
    bulletOther: "*",
    emphasis: "_",
    strong: "*",
    fence: "`",
    fences: true,
    incrementListMarker: true,
    listItemIndent: "one",
    rule: "-",
    setext: false,
    resourceLink: false,
  });

const OPEN = /^---[ \t]*\n/;
const CLOSE = /^(?:---|\.\.\.)[ \t]*(?:\n|$)/m;

export function splitFrontMatter(text: string): { front: string; body: string } {
  const open = OPEN.exec(text);
  if (!open) return { front: "", body: text };
  const rest = text.slice(open[0].length);
  const close = CLOSE.exec(rest);
  if (!close) return { front: "", body: text }; // no closing fence: a thematic break, not metadata
  const end = open[0].length + close.index + close[0].length;
  const front = text.slice(0, end);
  return { front: front.endsWith("\n") ? front : `${front}\n`, body: text.slice(end) };
}

export function canonicalize(input: string): string {
  const text = input.replace(/\r\n?/g, "\n");
  const { front, body } = splitFrontMatter(text);
  const rendered = String(processor.processSync(body)).replace(/\n+$/, "");
  if (!rendered) return front;
  return front ? `${front}\n${rendered}\n` : `${rendered}\n`;
}
