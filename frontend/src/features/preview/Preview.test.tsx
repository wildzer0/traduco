import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import { useTranslationState } from "../../lib/translation-store";
import type { TranslationView } from "../../lib/types";
import { installFakeApi } from "../../test/fake-api";
import { Preview } from "./Preview";

const VIEW: TranslationView = {
  path: "capitoli/01-a/01-s.md",
  lang: "en",
  markdown: "# Title\n\nSecond paragraph in Italian.\n",
  pending: 1,
  segments: [
    {
      key: "h:0",
      kind: "heading",
      line: 0,
      end: 1,
      source: "Titolo",
      target: "Title",
      status: "translated",
      locked: false,
      reason: "",
      pending_target: null,
    },
    {
      key: "p:0",
      kind: "paragraph",
      line: 2,
      end: 3,
      source: "Second paragraph in Italian.",
      target: "",
      status: "queued",
      locked: false,
      reason: "",
      pending_target: null,
    },
  ],
};

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Preview projectId="demo" />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  usePrefs.setState({ locale: "it" });
  usePreview.setState({
    path: VIEW.path,
    text: "# Titolo\n\nSecondo paragrafo.\n",
    mode: "translated",
    topBlock: 0,
  });
  useTranslationState.setState({ online: true, model: "m", pending: 0 });
  installFakeApi([
    (c) => (c.url.startsWith("/api/projects/demo/translation") ? { body: VIEW } : undefined),
  ]);
});
afterEach(() => vi.unstubAllGlobals());

describe("translated preview", () => {
  it("shows the translation and marks the segment still being translated", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: "Title" })).toBeInTheDocument();
    const pending = screen.getByText("Second paragraph in Italian.");
    await waitFor(() => expect(pending).toHaveAttribute("data-status", "queued"));
    expect(screen.getByText(/Anteprima · inglese/i)).toBeInTheDocument();
  });

  it("switches to the rendered source and back", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByRole("heading", { name: "Title" });
    await user.click(screen.getByRole("button", { name: /Mostra il sorgente/ }));
    expect(await screen.findByRole("heading", { name: "Titolo" })).toBeInTheDocument();
    expect(screen.getByText("Anteprima · sorgente")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Mostra la traduzione/ }));
    expect(await screen.findByRole("heading", { name: "Title" })).toBeInTheDocument();
  });

  it("tells the user when the model is unreachable, without blocking anything", async () => {
    useTranslationState.setState({ online: false });
    mount();
    expect(await screen.findByText(/Modello non raggiungibile/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Title" })).toBeInTheDocument();
  });
});
