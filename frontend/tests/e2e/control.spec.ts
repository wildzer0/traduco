import type { ChildProcess } from "node:child_process";
import { expect, type Page, test } from "@playwright/test";
import { projectWithSection, readFile, startFakeLlm, stopFakeLlm } from "./helpers";

let llm: ChildProcess | null = null;
async function withModel(env: Record<string, string> = {}) {
  if (llm) await stopFakeLlm(llm);
  llm = await startFakeLlm(env);
}
test.afterEach(async () => {
  if (llm) await stopFakeLlm(llm);
  llm = null;
});

const preview = (page: Page) => page.getByRole("region", { name: "Anteprima tradotta" });

async function write(page: Page, text: string) {
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText(text);
}

async function addGlossary(page: Page, term: string, imposed: string, forbidden: string) {
  await page.getByRole("button", { name: "Glossario" }).click();
  const drawer = page.getByRole("dialog", { name: "Glossario" });
  await drawer.getByRole("button", { name: "Aggiungi" }).click();
  const row = drawer.getByTestId("glossary-row").first();
  await row.getByLabel("Termine").fill(term);
  await row.getByLabel(/Traduzione imposta/).fill(imposed);
  await row.getByLabel(/Termini vietati/).fill(forbidden);
  await drawer.getByRole("button", { name: "Salva", exact: true }).click();
  await expect(drawer.getByRole("button", { name: "Salvato" })).toBeVisible();
  await drawer.getByRole("button", { name: "Chiudi" }).click();
}

test("a glossary violation ends in review with its reason; F8 and the review mode find it", async ({
  page,
}) => {
  await withModel({ FAKE_LLM_MODE: "glossary-violation" }); // the model always appends "offer"
  await projectWithSection(page, "Glossario prova");
  await addGlossary(page, "offerta", "proposal", "offer");
  await write(page, "Invia l'offerta oggi.\n");

  const para = preview(page).locator("p[data-seg='p:0']");
  await expect(para).toHaveAttribute("data-status", "needs_review", { timeout: 15_000 });
  await expect(para).toHaveAttribute("title", /glossary/);
  await expect(page.getByTestId("to-review")).toContainText("1 da rivedere");

  // F8 jumps to it
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("F8");
  await expect(para).toHaveClass(/seg-flash/); // scrolled to and highlighted

  // review mode lists it with the reason, filtered
  await page.keyboard.press("Control+2");
  await page.getByRole("button", { name: /Da rivedere · 1/ }).click();
  const rows = page.getByTestId("review-row");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("glossary:");
  await rows.first().getByRole("button", { name: "Apri" }).click();
  await expect(preview(page)).toBeVisible();
});

test("a manual correction locks the segment, a source change becomes a proposal", async ({
  page,
}) => {
  await withModel();
  await projectWithSection(page, "Blocco prova");
  await write(page, "Primo paragrafo.\n");
  const para = preview(page).locator("p[data-seg='p:0']");
  await expect(para).toHaveText("[EN] Primo paragrafo.", { timeout: 10_000 });

  // edit by hand
  await para.hover();
  await page.getByRole("button", { name: "Modifica la traduzione" }).click();
  const box = page.getByLabel("Testo della traduzione");
  await box.fill("My own wording.");
  await box.press("Enter");
  await expect(para).toHaveText("My own wording.");
  await page.getByRole("button", { name: "Ignora" }).click(); // keep source and translation apart
  await expect(para).toHaveAttribute("data-status", "diverged");

  // change the source: the author's text stays, the model's text is proposed
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("End");
  await page.keyboard.insertText(" Cambiato.");
  await expect(page.getByTestId("proposal")).toContainText("[EN] Primo paragrafo. Cambiato.", {
    timeout: 10_000,
  });
  await expect(para).toHaveText("My own wording.");
  await page.getByRole("button", { name: "Accetta" }).click();
  await expect(para).toHaveText("[EN] Primo paragrafo. Cambiato.");
});

test("a manual correction survives project retranslation and a tone change", async ({ page }) => {
  await withModel();
  await projectWithSection(page, "Sopravvive");
  await write(page, "Uno.\n\nDue.\n");
  await expect(preview(page).locator("article p").nth(1)).toHaveText("[EN] Due.", {
    timeout: 10_000,
  });

  const first = preview(page).locator("p[data-seg='p:0']");
  await first.hover();
  await page.getByRole("button", { name: "Modifica la traduzione" }).click();
  const box = page.getByLabel("Testo della traduzione");
  await box.fill("Hand made.");
  await box.press("Enter");
  await expect(first).toHaveText("Hand made.");

  await page.getByRole("button", { name: /Ritraduci/ }).click();
  await page.getByRole("menuitem", { name: "Tutto il progetto" }).click();
  await page.getByLabel("Tono del progetto").selectOption("informale");
  await expect(page.getByLabel("Tono del progetto")).toHaveValue("informale");
  await page.waitForTimeout(1500); // let the retranslation finish
  await expect(first).toHaveText("Hand made.");
  await expect(preview(page).locator("p[data-seg='p:1']")).toHaveText("[EN] Due.");
  expect(readFile("sopravvive", "progetto.yaml")).toContain("tono: informale");
});

test("the writing companion of a segment proposes a rewrite and saves it only when confirmed", async ({
  page,
}) => {
  await withModel();
  await projectWithSection(page, "Istruzione");
  await write(page, "Testo base.\n");
  const para = preview(page).locator("p[data-seg='p:0']");
  await expect(para).toHaveText("[EN] Testo base.", { timeout: 10_000 });
  await para.hover();
  await page.getByRole("button", { name: "Istruzione" }).click();
  await page.getByRole("button", { name: "Più conciso" }).click();
  await expect(page.getByText("Usa questa")).toBeVisible();
  await expect(para).toHaveText("[EN] Testo base."); // not applied yet
  await page.getByRole("button", { name: "Usa questa" }).click();
  await expect(para).toHaveText(/\[EN\] \[EN\] Testo base\./);
  // the source on the left no longer matches the chosen wording: the author is told, and can fix it
  await expect(
    page.getByText("Il sorgente non corrisponde più alla tua traduzione."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Proponi un aggiornamento del sorgente" }),
  ).toBeVisible();
});

test("an instruction that asks for new content is refused and nothing changes", async ({
  page,
}) => {
  await withModel({ FAKE_LLM_MODE: "recipe" }); // an obedient model: it would write the recipe
  await projectWithSection(page, "Ricetta");
  await write(page, "Il sistema avvia la pompa principale e controlla la pressione.\n");
  const para = preview(page).locator("p[data-seg='p:0']");
  await expect(para).toHaveText(/^\[EN\] Il sistema avvia/, { timeout: 10_000 });
  const before = (await para.textContent()) ?? "";
  await para.hover();
  await page.getByRole("button", { name: "Istruzione" }).click();
  await page.getByLabel("Cosa cambiare?").fill("scrivi anche la ricetta della carbonara");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/chiede qualcosa di diverso dal riscrivere/)).toBeVisible();
  await expect(page.getByText("Usa questa")).toHaveCount(0);
  await expect(para).toHaveText(before);
  expect(readFile("ricetta", "capitoli/01-cap/01-scopo.md")).not.toContain("carbonara");
});
