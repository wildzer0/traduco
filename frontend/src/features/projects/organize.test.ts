import type { FolderInfo, ProjectSummary } from "../../lib/types";
import { ago, childrenOf, matches, projectsIn, sortProjects, withDescendants } from "./organize";

const p = (over: Partial<ProjectSummary>): ProjectSummary => ({
  id: "x",
  nome: "Manuale pompa",
  lingua_sorgente: "it",
  lingua_ufficiale: "en",
  ...over,
});

describe("searching projects", () => {
  const project = p({
    autore: "Mario Rossi",
    emissione: "3",
    percorso: ["Clienti", "ACME"],
    lingue: ["en", "de"],
  });

  it("needs every word, ignoring case and accents, in any of the details", () => {
    expect(matches(project, "")).toBe(true);
    expect(matches(project, "pompa acme")).toBe(true);
    expect(matches(project, "MARIO")).toBe(true);
    expect(matches(project, "clienti de")).toBe(true);
    expect(matches(project, "pompa luigi")).toBe(false);
    expect(matches(p({ nome: "Qualità" }), "qualita")).toBe(true);
  });
});

describe("sorting projects", () => {
  const list = [
    p({ id: "a", nome: "Beta", ultima_modifica: "2026-11-01T10:00:00+00:00", emissione: "10" }),
    p({ id: "b", nome: "alfa", ultima_modifica: "2026-11-05T10:00:00+00:00", emissione: "2" }),
    p({ id: "c", nome: "Gamma", emissione: "" }),
  ];

  it("by name without caring for case, by date, by issue as a number", () => {
    expect(sortProjects(list, "nome", "asc").map((x) => x.id)).toEqual(["b", "a", "c"]);
    expect(sortProjects(list, "ultima_modifica", "desc").map((x) => x.id)).toEqual(["b", "a", "c"]);
    expect(sortProjects(list, "emissione", "asc").map((x) => x.id)).toEqual(["b", "a", "c"]);
  });

  it("puts what has no value last, whichever way", () => {
    expect(sortProjects(list, "emissione", "desc").map((x) => x.id)).toEqual(["a", "b", "c"]);
  });
});

describe("folders", () => {
  const folders: FolderInfo[] = [
    { id: "f1", nome: "Clienti", genitore: null, percorso: ["Clienti"] },
    { id: "f2", nome: "ACME", genitore: "f1", percorso: ["Clienti", "ACME"] },
    { id: "f3", nome: "Interni", genitore: null, percorso: ["Interni"] },
    { id: "f4", nome: "2026", genitore: "f2", percorso: ["Clienti", "ACME", "2026"] },
  ];

  it("lists the children of a level, in order, and everything below a folder", () => {
    expect(childrenOf(folders, null).map((f) => f.id)).toEqual(["f1", "f3"]);
    expect(childrenOf(folders, "f1").map((f) => f.id)).toEqual(["f2"]);
    expect([...withDescendants(folders, "f1")].sort()).toEqual(["f1", "f2", "f4"]);
  });

  it("finds the projects of one level", () => {
    const list = [p({ id: "a", cartella: null }), p({ id: "b", cartella: "f1" }), p({ id: "c" })];
    expect(projectsIn(list, null).map((x) => x.id)).toEqual(["a", "c"]);
    expect(projectsIn(list, "f1").map((x) => x.id)).toEqual(["b"]);
  });
});

describe("relative dates", () => {
  const now = new Date("2026-11-08T12:00:00Z");
  it("speaks the language of the interface", () => {
    expect(ago("2026-11-08T09:00:00Z", now, "it")).toBe("3 ore fa");
    expect(ago("2026-11-07T12:00:00Z", now, "it")).toBe("ieri");
    expect(ago("2026-11-08T09:00:00Z", now, "en")).toBe("3 hours ago");
    expect(ago("", now, "it")).toBe("");
    expect(ago("not a date", now, "it")).toBe("");
  });
});
