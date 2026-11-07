/** Case- and accent-insensitive subsequence match with a score (higher is better). */
export function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/**
 * `null` when `query` is not a subsequence of `text`. Consecutive letters, matches at the start of
 * a word and a short text score higher, so "esp" prefers "Esporta" over "Gestione del progetto".
 */
export function fuzzyScore(query: string, text: string): number | null {
  const q = fold(query).replace(/\s+/g, "");
  const t = fold(text);
  if (!q) return 0;
  let score = 0;
  let from = 0;
  let previous = -2;
  for (const ch of q) {
    const at = t.indexOf(ch, from);
    if (at < 0) return null;
    score += 1;
    if (at === previous + 1) score += 3; // consecutive
    if (at === 0 || /[\s\-_/.]/.test(t[at - 1] ?? "")) score += 4; // start of a word
    previous = at;
    from = at + 1;
  }
  return score - t.length * 0.05;
}
