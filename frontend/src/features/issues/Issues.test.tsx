import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { installFakeApi } from "../../test/fake-api";
import { CommentsPanel } from "./CommentsPanel";
import { ComparePanel } from "./ComparePanel";
import { IssuesPanel } from "./IssuesPanel";
import { RequirementsPanel } from "./RequirementsPanel";

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => vi.fn() }));

afterEach(() => vi.unstubAllGlobals());

const wrap = (node: React.ReactNode) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {node}
    </QueryClientProvider>,
  );

const issue = (rev: string) => ({
  rev,
  data: "2026-11-07",
  descrizione: `Emissione ${rev}`,
  created_at: `2026-11-07T10:0${rev}:00`,
  sections: 3,
  changes: 0,
});

describe("issues panel", () => {
  it("freezes an issue and offers the comparisons", async () => {
    usePrefs.setState({ locale: "it" });
    const calls = installFakeApi([
      (c) =>
        c.method === "POST" && c.url.endsWith("/issues") ? { status: 201, body: {} } : undefined,
      (c) => (c.url.endsWith("/issues") ? { body: [issue("1"), issue("2")] } : undefined),
      (c) =>
        c.url.includes("/compare")
          ? { body: { a: "1", b: "2", lang: "sorgente", sections: [], unchanged: 3 } }
          : undefined,
    ]);
    wrap(<IssuesPanel projectId="demo" />);
    expect(await screen.findByText("Emissione 2")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Numero"), "3");
    await userEvent.type(screen.getByLabelText("Descrizione"), "Terza");
    await userEvent.click(screen.getByRole("button", { name: "Congela" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({
      rev: "3",
      descrizione: "Terza",
    });
    await userEvent.click(
      screen.getAllByRole("button", { name: "Confronta con la precedente" })[0] as HTMLElement,
    );
    expect(await screen.findByRole("dialog", { name: "Confronto" })).toBeInTheDocument();
  });
});

describe("compare panel", () => {
  it("shows the word differences and counts them", async () => {
    usePrefs.setState({ locale: "it" });
    installFakeApi([
      (c) => (c.url.endsWith("/issues") ? { body: [issue("1")] } : undefined),
      (c) =>
        c.url.includes("/compare")
          ? {
              body: {
                a: "1",
                b: "bozza",
                lang: "sorgente",
                unchanged: 0,
                sections: [
                  {
                    path: "capitoli/a/01.md",
                    title: "Scopo",
                    status: "modified",
                    was: null,
                    words_added: 1,
                    words_removed: 1,
                    ops: [
                      { op: "equal", text: "La pompa è " },
                      { op: "del", text: "rossa" },
                      { op: "ins", text: "blu" },
                    ],
                  },
                ],
              },
            }
          : undefined,
    ]);
    wrap(<ComparePanel projectId="demo" from="1" to="bozza" onClose={() => undefined} />);
    expect(await screen.findByText("rossa")).toHaveClass("line-through");
    expect(screen.getByText("blu")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ripristina questa sezione" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Cambio 1 di 2"));
    await userEvent.click(screen.getByRole("button", { name: "Cambio successivo" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Cambio 2 di 2"));
  });
});

describe("comments panel", () => {
  it("lists threads and posts a new comment on a segment", async () => {
    usePrefs.setState({ locale: "it" });
    const calls = installFakeApi([
      (c) =>
        c.method === "POST" && c.url.endsWith("/comments") ? { status: 201, body: {} } : undefined,
      (c) =>
        c.url.includes("/comments?")
          ? {
              body: {
                counts: { open: 1, resolved: 0 },
                threads: [
                  {
                    id: "t1",
                    status: "open",
                    key: "p:1",
                    lost: false,
                    source: "Il sistema parte in dieci secondi.",
                    messages: [{ author: "Anna", at: "2026-11-07T10:00:00", text: "Troppo?" }],
                  },
                ],
              },
            }
          : undefined,
      (c) =>
        c.url.includes("/translation")
          ? {
              body: {
                segments: [
                  { key: "p:1", kind: "paragraph", source: "Il sistema parte in dieci secondi." },
                ],
              },
            }
          : undefined,
    ]);
    wrap(<CommentsPanel projectId="demo" path="capitoli/a/01.md" />);
    expect(await screen.findByText("Troppo?")).toBeInTheDocument();
    await screen.findByRole("option", { name: /Il sistema parte/ });
    await userEvent.selectOptions(screen.getByLabelText("Commenta"), "p:1");
    await userEvent.type(screen.getByLabelText("Il tuo nome"), "Bruno");
    await userEvent.type(screen.getByLabelText("Commento"), "Va bene così");
    await userEvent.click(screen.getAllByRole("button", { name: "Invia" }).at(-1) as HTMLElement);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      path: "capitoli/a/01.md",
      key: "p:1",
      author: "Bruno",
      text: "Va bene così",
    });
  });
});

describe("requirements panel", () => {
  it("lists what to check before the full list", async () => {
    usePrefs.setState({ locale: "it" });
    installFakeApi([
      (c) =>
        c.url.endsWith("/requirements")
          ? {
              body: {
                requirements: [
                  {
                    id: "FOO-REQ-00001",
                    path: "capitoli/a/01.md",
                    key: "p:0",
                    text: "Il sistema deve partire.",
                    referenced_by: [],
                  },
                ],
                problems: [
                  {
                    kind: "unreferenced",
                    id: "FOO-REQ-00001",
                    path: "capitoli/a/01.md",
                    key: "p:0",
                  },
                ],
              },
            }
          : undefined,
    ]);
    wrap(<RequirementsPanel projectId="demo" />);
    expect(await screen.findByLabelText("Da controllare")).toHaveTextContent("Mai citato");
    expect(screen.getByText("0 riferimenti")).toBeInTheDocument();
  });
});
