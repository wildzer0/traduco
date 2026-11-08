import { fold } from "../../lib/fuzzy";
import type { FolderInfo, ProjectSummary } from "../../lib/types";

export type SortKey = "ultima_modifica" | "nome" | "emissione" | "autore";

/** Every word of the search must be found in the name, author, issue, folder or languages. */
export function matches(project: ProjectSummary, query: string): boolean {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const haystack = fold(
    [
      project.nome,
      project.autore ?? "",
      project.emissione ?? "",
      (project.percorso ?? []).join(" "),
      (project.lingue ?? []).join(" "),
      project.lingua_sorgente,
    ].join(" "),
  );
  return words.every((w) => haystack.includes(w));
}

export function sortProjects(
  list: ProjectSummary[],
  key: SortKey,
  direction: "asc" | "desc",
): ProjectSummary[] {
  const sign = direction === "asc" ? 1 : -1;
  const value = (p: ProjectSummary) => (key === "nome" ? p.nome : (p[key] ?? ""));
  return [...list].sort((a, b) => {
    const x = value(a);
    const y = value(b);
    // a project without a value (no issue yet, no author) goes last whichever way we sort
    if (!x && y) return 1;
    if (x && !y) return -1;
    return sign * x.localeCompare(y, undefined, { numeric: true, sensitivity: "base" });
  });
}

export const childrenOf = (folders: FolderInfo[], parent: string | null): FolderInfo[] =>
  folders
    .filter((f) => f.genitore === parent)
    .sort((a, b) => a.nome.localeCompare(b.nome, undefined, { sensitivity: "base" }));

/** The folder and everything under it. */
export function withDescendants(folders: FolderInfo[], id: string): Set<string> {
  const found = new Set([id]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const f of folders) {
      if (f.genitore && found.has(f.genitore) && !found.has(f.id)) {
        found.add(f.id);
        grew = true;
      }
    }
  }
  return found;
}

/** Projects directly in a folder (null: the top level). */
export const projectsIn = (projects: ProjectSummary[], folder: string | null) =>
  projects.filter((p) => (p.cartella ?? null) === folder);

/** "3 hours ago", "yesterday"... in the interface language; the exact time goes in a tooltip. */
export function ago(iso: string | undefined, now: Date, locale: string): string {
  if (!iso) return "";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const seconds = Math.round((then.getTime() - now.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return rtf.format(0, "second");
}
