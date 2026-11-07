import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../lib/prefs";
import type { Capabilities, ModelDownload } from "../lib/types";
import { installFakeApi } from "../test/fake-api";
import { ModelBanner } from "./ModelBanner";

function mount(model: ModelDownload) {
  const body: Capabilities = {
    pandoc: { available: true },
    libreoffice: { available: false },
    formats: ["docx"],
    model,
  };
  installFakeApi([(c) => (c.url === "/api/capabilities" ? { body } : undefined)]);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ModelBanner />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  usePrefs.setState({ locale: "it", settingsOpen: false });
  sessionStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("model banner", () => {
  it("shows the download progress and says writing is possible meanwhile", async () => {
    mount({ state: "downloading", model: "gemma4:e4b", completed: 250, total: 1000 });
    const banner = await screen.findByTestId("model-banner");
    expect(banner).toHaveTextContent("Download del modello gemma4:e4b: 25%");
    expect(banner).toHaveTextContent("Puoi già scrivere");
    expect(screen.getByTestId("model-progress")).toHaveStyle({ width: "25%" });
    expect(screen.queryByRole("button", { name: "Nascondi" })).not.toBeInTheDocument();
  });

  it("explains a failed download and offers the settings", async () => {
    const user = userEvent.setup();
    mount({ state: "error", model: "gemma4:e4b", error: "disk full" });
    expect(await screen.findByTestId("model-banner")).toHaveTextContent("disk full");
    await user.click(screen.getByRole("button", { name: "Apri le impostazioni del modello" }));
    expect(usePrefs.getState().settingsOpen).toBe(true);
  });

  it("tells a user without Ollama what to do, and can be dismissed", async () => {
    const user = userEvent.setup();
    mount({ state: "unavailable", model: "gemma4:e4b" });
    expect(await screen.findByTestId("model-banner")).toHaveTextContent("Ollama non è installato");
    await user.click(screen.getByRole("button", { name: "Nascondi" }));
    expect(screen.queryByTestId("model-banner")).not.toBeInTheDocument();
  });

  it("is absent when the model is ready or nothing is known", async () => {
    mount({ state: "ready", model: "gemma4:e4b" });
    await screen.findByTestId("model-banner").then(
      () => {
        throw new Error("should not be shown");
      },
      () => undefined,
    );
    expect(screen.queryByTestId("model-banner")).not.toBeInTheDocument();
  });
});
