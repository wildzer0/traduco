import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../lib/prefs";
import { chapter, demoTree, health, installFakeApi, project } from "../test/fake-api";
import { createAppRouter, memoryHistory } from "./router";

function renderApp(path: string) {
  const router = createAppRouter(memoryHistory(path));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router as never} />
    </QueryClientProvider>,
  );
  return { router, ...utils };
}

const workspaceApi = (tree = demoTree()) => [
  health,
  (c: { url: string; method: string }) =>
    c.url === "/api/projects" && c.method === "GET" ? { body: [project()] } : undefined,
  (c: { url: string; method: string }) =>
    c.url === "/api/workspace" ? { body: { folders: [], projects: [project()] } } : undefined,
  (c: { url: string; method: string }) => (c.url === "/api/trash" ? { body: [] } : undefined),
  (c: { url: string; method: string }) =>
    c.url === "/api/projects/demo/tree" ? { body: { nodes: tree } } : undefined,
];

beforeEach(() =>
  usePrefs.setState({ locale: "it", theme: "system", sidebarOpen: true, settingsOpen: false }),
);
afterEach(() => vi.unstubAllGlobals());

describe("welcome page", () => {
  it("lists projects and opens one", async () => {
    installFakeApi(workspaceApi());
    const user = userEvent.setup();
    const { router } = renderApp("/");
    await user.click(await screen.findByRole("button", { name: "Demo" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/p/demo"));
    expect(await screen.findByRole("navigation", { name: "Capitoli" })).toBeInTheDocument();
  });

  it("creates a project from the form and opens it", async () => {
    const calls = installFakeApi([
      ...workspaceApi(),
      (c) =>
        c.url === "/api/projects" && c.method === "POST"
          ? { status: 201, body: project("nuovo", "Nuovo") }
          : undefined,
    ]);
    const user = userEvent.setup();
    const { router } = renderApp("/");
    await user.click(await screen.findByRole("button", { name: "Crea progetto" }));
    const submit = screen.getByRole("button", { name: "Crea" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Nome del progetto"), "Nuovo");
    await user.click(submit);
    await waitFor(() => expect(router.state.location.pathname).toBe("/p/nuovo"));
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ nome: "Nuovo", lingua_sorgente: "it", lingua_ufficiale: "en" });
  });

  it("does not allow identical source and official languages", async () => {
    installFakeApi(workspaceApi());
    const user = userEvent.setup();
    renderApp("/");
    await user.click(await screen.findByRole("button", { name: "Crea progetto" }));
    await user.type(screen.getByLabelText("Nome del progetto"), "X");
    await user.selectOptions(screen.getByLabelText("Lingua ufficiale del progetto"), "it");
    expect(screen.getByRole("button", { name: "Crea" })).toBeDisabled();
  });

  it("opens the bundled example", async () => {
    const calls = installFakeApi([
      ...workspaceApi(),
      (c) =>
        c.url === "/api/projects" && c.method === "POST"
          ? { status: 201, body: project("progetto-esempio", "Esempio") }
          : undefined,
    ]);
    const user = userEvent.setup();
    const { router } = renderApp("/");
    await user.click(await screen.findByRole("button", { name: "Apri esempio" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/p/progetto-esempio"));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ esempio: true });
  });
});

describe("workspace", () => {
  it("renders the three columns, the tree and the status bar", async () => {
    installFakeApi(workspaceApi());
    renderApp("/p/demo");
    expect(await screen.findByRole("button", { name: "Introduzione" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "Editor" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Anteprima tradotta" })).toBeInTheDocument();
    expect(await screen.findByText("Backend attivo · v0.1.0")).toBeInTheDocument();
  });

  it("selects a section and shows it in the breadcrumb", async () => {
    installFakeApi(workspaceApi());
    const user = userEvent.setup();
    const { router } = renderApp("/p/demo");
    await user.click(await screen.findByRole("button", { name: "Ambito" }));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ s: "capitoli/01-intro/02-ambito.md" }),
    );
    const crumbs = screen.getByRole("navigation", { name: "breadcrumb" });
    expect(within(crumbs).getByText(/Ambito/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ambito" })).toHaveAttribute("aria-current", "true");
  });

  it("collapses and expands a chapter", async () => {
    installFakeApi(workspaceApi());
    const user = userEvent.setup();
    renderApp("/p/demo");
    await screen.findByRole("button", { name: "Scopo" });
    await user.click(screen.getAllByRole("button", { name: "Comprimi" })[0] as HTMLElement);
    expect(screen.queryByRole("button", { name: "Scopo" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Espandi" }));
    expect(screen.getByRole("button", { name: "Scopo" })).toBeInTheDocument();
  });

  it("'+ Sezione' creates a section in the last chapter and starts renaming it", async () => {
    const calls = installFakeApi([
      ...workspaceApi(),
      (c) =>
        c.url === "/api/projects/demo/nodes" && c.method === "POST"
          ? { status: 201, body: { path: "capitoli/02-inst/02-nuova-sezione.md", renamed: {} } }
          : undefined,
    ]);
    const user = userEvent.setup();
    renderApp("/p/demo");
    await user.click(await screen.findByRole("button", { name: "+ Sezione" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      kind: "section",
      title: "Nuova sezione",
      parent: "capitoli/02-inst",
    });
  });

  it("'+ Section' right after '+ Chapter' goes into the new chapter", async () => {
    let tree = demoTree();
    const calls = installFakeApi([
      health,
      (c) => (c.url === "/api/projects" ? { body: [project()] } : undefined),
      (c) => (c.url === "/api/projects/demo/tree" ? { body: { nodes: tree } } : undefined),
      (c) => {
        if (c.url !== "/api/projects/demo/nodes" || c.method !== "POST") return undefined;
        const body = c.body as { kind: string; title: string };
        if (body.kind === "chapter") {
          tree = [...tree, chapter("capitoli/03-nuovo", "Nuovo capitolo")];
          return { status: 201, body: { path: "capitoli/03-nuovo", renamed: {} } };
        }
        return { status: 201, body: { path: "capitoli/03-nuovo/01-x.md", renamed: {} } };
      },
    ]);
    const user = userEvent.setup();
    renderApp("/p/demo?s=capitoli%2F01-intro%2F01-scopo.md");
    await user.click(await screen.findByRole("button", { name: "+ Capitolo" }));
    await user.keyboard("{Enter}");
    await user.click(await screen.findByRole("button", { name: "+ Sezione" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(2));
    expect(calls.filter((c) => c.method === "POST")[1]?.body).toMatchObject({
      kind: "section",
      parent: "capitoli/03-nuovo",
    });
  });

  it("renames a section on double click and follows the new path", async () => {
    const calls = installFakeApi([
      ...workspaceApi(),
      (c) =>
        c.method === "PATCH"
          ? {
              body: {
                path: "capitoli/01-intro/01-obiettivo.md",
                renamed: { "capitoli/01-intro/01-scopo.md": "capitoli/01-intro/01-obiettivo.md" },
              },
            }
          : undefined,
    ]);
    const user = userEvent.setup();
    const { router } = renderApp("/p/demo?s=capitoli%2F01-intro%2F01-scopo.md");
    await user.dblClick(await screen.findByRole("button", { name: "Scopo" }));
    const input = screen.getByRole("textbox", { name: "Rinomina" });
    await user.clear(input);
    await user.type(input, "Obiettivo{Enter}");
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ s: "capitoli/01-intro/01-obiettivo.md" }),
    );
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      path: "capitoli/01-intro/01-scopo.md",
      title: "Obiettivo",
    });
  });

  it("Escape cancels a rename without calling the API", async () => {
    const calls = installFakeApi(workspaceApi());
    const user = userEvent.setup();
    renderApp("/p/demo");
    await user.dblClick(await screen.findByRole("button", { name: "Scopo" }));
    await user.type(screen.getByRole("textbox", { name: "Rinomina" }), "xx{Escape}");
    expect(screen.getByRole("button", { name: "Scopo" })).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
  });

  it("deleting the open section clears the selection", async () => {
    const calls = installFakeApi([
      ...workspaceApi(),
      (c) => (c.method === "DELETE" ? { body: { trash: ".traduco/cestino/x" } } : undefined),
    ]);
    const user = userEvent.setup();
    const { router } = renderApp("/p/demo?s=capitoli%2F01-intro%2F01-scopo.md");
    await user.pointer({
      target: await screen.findByRole("button", { name: "Scopo" }),
      keys: "[MouseRight]",
    });
    await user.click(await screen.findByRole("menuitem", { name: "Elimina" }));
    await waitFor(() => expect(router.state.location.search).toEqual({}));
    expect(calls.find((c) => c.method === "DELETE")?.url).toContain(
      "path=capitoli%2F01-intro%2F01-scopo.md",
    );
  });

  it("shows API errors in the status bar", async () => {
    installFakeApi([
      ...workspaceApi(),
      (c) =>
        c.method === "POST"
          ? {
              status: 422,
              body: { error: { code: "depth_exceeded", message: "troppo profondo", details: {} } },
            }
          : undefined,
    ]);
    const user = userEvent.setup();
    renderApp("/p/demo");
    await user.click(await screen.findByRole("button", { name: "+ Capitolo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("troppo profondo");
  });

  it("toggles the sidebar with the button and with Ctrl+B", async () => {
    installFakeApi(workspaceApi());
    const user = userEvent.setup();
    renderApp("/p/demo");
    await screen.findByRole("navigation", { name: "Capitoli" });
    await user.click(screen.getByRole("button", { name: /barra laterale/i }));
    expect(screen.queryByRole("navigation", { name: "Capitoli" })).not.toBeInTheDocument();
    await user.keyboard("{Control>}b{/Control}");
    expect(screen.getByRole("navigation", { name: "Capitoli" })).toBeInTheDocument();
  });

  it("switches language and theme from the settings drawer, closes with Esc", async () => {
    installFakeApi(workspaceApi());
    const user = userEvent.setup();
    renderApp("/p/demo");
    await user.click(await screen.findByRole("button", { name: "Impostazioni" }));
    await user.selectOptions(screen.getByLabelText("Lingua dell'interfaccia"), "en");
    await waitFor(() => expect(screen.getByRole("navigation", { name: "Chapters" })).toBeVisible());
    await user.selectOptions(screen.getByLabelText("Theme"), "dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an error state when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    renderApp("/");
    expect(await screen.findByText("Backend non raggiungibile")).toBeInTheDocument();
  });
});

describe("project from a skeleton", () => {
  it("offers the bundled skeletons and sends the chosen one", async () => {
    const calls = installFakeApi([
      ...workspaceApi(),
      (c) =>
        c.url === "/api/skeletons" ? { body: [{ id: "ecss", nome: "Stile ECSS" }] } : undefined,
      (c) =>
        c.url === "/api/projects" && c.method === "POST"
          ? { status: 201, body: project("spec", "Spec") }
          : undefined,
    ]);
    const user = userEvent.setup();
    renderApp("/");
    await user.click(await screen.findByRole("button", { name: "Crea progetto" }));
    await user.type(screen.getByLabelText("Nome del progetto"), "Spec");
    await user.selectOptions(await screen.findByLabelText("Struttura iniziale"), "ecss");
    await user.click(screen.getByRole("button", { name: "Crea" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({ scheletro: "ecss" });
  });

  it("shows the line of an invalid skeleton file", async () => {
    installFakeApi([
      ...workspaceApi(),
      (c) => (c.url === "/api/skeletons" ? { body: [] } : undefined),
      (c) =>
        c.url === "/api/projects" && c.method === "POST"
          ? {
              status: 422,
              body: {
                error: {
                  code: "invalid_skeleton",
                  message: "riga 3: id duplicato",
                  details: { line: 3 },
                },
              },
            }
          : undefined,
    ]);
    const user = userEvent.setup();
    renderApp("/");
    await user.click(await screen.findByRole("button", { name: "Crea progetto" }));
    await user.type(screen.getByLabelText("Nome del progetto"), "Spec");
    await user.selectOptions(screen.getByLabelText("Struttura iniziale"), "@file");
    const file = new File(["nome: X"], "s.yaml", { type: "text/yaml" });
    await user.upload(screen.getByLabelText("File scheletro (YAML)"), file);
    await user.click(screen.getByRole("button", { name: "Crea" }));
    expect(await screen.findByText(/riga 3: id duplicato/)).toBeInTheDocument();
  });
});
