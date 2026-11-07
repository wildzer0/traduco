import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { useView } from "../../lib/view-store";
import { installFakeApi } from "../../test/fake-api";
import { CommandPalette } from "./CommandPalette";
import { ShortcutsHelp } from "./ShortcutsHelp";

const navigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
  useParams: () => ({ projectId: "demo" }),
  useSearch: () => ({ s: "capitoli/01-a/01-scopo.md" }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  navigate.mockClear();
  useView.setState({ paletteOpen: false, helpOpen: false, exportOpen: false });
});

const tree = [
  {
    kind: "chapter",
    path: "capitoli/01-a",
    name: "01-a",
    title: "Introduzione",
    children: [
      {
        kind: "section",
        path: "capitoli/01-a/01-scopo.md",
        name: "01-scopo.md",
        title: "Scopo",
        children: [],
      },
      {
        kind: "section",
        path: "capitoli/01-a/02-ambito.md",
        name: "02-ambito.md",
        title: "Ambito di applicazione",
        children: [],
      },
    ],
  },
];

function mount(mode: "all" | "text" = "all") {
  usePrefs.setState({ locale: "it" });
  useView.setState({ paletteOpen: true, paletteMode: mode });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <CommandPalette />
    </QueryClientProvider>,
  );
}

describe("command palette", () => {
  it("opens a section found by a few letters", async () => {
    installFakeApi([(c) => (c.url.endsWith("/tree") ? { body: { nodes: tree } } : undefined)]);
    mount();
    const box = screen.getByRole("combobox");
    await userEvent.type(box, "ambit");
    await userEvent.keyboard("{Enter}");
    expect(navigate).toHaveBeenCalledWith({
      to: "/p/$projectId",
      params: { projectId: "demo" },
      search: { s: "capitoli/01-a/02-ambito.md" },
    });
    expect(useView.getState().paletteOpen).toBe(false);
  });

  it("runs an action", async () => {
    installFakeApi([(c) => (c.url.endsWith("/tree") ? { body: { nodes: tree } } : undefined)]);
    mount();
    await userEvent.type(screen.getByRole("combobox"), "esporta");
    await userEvent.keyboard("{Enter}");
    expect(useView.getState().exportOpen).toBe(true);
  });

  it("searches the text of the project and opens the section of a hit", async () => {
    installFakeApi([
      (c) => (c.url.endsWith("/tree") ? { body: { nodes: tree } } : undefined),
      (c) =>
        c.url.includes("/search?")
          ? {
              body: {
                hits: [
                  {
                    path: "capitoli/01-a/02-ambito.md",
                    title: "Ambito di applicazione",
                    key: "p:0",
                    field: "source",
                    before: "La ",
                    match: "pompa",
                    after: " parte.",
                  },
                ],
              },
            }
          : undefined,
    ]);
    mount("text");
    await userEvent.type(screen.getByRole("combobox"), "pompa");
    const hit = await screen.findByRole("option", { name: /La pompa parte\./ });
    expect(hit).toHaveTextContent("Ambito di applicazione · sorgente");
    await userEvent.click(hit);
    await waitFor(() => expect(navigate).toHaveBeenCalled());
  });

  it("says when nothing matches", async () => {
    installFakeApi([(c) => (c.url.endsWith("/tree") ? { body: { nodes: tree } } : undefined)]);
    mount();
    await userEvent.type(screen.getByRole("combobox"), "zzzzqq");
    expect(await screen.findByText("Nessun risultato")).toBeInTheDocument();
  });
});

describe("shortcuts help", () => {
  it("lists the shortcuts and closes with Escape", async () => {
    usePrefs.setState({ locale: "it" });
    useView.setState({ helpOpen: true });
    render(<ShortcutsHelp />);
    expect(screen.getByRole("dialog", { name: "Scorciatoie da tastiera" })).toBeInTheDocument();
    expect(screen.getByText("Palette comandi")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(useView.getState().helpOpen).toBe(false);
  });
});
