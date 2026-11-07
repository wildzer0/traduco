/** Tab-stops of a snippet (VS Code syntax): ``${1:default}``, ``${1}``, ``$1``, ``$0``. */
export interface Resolved {
  text: string;
  /** Range of the first tab-stop in `text` (the lowest number, `$0` last), if there is one. */
  first: { from: number; to: number } | null;
}

const STOP = /\$\{(\d+)(?::([^}]*))?\}|\$(\d+)/g;

export function resolveStops(source: string): Resolved {
  let text = "";
  let last = 0;
  let best: { n: number; from: number; to: number } | null = null;
  for (const m of source.matchAll(STOP)) {
    const n = Number(m[1] ?? m[3]);
    const fill = m[2] ?? "";
    text += source.slice(last, m.index);
    const from = text.length;
    text += fill;
    last = (m.index ?? 0) + m[0].length;
    const rank = n === 0 ? Number.MAX_SAFE_INTEGER : n;
    if (!best || rank < best.n) best = { n: rank, from, to: from + fill.length };
  }
  text += source.slice(last);
  return { text, first: best ? { from: best.from, to: best.to } : null };
}
