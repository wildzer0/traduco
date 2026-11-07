import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import { useTranslationState } from "../../lib/translation-store";
import { installFakeApi } from "../../test/fake-api";
import { Preview } from "./Preview";

// The diagram engine is a lazy chunk. After an update an old page asks for a file that is gone.
vi.mock("mermaid", () => {
  throw new Error("Failed to fetch dynamically imported module");
});

describe("diagram that cannot be drawn", () => {
  it("says the engine did not load and what to do, instead of calling the diagram invalid", async () => {
    usePrefs.setState({ locale: "it" });
    useTranslationState.setState({ online: true, model: "m", pending: 0 });
    usePreview.setState({
      path: "capitoli/01-a/01-s.md",
      text: "```mermaid\nflowchart LR\n  A --> B\n```\n",
      mode: "source",
      topBlock: 0,
    });
    installFakeApi([]);
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <Preview projectId="demo" />
      </QueryClientProvider>,
    );
    expect(
      await screen.findByText(/Impossibile caricare il motore dei diagrammi/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Diagramma non valido/)).not.toBeInTheDocument();
  });
});
