import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { installFakeApi } from "../../test/fake-api";
import { MemoryBox } from "./MemoryBox";

afterEach(() => vi.unstubAllGlobals());

function mount(matches: object[], onUse = vi.fn()) {
  usePrefs.setState({ locale: "it" });
  installFakeApi([(c) => (c.url.includes("/tm/suggest") ? { body: { matches } } : undefined)]);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryBox
        projectId="demo"
        path="capitoli/a/01.md"
        segKey="p:0"
        top={0}
        onUse={onUse}
        onClose={() => undefined}
      />
    </QueryClientProvider>,
  );
  return onUse;
}

describe("translation memory box", () => {
  it("shows the similarity and uses the chosen translation", async () => {
    const onUse = mount([
      {
        source: "La pompa parte subito.",
        target: "The pump starts at once.",
        score: 0.91,
        origin: "approved",
      },
    ]);
    expect(await screen.findByText(/91% · La pompa parte subito\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usa questa" }));
    expect(onUse).toHaveBeenCalledWith("The pump starts at once.");
  });

  it("says so when the memory has nothing", async () => {
    mount([]);
    expect(
      await screen.findByText("Nessuna frase simile è stata ancora approvata."),
    ).toBeInTheDocument();
  });
});
