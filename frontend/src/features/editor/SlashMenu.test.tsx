import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { SlashMenu } from "./SlashMenu";

const state = (query: string) => ({ x: 0, y: 0, query, consume: vi.fn() });

describe("slash menu", () => {
  it("offers the project's snippets by alias and by description", async () => {
    usePrefs.setState({ locale: "it" });
    const pick = vi.fn();
    render(
      <SlashMenu
        state={state("req")}
        snippets={[
          { alias: "req", descrizione: "Nuovo requisito" },
          { alias: "nota", descrizione: "" },
        ]}
        onPick={pick}
        onClose={() => undefined}
      />,
    );
    expect(screen.queryByText("nota")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText("req — Nuovo requisito"));
    expect(pick).toHaveBeenCalledWith({ type: "snippet", alias: "req" });
  });

  it("always ends with the way to edit them", async () => {
    usePrefs.setState({ locale: "it" });
    const pick = vi.fn();
    render(<SlashMenu state={state("zzz")} onPick={pick} onClose={() => undefined} />);
    await userEvent.click(screen.getByText("Modifica gli snippet…"));
    expect(pick).toHaveBeenCalledWith({ type: "edit-snippets" });
  });
});
