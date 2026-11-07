import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import type { ReviewRow } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { installFakeApi } from "../../test/fake-api";
import { ReviewTable } from "./ReviewTable";

const r = (
  key: string,
  status: ReviewRow["status"],
  extra: Partial<ReviewRow> = {},
): ReviewRow => ({
  key,
  kind: "paragraph",
  line: 0,
  end: 1,
  source: `src ${key}`,
  target: `tgt ${key}`,
  status,
  locked: false,
  reason: "",
  pending_target: null,
  path: "capitoli/01-a/01-s.md",
  section: "Scopo",
  ...extra,
});

const DATA = {
  segments: [
    r("p:0", "translated"),
    r("p:1", "needs_review", { reason: "glossary: use proposal" }),
    r("p:2", "approved", { locked: true }),
  ],
  counts: { translated: 1, needs_review: 1, approved: 1 },
};

function mount(onOpen = vi.fn()) {
  usePrefs.setState({ locale: "it" });
  useView.setState({ reviewFilter: "all" });
  const calls = installFakeApi([
    (c) => (c.url === "/api/projects/demo/review" ? { body: DATA } : undefined),
    (c) => (c.method === "PUT" ? { body: r("p:0", "approved") } : undefined),
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ReviewTable projectId="demo" onOpen={onOpen} />
    </QueryClientProvider>,
  );
  return { calls, onOpen };
}
afterEach(() => vi.unstubAllGlobals());

describe("review table", () => {
  it("lists every segment and filters by status", async () => {
    const user = userEvent.setup();
    mount();
    expect(await screen.findAllByTestId("review-row")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: /Da rivedere · 1/ }));
    const rows = screen.getAllByTestId("review-row");
    expect(rows).toHaveLength(1);
    expect(within(rows[0] as HTMLElement).getByText("glossary: use proposal")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Bloccati · 1/ }));
    expect(screen.getAllByTestId("review-row")).toHaveLength(1);
  });

  it("approves from the table and opens a segment in the editor", async () => {
    const user = userEvent.setup();
    const { calls, onOpen } = mount();
    const rows = await screen.findAllByTestId("review-row");
    await user.click(within(rows[0] as HTMLElement).getByRole("button", { name: "Approva" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ action: "approve" }),
    );
    await user.click(within(rows[1] as HTMLElement).getByRole("button", { name: "Apri" }));
    expect(onOpen).toHaveBeenCalledWith("capitoli/01-a/01-s.md", "p:1");
  });
});
