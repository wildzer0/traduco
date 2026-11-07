import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import { useTranslationState } from "../../lib/translation-store";
import type { SegmentRow, TranslationView } from "../../lib/types";
import { type Call, installFakeApi } from "../../test/fake-api";
import { Preview } from "./Preview";

const row = (key: string, patch: Partial<SegmentRow> = {}): SegmentRow => ({
  key,
  kind: "paragraph",
  line: 0,
  end: 1,
  source: "Sorgente",
  target: "Target",
  status: "translated",
  locked: false,
  reason: "",
  pending_target: null,
  ...patch,
});

function view(segments: SegmentRow[], markdown: string): TranslationView {
  return {
    path: "capitoli/01-a/01-s.md",
    lang: "en",
    tone: null,
    project_tone: "formale",
    note: "",
    markdown,
    segments,
    pending: 0,
  };
}

function setup(
  v: TranslationView,
  extra: ((c: Call) => { status?: number; body: unknown } | undefined)[] = [],
) {
  usePrefs.setState({ locale: "it" });
  usePreview.setState({ path: v.path, text: "x\n", mode: "translated", topBlock: 0 });
  useTranslationState.setState({ online: true, model: "m", pending: 0 });
  const calls = installFakeApi([
    ...extra,
    (c) => (c.url.startsWith("/api/projects/demo/translation") ? { body: v } : undefined),
    (c) => (c.method === "PUT" && c.url.includes("/segments/") ? { body: row("p:0") } : undefined),
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Preview projectId="demo" />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("segment interactions", () => {
  it("shows the actions on hover and approves with one click", async () => {
    const user = userEvent.setup();
    const calls = setup(view([row("p:0")], "Target\n"));
    await user.hover(await screen.findByText("Target"));
    await user.click(await screen.findByRole("button", { name: "Approva" }));
    console.log(JSON.stringify(calls.map((c) => [c.method, c.url])));
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.url).toContain("/segments/p%3A0?path=");
    expect(put?.body).toEqual({ action: "approve" });
  });

  it("locks and unlocks", async () => {
    const user = userEvent.setup();
    const calls = setup(view([row("p:0", { locked: true })], "Target\n"));
    await user.hover(await screen.findByText("Target"));
    await user.click(await screen.findByRole("button", { name: "Sblocca" }));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ locked: false });
  });

  it("saves a manual edit with Enter and offers to update the source", async () => {
    const user = userEvent.setup();
    const calls = setup(view([row("p:0")], "Target\n"));
    await user.hover(await screen.findByText("Target"));
    await user.click(await screen.findByRole("button", { name: "Modifica la traduzione" }));
    const box = await screen.findByLabelText("Testo della traduzione");
    await user.clear(box);
    await user.type(box, "Mio testo{Enter}");
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ target: "Mio testo" }),
    );
    expect(await screen.findByText(/Il sorgente non corrisponde più/)).toBeInTheDocument();
  });

  it("shows the proposal of a locked segment and accepts or ignores it", async () => {
    const user = userEvent.setup();
    const calls = setup(
      view(
        [row("p:0", { locked: true, status: "needs_review", pending_target: "Nuova versione" })],
        "Mia\n",
      ),
    );
    const proposal = await screen.findByTestId("proposal");
    expect(proposal).toHaveTextContent("Nuova versione");
    await user.click(screen.getByRole("button", { name: "Accetta" }));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ action: "accept" });
  });

  it("asks the model for a rewrite and uses the proposal only on confirmation", async () => {
    const user = userEvent.setup();
    const calls = setup(view([row("p:0")], "Target\n"), [
      (c) =>
        c.url.includes("/instruct") ? { body: { proposals: ["Più formale così"] } } : undefined,
    ]);
    await user.hover(await screen.findByText("Target"));
    await user.click(await screen.findByRole("button", { name: "Istruzione" }));
    await user.click(await screen.findByRole("button", { name: "Più formale" }));
    expect(await screen.findByText("Più formale così")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PUT")).toBe(false); // nothing saved yet
    await user.click(screen.getByRole("button", { name: "Usa questa" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ target: "Più formale così" }),
    );
  });
});

describe("writing companion", () => {
  const assistApi = (changed = true) => [
    (c: Call) =>
      c.url === "/api/projects/demo/assist"
        ? {
            body: {
              original: "Il sistema e' pronto",
              proposal: changed ? "Il sistema è pronto" : "Il sistema e' pronto",
              changed,
            },
          }
        : undefined,
    (c: Call) =>
      c.url === "/api/projects/demo/assist/apply" ? { body: { path: "x", key: "p:0" } } : undefined,
  ];

  it("proposes a rewrite as a difference and changes nothing until Apply", async () => {
    const user = userEvent.setup();
    const calls = setup(
      view([row("p:0", { source: "Il sistema e' pronto" })], "Target\n"),
      assistApi(),
    );
    await user.hover(await screen.findByText("Target"));
    await user.click(await screen.findByRole("button", { name: "Migliora il testo" }));
    await user.click(await screen.findByRole("button", { name: "Correggi" }));
    const diff = await screen.findByTestId("diff");
    expect(diff.querySelector("del")?.textContent).toBe("e'");
    expect(diff.querySelector("ins")?.textContent).toBe("è");
    expect(calls.find((c) => c.url.endsWith("/assist"))?.body).toMatchObject({
      key: "p:0",
      action: "correct",
    });
    expect(calls.some((c) => c.url.endsWith("/assist/apply"))).toBe(false);
    await user.click(screen.getByRole("button", { name: "Applica" }));
    await waitFor(() =>
      expect(calls.find((c) => c.url.endsWith("/assist/apply"))?.body).toMatchObject({
        key: "p:0",
        text: "Il sistema è pronto",
      }),
    );
  });

  it("says so when there is nothing to change", async () => {
    const user = userEvent.setup();
    setup(view([row("p:0", { source: "Il sistema e' pronto" })], "Target\n"), assistApi(false));
    await user.hover(await screen.findByText("Target"));
    await user.click(await screen.findByRole("button", { name: "Migliora il testo" }));
    await user.click(await screen.findByRole("button", { name: "Più conciso" }));
    expect(await screen.findByText("Il modello non propone modifiche.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Applica" })).not.toBeInTheDocument();
  });

  it("is disabled with a message while the model is unreachable", async () => {
    const user = userEvent.setup();
    setup(view([row("p:0")], "Target\n"), assistApi());
    useTranslationState.setState({ online: false });
    await user.hover(await screen.findByText("Target"));
    await user.click(await screen.findByRole("button", { name: "Migliora il testo" }));
    expect(await screen.findByText(/l'assistente è disattivato/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correggi" })).toBeDisabled();
  });
});
