import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createAppRouter, memoryHistory } from "../../app/router";
import { usePrefs } from "../../lib/prefs";
import type { FolderInfo, ProjectSummary } from "../../lib/types";
import { health, installFakeApi } from "../../test/fake-api";

const folders: FolderInfo[] = [
  { id: "f1", nome: "Clienti", genitore: null, percorso: ["Clienti"] },
  { id: "f2", nome: "ACME", genitore: "f1", percorso: ["Clienti", "ACME"] },
];
const project = (over: Partial<ProjectSummary>): ProjectSummary => ({
  id: "p",
  nome: "P",
  lingua_sorgente: "it",
  lingua_ufficiale: "en",
  cartella: null,
  percorso: [],
  autore: "",
  emissione: "",
  ultima_modifica: new Date(Date.now() - 3 * 3600_000).toISOString(),
  sezioni: 4,
  lingue: ["en"],
  ...over,
});
const projects = [
  project({ id: "libero", nome: "Progetto libero" }),
  project({
    id: "pompa",
    nome: "Manuale pompa",
    cartella: "f2",
    percorso: ["Clienti", "ACME"],
    autore: "Mario Rossi",
    emissione: "3",
    lingue: ["en", "de"],
  }),
];

function mount(path = "/", state = { folders, projects }) {
  const calls = installFakeApi([
    health,
    (c) => (c.url === "/api/workspace" ? { body: state } : undefined),
    (c) =>
      c.url === "/api/trash" && c.method === "GET"
        ? {
            body: [
              {
                name: "20261101T100000Z-vecchio",
                id: "vecchio",
                nome: "Vecchio manuale",
                deleted_at: "2026-11-01T10:00:00+00:00",
              },
            ],
          }
        : undefined,
    (c) =>
      c.method !== "GET" ? { body: { id: "x", nome: "x", trash: "t", cartella: null } } : undefined,
  ]);
  const router = createAppRouter(memoryHistory(path));
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router as never} />
    </QueryClientProvider>,
  );
  return { calls, router };
}

beforeEach(() => usePrefs.setState({ locale: "it" }));
afterEach(() => vi.unstubAllGlobals());

describe("projects page", () => {
  it("shows the top level with its folders, and what each project is at a glance", async () => {
    mount();
    const rows = await screen.findAllByTestId("project-row");
    expect(rows).toHaveLength(1); // only the loose project: the other one is inside a folder
    expect(within(rows[0] as HTMLElement).getByText("Progetto libero")).toBeInTheDocument();
    expect(within(rows[0] as HTMLElement).getByText("3 ore fa")).toBeInTheDocument();
    const tree = screen.getByRole("navigation", { name: "Cartelle" });
    expect(within(tree).getByText("Clienti")).toBeInTheDocument();
  });

  it("opens a folder, shows its details, and the path is clickable", async () => {
    const user = userEvent.setup();
    const { router } = mount("/?c=f2");
    const row = await screen.findByTestId("project-row");
    expect(within(row).getByText("Manuale pompa")).toBeInTheDocument();
    expect(within(row).getByText("Emissione 3")).toBeInTheDocument();
    expect(within(row).getByText("Mario Rossi")).toBeInTheDocument();
    expect(within(row).getByText("it → en, de")).toBeInTheDocument();
    const where = screen.getByRole("navigation", { name: "Dove sei" });
    await user.click(within(where).getByRole("button", { name: "Clienti" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ c: "f1" }));
  });

  it("searches every folder at once and says where each result is", async () => {
    const user = userEvent.setup();
    mount();
    await user.type(await screen.findByRole("searchbox"), "mario acme");
    const row = await screen.findByTestId("project-row");
    expect(within(row).getByText("Manuale pompa")).toBeInTheDocument();
    expect(within(row).getByText("Clienti › ACME")).toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "inesistente");
    expect(await screen.findByText(/Nessun progetto corrisponde/)).toBeInTheDocument();
  });

  it("creates a folder inside the folder one is looking at", async () => {
    const user = userEvent.setup();
    const { calls } = mount("/?c=f1");
    await user.click(await screen.findByRole("button", { name: "Nuova cartella" }));
    await user.type(screen.getByLabelText("Nome della cartella"), "2026");
    await user.click(screen.getByRole("button", { name: "Crea" }));
    await waitFor(() =>
      expect(calls.some((c) => c.url === "/api/folders" && c.method === "POST")).toBe(true),
    );
    expect(calls.find((c) => c.url === "/api/folders")?.body).toEqual({
      nome: "2026",
      genitore: "f1",
    });
  });

  it("duplicates a project under a name of the author's choice", async () => {
    const user = userEvent.setup();
    const { calls } = mount();
    await user.click(await screen.findByRole("button", { name: "Azioni su Progetto libero" }));
    await user.click(await screen.findByRole("menuitem", { name: "Duplica…" }));
    const name = screen.getByLabelText("Nome della copia");
    expect(name).toHaveValue("Progetto libero (copia)");
    await user.clear(name);
    await user.type(name, "Versione cliente");
    await user.click(screen.getByRole("button", { name: "Duplica" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/duplicate"))).toBe(true));
    expect(calls.find((c) => c.url.endsWith("/duplicate"))?.body).toEqual({
      nome: "Versione cliente",
    });
  });

  it("moves a project to a folder from the dialog", async () => {
    const user = userEvent.setup();
    const { calls } = mount();
    await user.click(await screen.findByRole("button", { name: "Azioni su Progetto libero" }));
    await user.click(await screen.findByRole("menuitem", { name: "Sposta in…" }));
    await user.click(screen.getByRole("radio", { name: "ACME" }));
    await user.click(screen.getByRole("button", { name: "Sposta qui" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/folder"))).toBe(true));
    expect(calls.find((c) => c.url.endsWith("/folder"))?.body).toEqual({ cartella: "f2" });
  });

  it("asks before deleting, and says the project goes to the trash", async () => {
    const user = userEvent.setup();
    const { calls } = mount();
    await user.click(await screen.findByRole("button", { name: "Azioni su Progetto libero" }));
    await user.click(await screen.findByRole("menuitem", { name: "Elimina…" }));
    const ask = screen.getByRole("dialog", { name: "Eliminare «Progetto libero»?" });
    expect(ask).toHaveTextContent("cestino");
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await user.click(within(ask).getByRole("button", { name: "Sposta nel cestino" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/projects/libero")).toBe(
        true,
      ),
    );
  });

  it("cancelling a deletion changes nothing, and Escape closes the window", async () => {
    const user = userEvent.setup();
    const { calls } = mount();
    await user.click(await screen.findByRole("button", { name: "Azioni su Progetto libero" }));
    await user.click(await screen.findByRole("menuitem", { name: "Elimina…" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("brings a project back from the trash", async () => {
    const user = userEvent.setup();
    const { calls } = mount();
    await user.click(await screen.findByRole("button", { name: /Cestino/ }));
    const trash = screen.getByRole("dialog", { name: "Cestino" });
    expect(trash).toHaveTextContent("Vecchio manuale");
    await user.click(within(trash).getByRole("button", { name: "Ripristina" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/restore"))).toBe(true));
  });

  it("sorts by a column and says so", async () => {
    const user = userEvent.setup();
    mount("/?c=", {
      folders,
      projects: [project({ id: "a", nome: "Beta" }), project({ id: "b", nome: "Alfa" })],
    });
    const head = await screen.findByRole("columnheader", { name: /Nome/ });
    await user.click(within(head).getByRole("button"));
    expect(head).toHaveAttribute("aria-sort", "ascending");
    const names = screen
      .getAllByTestId("project-row")
      .map((r) => within(r).getAllByRole("button")[0]?.textContent);
    expect(names).toEqual(["Alfa", "Beta"]);
    await user.click(within(head).getByRole("button"));
    expect(head).toHaveAttribute("aria-sort", "descending");
  });
});
