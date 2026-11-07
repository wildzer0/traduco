import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { useTranslationState } from "../../lib/translation-store";
import type { Suggestion } from "../../lib/types";
import { installFakeApi } from "../../test/fake-api";
import { CheckPanel } from "./CheckPanel";

const PATH = "capitoli/01-a/01-s.md";
const item = (over: Partial<Suggestion>): Suggestion => ({
  id: "a1",
  key: "p:0",
  source_hash: "h",
  category: "grammar",
  message: "Errore di ortografia",
  suggestion: "Il sistema è pronto",
  origin: "model",
  status: "open",
  ...over,
});

function mount(items: Suggestion[]) {
  usePrefs.setState({ locale: "it" });
  useTranslationState.setState({ online: true, model: "m", pending: 0 });
  const calls = installFakeApi([
    (c) =>
      c.url.startsWith("/api/projects/demo/translation")
        ? {
            body: {
              path: PATH,
              lang: "en",
              tone: null,
              project_tone: "formale",
              note: "",
              markdown: "x\n",
              pending: 0,
              segments: [
                {
                  key: "p:0",
                  kind: "paragraph",
                  line: 0,
                  end: 1,
                  source: "Il sistema e' pronto",
                  target: "",
                  status: "translated",
                  locked: false,
                  reason: "",
                  pending_target: null,
                },
              ],
            },
          }
        : undefined,
    (c) =>
      c.method === "GET" && c.url.startsWith("/api/projects/demo/check")
        ? { body: { items: [] } }
        : undefined,
    (c) =>
      c.method === "POST" && c.url === "/api/projects/demo/check" ? { body: { items } } : undefined,
    (c) =>
      c.url.endsWith("/assist/apply") || c.url.endsWith("/check/dismiss")
        ? { body: {} }
        : undefined,
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CheckPanel projectId="demo" path={PATH} />
    </QueryClientProvider>,
  );
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

describe("section check panel", () => {
  it("runs the check with the requirement rules on request and lists the suggestions", async () => {
    const user = userEvent.setup();
    const calls = mount([
      item({}),
      item({
        id: "r1",
        origin: "rule",
        category: "vague",
        message: "«adeguato» non è verificabile",
        suggestion: "",
      }),
    ]);
    await user.click(screen.getByLabelText(/Regole per i requisiti/));
    await user.click(screen.getByRole("button", { name: "Controlla" }));
    expect(await screen.findAllByTestId("suggestion")).toHaveLength(2);
    expect(calls.find((c) => c.method === "POST" && c.url.endsWith("/check"))?.body).toEqual({
      path: PATH,
      requirements: true,
    });
    expect(screen.getByText("«adeguato» non è verificabile")).toBeInTheDocument();
    // only suggestions with a fix offer "Applica"
    expect(screen.getAllByRole("button", { name: "Applica" })).toHaveLength(1);
  });

  it("applies a suggestion only when asked and dismisses another", async () => {
    const user = userEvent.setup();
    const calls = mount([item({})]);
    await user.click(screen.getByRole("button", { name: "Controlla" }));
    await screen.findByTestId("suggestion");
    expect(calls.some((c) => c.url.endsWith("/assist/apply"))).toBe(false);
    await user.click(screen.getByRole("button", { name: "Applica" }));
    await waitFor(() =>
      expect(calls.find((c) => c.url.endsWith("/assist/apply"))?.body).toMatchObject({
        path: PATH,
        key: "p:0",
        text: "Il sistema è pronto",
        suggestion_id: "a1",
      }),
    );
  });

  it("does not run while the model is unreachable", async () => {
    useTranslationState.setState({ online: false });
    mount([]);
    useTranslationState.setState({ online: false });
    expect(await screen.findByText(/l'assistente è disattivato/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Controlla" })).toBeDisabled();
  });
});
