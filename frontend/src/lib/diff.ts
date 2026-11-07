export type DiffPart = { type: "same" | "add" | "del"; text: string };

const tokens = (text: string) => text.match(/\s+|[^\s]+/g) ?? [];

/**
 * Word-level difference between two texts (docs/03-ui.md: suggestions are shown as a diff).
 * Longest-common-subsequence over words and the spaces between them; adjacent parts of the same
 * kind are merged. Joining the `same` and `del` parts gives back `before`, `same` + `add` gives `after`.
 */
export function diffWords(before: string, after: string): DiffPart[] {
  const a = tokens(before);
  const b = tokens(after);
  // lcs[i][j]: length of the common subsequence of a[i:] and b[j:], stored flat
  const width = b.length + 1;
  const lcs = new Array<number>((a.length + 1) * width).fill(0);
  const at = (i: number, j: number) => lcs[i * width + j] ?? 0;
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      lcs[i * width + j] =
        a[i] === b[j] ? at(i + 1, j + 1) + 1 : Math.max(at(i + 1, j), at(i, j + 1));

  const parts: DiffPart[] = [];
  const push = (type: DiffPart["type"], text: string) => {
    const last = parts[parts.length - 1];
    if (last && last.type === type) last.text += text;
    else parts.push({ type, text });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push("same", a[i] as string);
      i++;
      j++;
    } else if (at(i + 1, j) >= at(i, j + 1)) push("del", a[i++] as string);
    else push("add", b[j++] as string);
  }
  while (i < a.length) push("del", a[i++] as string);
  while (j < b.length) push("add", b[j++] as string);
  return parts;
}
