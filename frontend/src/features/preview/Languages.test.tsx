import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { languageContext } from "../../lib/language";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import { installFakeApi } from "../../test/fake-api";
import { LanguageMenu } from "./LanguageMenu";
import { LanguagesPanel } from "./LanguagesPanel";

afterEach(() => {
  vi.unstubAllGlobals();
  usePreview.getState().setLanguage(null);
});

const rows = [
  { code: "it", role: "source", percent: 100, translated: 10, total: 10 },
  { code: "en", role: "official", percent: 100, translated: 10, total: 10 },
  {
    code: "de",
    role: "additional",
    percent: 40,
    translated: 4,
    total: 10,
    tono: "informale",
    formato_date: "dd.MM.yyyy",
  },
];

const wrap = (node: React.ReactNode) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {node}
    </QueryClientProvider>,
  );

describe("language menu", () => {
  it("lists the target languages with their progress and switches the one shown", async () => {
    usePrefs.setState({ locale: "it" });
    installFakeApi([(c) => (c.url.endsWith("/languages") ? { body: rows } : undefined)]);
    wrap(<LanguageMenu projectId="demo" />);
    await userEvent.click(await screen.findByRole("button", { name: /inglese/i }));
    expect(await screen.findByRole("menuitem", { name: /tedesco.*40%/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: /tedesco/i }));
    expect(usePreview.getState().language).toBe("de");
    expect(languageContext.lang).toBe("de"); // requests about translations now carry the language
    expect(screen.queryByRole("menuitem", { name: /italiano/i })).not.toBeInTheDocument(); // not a target
  });
});

describe("languages panel", () => {
  it("adds a language with its own tone and saves the whole list", async () => {
    usePrefs.setState({ locale: "it" });
    const calls = installFakeApi([
      (c) => (c.method === "PATCH" ? { body: {} } : undefined),
      (c) => (c.url.endsWith("/languages") ? { body: rows } : undefined),
    ]);
    wrap(<LanguagesPanel projectId="demo" />);
    expect(await screen.findByDisplayValue("de")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi una lingua" }));
    const codes = screen.getAllByLabelText("Codice lingua");
    await userEvent.type(codes[1] as HTMLElement, "fr");
    await userEvent.selectOptions(screen.getAllByLabelText("Tono")[1] as HTMLElement, "formale");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      lingue_aggiuntive: [
        { codice: "de", tono: "informale", formato_date: "dd.MM.yyyy" },
        { codice: "fr", tono: "formale" },
      ],
    });
  });
});
