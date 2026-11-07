/**
 * Follow a rename done by the server. ``renamed`` maps old project-relative paths to new ones; renaming a
 * chapter also moves everything below it, so the longest matching prefix wins.
 */
export function remapPath(path: string, renamed: Record<string, string>): string {
  let best: string | null = null;
  for (const old of Object.keys(renamed)) {
    if (
      (path === old || path.startsWith(`${old}/`)) &&
      (best === null || old.length > best.length)
    ) {
      best = old;
    }
  }
  if (best === null) return path;
  return `${renamed[best]}${path.slice(best.length)}`;
}

/** Directory part of a project-relative path (``null`` for a top-level chapter). */
export function parentOf(path: string): string | null {
  const i = path.lastIndexOf("/");
  const parent = path.slice(0, i);
  return parent === "capitoli" ? null : parent;
}

export function isInside(path: string, ancestor: string): boolean {
  return path === ancestor || path.startsWith(`${ancestor}/`);
}
