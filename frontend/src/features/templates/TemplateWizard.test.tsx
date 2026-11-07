import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePrefs } from "../../lib/prefs";
import { installFakeApi } from "../../test/fake-api";
import { TemplateWizard } from "./TemplateWizard";

afterEach(() => vi.unstubAllGlobals());

describe("template wizard", () => {
  it("walks the four steps and sends the choices", async () => {
    usePrefs.setState({ locale: "it" });
    const created = vi.fn();
    const calls = installFakeApi([
      (c) =>
        c.url.endsWith("/template-wizard/fonts") ? { body: ["Calibri", "Arial"] } : undefined,
      (c) =>
        c.url.endsWith("/templates/wizard")
          ? { status: 201, body: { name: "aziendale" } }
          : undefined,
    ]);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TemplateWizard projectId="demo" onCreated={created} onCancel={() => undefined} />
      </QueryClientProvider>,
    );
    await screen.findAllByRole("option", { name: "Arial" });
    await userEvent.selectOptions(screen.getByLabelText("Carattere dei titoli"), "Arial");
    await userEvent.click(screen.getByRole("button", { name: "Avanti" }));
    await userEvent.click(screen.getByLabelText("Cliente"));
    await userEvent.click(screen.getByRole("button", { name: "Avanti" }));
    await userEvent.clear(screen.getByLabelText("Testo dell'intestazione"));
    await userEvent.type(screen.getByLabelText("Testo dell'intestazione"), "Riservato");
    await userEvent.click(screen.getByRole("button", { name: "Avanti" }));
    expect(screen.getByText("Passo 4 di 4 · Contenuti")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Crea il template" }));
    await waitFor(() => expect(created).toHaveBeenCalled());
    const sent = calls.find((c) => c.url.endsWith("/templates/wizard"))?.body as {
      nome: string;
      opzioni: { font_heading: string; cover_fields: string[]; header_text: string };
    };
    expect(sent.nome).toBe("aziendale");
    expect(sent.opzioni.font_heading).toBe("Arial");
    expect(sent.opzioni.cover_fields).toContain("cliente");
    expect(sent.opzioni.header_text).toBe("Riservato");
  });
});
