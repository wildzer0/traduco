import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { usePrefs } from "../../lib/prefs";
import { useView } from "../../lib/view-store";
import { installFakeApi } from "../../test/fake-api";
import { ExportPanel } from "./ExportPanel";

afterEach(() => vi.unstubAllGlobals());

describe("export panel", () => {
  it("opens even before the list of projects has arrived (it crashed in CI on a slow machine)", async () => {
    usePrefs.setState({ locale: "it" });
    useView.setState({ exportAutoRun: false });
    // the projects request never answers: the panel must still render
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => undefined)),
    );
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ExportPanel projectId="demo" selected={null} />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("dialog", { name: "Esporta" })).toBeInTheDocument();
    expect(screen.getByLabelText("Lingua")).toBeInTheDocument();
  });

  it("offers PDF and ODT only when LibreOffice is there", async () => {
    usePrefs.setState({ locale: "it" });
    installFakeApi([
      (c) =>
        c.url === "/api/capabilities"
          ? {
              body: {
                pandoc: { available: true },
                libreoffice: { available: false },
                formats: ["docx"],
                model: { state: "none" },
              },
            }
          : undefined,
      (c) => (c.url === "/api/projects" ? { body: [] } : undefined),
      (c) => (c.url.endsWith("/templates") ? { body: [] } : undefined),
    ]);
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ExportPanel projectId="demo" selected={null} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/PDF e ODT richiedono LibreOffice/)).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "PDF" })).toBeDisabled();
    expect(screen.getByRole("option", { name: "Word (.docx)" })).toBeEnabled();
  });
});
