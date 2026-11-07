import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { installFakeApi } from "../../test/fake-api";
import { MetadataForm } from "./MetadataForm";

afterEach(() => vi.unstubAllGlobals());

describe("metadata form", () => {
  it("saves the values of the template fields and the revisions", async () => {
    usePrefs.setState({ locale: "it" });
    const calls = installFakeApi([(c) => (c.method === "PATCH" ? { body: {} } : undefined)]);
    const saved = vi.fn();
    render(
      <MetadataForm
        projectId="demo"
        fields={["codice_documento"]}
        metadata={{}}
        revisions={[]}
        onSaved={saved}
      />,
    );
    await userEvent.type(screen.getByLabelText("codice_documento"), "DOC-1");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi una revisione" }));
    await userEvent.type(screen.getByLabelText("Revisione"), "01");
    await userEvent.type(screen.getByLabelText("Cosa è cambiato"), "Prima emissione");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(saved).toHaveBeenCalled());
    const body = calls.find((c) => c.method === "PATCH")?.body as {
      metadati: Record<string, string>;
      revisioni: { rev: string; descrizione: string }[];
    };
    expect(body.metadati).toEqual({ codice_documento: "DOC-1" });
    expect(body.revisioni[0]).toMatchObject({ rev: "01", descrizione: "Prima emissione" });
  });
});
