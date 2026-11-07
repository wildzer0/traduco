import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { installFakeApi } from "../../test/fake-api";
import { ImportPanel } from "./ImportPanel";

afterEach(() => vi.unstubAllGlobals());

const proposal = (id: string, over: object = {}) => ({
  id,
  kind: "modified",
  unit_kind: "paragraph",
  section: "capitoli/01/01-a.md",
  section_title: "Scopo",
  old: "vecchio",
  new: "nuovo del cliente",
  current_source: "testo attuale",
  proposed_source: "testo proposto",
  authors: [],
  tracked: false,
  stale: false,
  applicable: true,
  status: "pending",
  note: "",
  ...over,
});

const job = (proposals: object[]) => ({
  id: "j1",
  state: "done",
  progress: 100,
  message: "",
  filename: "r.docx",
  language: "sorgente",
  warnings: [],
  error: null,
  proposals,
});

function mount() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ImportPanel projectId="demo" />
    </QueryClientProvider>,
  );
}

describe("import panel", () => {
  it("shows the proposals of the section and accepts one with the edited text", async () => {
    usePrefs.setState({ locale: "it" });
    const calls = installFakeApi([
      (c) =>
        c.method === "POST" && c.url.includes("/import?filename=")
          ? { body: job([proposal("p1", { tracked: true, authors: ["Cliente"] }), proposal("p2")]) }
          : undefined,
      (c) =>
        c.url.endsWith("/proposals/p1")
          ? { body: proposal("p1", { status: "accepted" }) }
          : undefined,
    ]);
    mount();
    const file = new File(["x"], "r.docx");
    await userEvent.upload(screen.getByLabelText(/Scegli un file/), file);
    expect(await screen.findByRole("region", { name: "Scopo" })).toBeInTheDocument();
    expect(screen.getAllByTestId("proposal")).toHaveLength(2);
    expect(screen.getByText(/revisioni di Cliente/)).toBeInTheDocument();

    const first = screen.getAllByLabelText("Testo sorgente proposto")[0] as HTMLElement;
    await userEvent.clear(first);
    await userEvent.type(first, "versione mia");
    await userEvent.click(screen.getAllByRole("button", { name: "Accetta" })[0] as HTMLElement);
    await waitFor(() => expect(screen.getByText("Accettata")).toBeInTheDocument());
    const sent = calls.find((c) => c.url.endsWith("/proposals/p1"));
    expect(sent?.body).toEqual({ action: "accept", source: "versione mia" });
  });

  it("cannot accept what the program cannot apply", async () => {
    usePrefs.setState({ locale: "it" });
    installFakeApi([
      (c) =>
        c.method === "POST"
          ? { body: job([proposal("p1", { applicable: false, note: "table cell" })]) }
          : undefined,
    ]);
    mount();
    await userEvent.upload(screen.getByLabelText(/Scegli un file/), new File(["x"], "r.docx"));
    expect(await screen.findByRole("button", { name: "Accetta" })).toBeDisabled();
    expect(screen.getByText(/non si può applicare in automatico/)).toBeInTheDocument();
  });

  it("says so when nothing changed", async () => {
    usePrefs.setState({ locale: "it" });
    installFakeApi([(c) => (c.method === "POST" ? { body: job([]) } : undefined)]);
    mount();
    await userEvent.upload(screen.getByLabelText(/Scegli un file/), new File(["x"], "r.docx"));
    expect(await screen.findByText(/Nessuna modifica/)).toBeInTheDocument();
  });
});
