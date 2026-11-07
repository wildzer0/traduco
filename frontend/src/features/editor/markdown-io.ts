import { canonicalize, splitFrontMatter } from "../../lib/markdown/canonical";

/** A section split into the YAML front matter (kept verbatim) and the Markdown body. */
export interface ParsedDocument {
  front: string;
  body: string;
}

export function parseDocument(text: string): ParsedDocument {
  return splitFrontMatter(text.replace(/\r\n?/g, "\n"));
}

/** Rebuild the file text from untouched front matter and an edited body, in canonical form. */
export function composeDocument(front: string, body: string): string {
  return canonicalize(front ? `${front}\n${body}` : body);
}
