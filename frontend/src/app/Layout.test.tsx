import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../lib/prefs";
import { Layout } from "./Layout";

function renderLayout() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Layout />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  usePrefs.setState({ locale: "it", theme: "system", sidebarOpen: true });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", version: "0.1.0" }))),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe("Layout", () => {
  it("renders the three columns plus top and status bars", async () => {
    renderLayout();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Capitoli" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "Editor" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Anteprima tradotta" })).toBeInTheDocument();
    expect(await screen.findByText("Backend attivo · v0.1.0")).toBeInTheDocument();
  });

  it("shows an error state when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    renderLayout();
    expect(await screen.findByText("Backend non raggiungibile")).toBeInTheDocument();
  });

  it("toggles the sidebar with the button and with Ctrl+B", async () => {
    const user = userEvent.setup();
    renderLayout();
    await user.click(screen.getByRole("button", { name: /barra laterale/i }));
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    await user.keyboard("{Control>}b{/Control}");
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("switches language and theme from the settings drawer, closes with Esc", async () => {
    const user = userEvent.setup();
    renderLayout();
    await user.click(screen.getByRole("button", { name: "Impostazioni" }));
    await user.selectOptions(screen.getByLabelText("Lingua dell'interfaccia"), "en");
    await waitFor(() => expect(screen.getByRole("navigation", { name: "Chapters" })).toBeVisible());
    await user.selectOptions(screen.getByLabelText("Theme"), "dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
