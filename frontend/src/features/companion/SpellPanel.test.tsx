import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { installFakeApi } from "../../test/fake-api";
import { SpellPanel } from "./SpellPanel";

afterEach(() => vi.unstubAllGlobals());

const issue = {
  key: "p:0",
  offset: 6,
  length: 6,
  message: "Errore di ortografia",
  rule: "IT",
  category: "misspelling",
  replacements: ["qual è"],
  context: "Dimmi qual'è la pompa.",
  word: "qual'è",
};

describe("spelling panel", () => {
  it("lists the problems and applies the chosen replacement to the source", async () => {
    usePrefs.setState({ locale: "it" });
    let call = 0;
    const calls = installFakeApi([
      (c) =>
        c.url.endsWith("/spellcheck")
          ? { body: { issues: call++ === 0 ? [issue] : [] } }
          : undefined,
      (c) => (c.url.endsWith("/assist/apply") ? { body: { path: "a.md", key: "p:0" } } : undefined),
    ]);
    render(<SpellPanel projectId="demo" path="capitoli/a/01.md" />);
    await userEvent.click(screen.getByRole("button", { name: "Controlla l'ortografia" }));
    expect(await screen.findByText("qual'è")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "qual è" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Nessun problema"));
    const applied = calls.find((c) => c.url.endsWith("/assist/apply"))?.body;
    expect(applied).toMatchObject({ key: "p:0", text: "Dimmi qual è la pompa." });
  });
});
