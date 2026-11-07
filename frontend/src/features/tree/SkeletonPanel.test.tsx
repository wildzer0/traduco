import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import type { SkeletonReport } from "../../lib/types";
import { installFakeApi } from "../../test/fake-api";
import { SkeletonPanel } from "./SkeletonPanel";

const item = (
  id: string,
  status: SkeletonReport["items"][number]["status"],
  path: string | null,
) => ({
  id,
  title: id.toUpperCase(),
  mandatory: true,
  status,
  path,
  guide: "",
});

function mount(report: SkeletonReport | null, onSelect = vi.fn()) {
  const calls = installFakeApi([
    (c) =>
      c.url === "/api/projects/demo/skeleton/check"
        ? report
          ? { body: report }
          : { status: 404, body: { error: { code: "not_found", message: "none", details: {} } } }
        : undefined,
    (c) =>
      c.url === "/api/projects/demo/skeleton/create-missing"
        ? { body: { created: ["x"] } }
        : undefined,
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SkeletonPanel projectId="demo" onSelect={onSelect} />
    </QueryClientProvider>,
  );
  return { calls, onSelect };
}

beforeEach(() => usePrefs.setState({ locale: "it" }));
afterEach(() => vi.unstubAllGlobals());

describe("skeleton panel", () => {
  it("is absent for a project without skeleton", async () => {
    const { calls } = mount(null);
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(screen.queryByText("Scheletro")).not.toBeInTheDocument();
  });

  it("says when the project conforms", async () => {
    mount({ conform: true, items: [item("a", "ok", "capitoli/a.md")], extra: [] });
    expect(await screen.findByTestId("skeleton-summary")).toHaveTextContent("Conforme");
  });

  it("lists what to fix, opens existing ones and creates the missing ones", async () => {
    const user = userEvent.setup();
    const { calls, onSelect } = mount({
      conform: false,
      items: [
        item("a", "empty", "capitoli/a.md"),
        item("b", "missing", null),
        item("c", "ok", "x"),
      ],
      extra: ["capitoli/z.md"],
    });
    expect(await screen.findByTestId("skeleton-summary")).toHaveTextContent("2 da sistemare");
    await user.click(screen.getByRole("button", { name: /Scheletro/ }));
    await user.click(screen.getByRole("button", { name: /^A\s*Vuota/ }));
    expect(onSelect).toHaveBeenCalledWith("capitoli/a.md");
    expect(screen.getByRole("button", { name: /^B\s*Mancante/ })).toBeDisabled();
    expect(screen.getByText("1 fuori scheletro")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Crea le sezioni mancanti" }));
    await waitFor(() =>
      expect(
        calls.some((c) => c.url.endsWith("/skeleton/create-missing") && c.method === "POST"),
      ).toBe(true),
    );
  });
});
