import type { ChildProcess } from "node:child_process";
import { expect, type Page, test } from "@playwright/test";
import {
  addNode,
  projectWithSection,
  readFile,
  startFakeLlm,
  stopFakeLlm,
  waitSaved,
} from "./helpers";

let llm: ChildProcess | null = null;
test.beforeEach(async () => {
  llm = await startFakeLlm();
});
test.afterEach(async () => {
  if (llm) await stopFakeLlm(llm);
  llm = null;
});

const preview = (page: Page) => page.getByRole("region", { name: "Anteprima tradotta" });

/** Append text in the Markdown editor and wait until it is saved. */
async function write(page: Page, text: string) {
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText(text);
  await waitSaved(page);
}

test("the palette finds actions, the project text, and ? lists the shortcuts", async ({ page }) => {
  await projectWithSection(page, "Palette");
  await write(page, "La pompa principale parte subito.\n");

  await page.keyboard.press("Control+k");
  const palette = page.getByRole("dialog", { name: "Palette comandi" });
  await expect(palette).toBeVisible();
  await palette.getByRole("combobox").fill("esport");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Esporta" })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.keyboard.press("Control+Shift+f");
  await page.getByRole("combobox", { name: "Palette comandi" }).fill("pompa principale");
  // the source and its translation both contain the words: two hits, each says which it is
  const hits = page.getByRole("option", { name: /pompa principale parte subito/ });
  await expect(hits).toHaveCount(2);
  await expect(hits.filter({ hasText: "sorgente" })).toHaveCount(1);
  await expect(hits.filter({ hasText: "traduzione" })).toHaveCount(1);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Palette comandi" })).toHaveCount(0);

  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("?");
  await expect(page.getByRole("dialog", { name: "Scorciatoie da tastiera" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Scorciatoie da tastiera" })).toHaveCount(0);
});

test("the requirements panel lists what to fix", async ({ page }) => {
  await projectWithSection(page, "Requisiti prova");
  await write(
    page,
    "FOO-REQ-00001 Il sistema deve partire.\n\nFOO-REQ-00099 Citato qui, vedi FOO-REQ-00001.\n\nVedi FOO-REQ-00042.\n",
  );
  await page.getByRole("button", { name: "Requisiti", exact: true }).click();
  const problems = page.getByRole("list", { name: "Da controllare" });
  await expect(problems).toContainText("FOO-REQ-00042");
  await expect(problems).toContainText("Citato ma mai definito");
  await expect(problems).toContainText("Mai citato"); // FOO-REQ-00099 is never mentioned
});

test("snippets with a counter that goes on", async ({ page }) => {
  await projectWithSection(page, "Snippet prova");
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("/");
  await page.getByRole("option", { name: "Modifica gli snippet…" }).click();
  const drawer = page.getByRole("dialog", { name: "Snippet" });
  await drawer.getByRole("button", { name: "Inserisci un esempio" }).click();
  await drawer.getByRole("button", { name: "Salva" }).click();
  await expect(drawer.getByText("Salvato")).toBeVisible();
  await expect(drawer).toContainText("FOO-REQ-00001"); // the next number of the counter
  await drawer.getByRole("button", { name: "Chiudi" }).click();

  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("/req");
  await page.keyboard.press("Enter");
  await expect(page.locator(".cm-content")).toContainText("**FOO-REQ-00001** Il sistema deve");
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\n\n/req");
  await page.keyboard.press("Enter");
  await expect(page.locator(".cm-content")).toContainText("**FOO-REQ-00002**");
});

test("review comments: add, reply and resolve", async ({ page }) => {
  await projectWithSection(page, "Commenti prova");
  await write(page, "Il sistema parte entro dieci secondi.\n");
  await expect(preview(page).locator("p[data-seg='p:0']")).toHaveText(/\[EN\]/, {
    timeout: 10_000,
  });
  await page.getByRole("button", { name: "Commenti", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Commenti" });
  await panel.getByLabel("Commenta").selectOption({ index: 1 });
  await panel.getByLabel("Il tuo nome").fill("Anna");
  await panel.getByLabel("Commento", { exact: true }).fill("Quanti secondi, davvero?");
  await panel.getByRole("button", { name: "Invia" }).last().click();
  const thread = panel.getByTestId("thread");
  await expect(thread).toContainText("Quanti secondi, davvero?");
  await thread.getByLabel("Rispondi").fill("Dieci, da specifica.");
  await thread.getByRole("button", { name: "Invia" }).click();
  await expect(thread).toContainText("Dieci, da specifica.");
  await thread.getByRole("button", { name: "Risolvi" }).click();
  await expect(thread.getByRole("button", { name: "Riapri" })).toBeVisible();
  expect(readFile("commenti-prova", "capitoli/01-cap/01-scopo.md")).not.toContain("Anna");
});

test("issues: freeze two, compare, and turn the differences into the revision table", async ({
  page,
}) => {
  await projectWithSection(page, "Emissioni prova");
  await write(page, "Uno due tre.\n");
  await page.getByRole("button", { name: "Emissioni", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Emissioni" });
  await panel.getByLabel("Numero").fill("1");
  await panel.getByLabel("Descrizione").fill("Prima emissione");
  await panel.getByRole("button", { name: "Congela" }).click();
  await expect(panel.getByText("Prima emissione").first()).toBeVisible();
  await panel.getByRole("button", { name: "Chiudi" }).click();

  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText("\nQuattro cinque.\n");
  await waitSaved(page);
  await page.getByRole("button", { name: "Emissioni", exact: true }).click();
  await panel.getByLabel("Numero").fill("2");
  await panel.getByRole("button", { name: "Congela" }).click();
  await expect(panel.getByRole("button", { name: "Confronta con la precedente" })).toBeVisible();

  await panel.getByRole("button", { name: "Confronta con la precedente" }).click();
  const compare = page.getByRole("dialog", { name: "Confronto" });
  await expect(compare.getByText("Quattro cinque.")).toBeVisible();
  await expect(compare.getByRole("status")).toContainText("Cambio 1 di 1");
  await compare.getByRole("button", { name: "Chiudi" }).click();

  await panel.getByRole("button", { name: "Tabella dei cambiamenti" }).first().click();
  await panel.getByRole("button", { name: "Scrivila con il modello" }).click();
  await expect(
    panel.getByRole("button", { name: "Usa nella tabella delle revisioni" }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Usa nella tabella delle revisioni" }).click();
  await expect(panel.getByText("Tabella delle revisioni aggiornata")).toBeVisible();
  await expect.poll(() => readFile("emissioni-prova", "progetto.yaml")).toContain("rev: '2'");
  expect(readFile("emissioni-prova", ".traduco/emissioni/1/meta.json")).toContain(
    "Prima emissione",
  );
});

test("a second language: add it, look at it, and let it start from the approved English", async ({
  page,
}) => {
  await projectWithSection(page, "Lingue prova");
  await write(page, "La pompa parte subito.\n");
  await expect(preview(page).locator("p[data-seg='p:0']")).toHaveText(
    "[EN] La pompa parte subito.",
    {
      timeout: 10_000,
    },
  );

  await preview(page).getByRole("button", { name: "inglese" }).click();
  await page.getByRole("menuitem", { name: "Lingue del progetto…" }).click();
  const panel = page.getByRole("dialog", { name: "Lingue del progetto…" });
  await panel.getByRole("button", { name: "Aggiungi una lingua" }).click();
  await panel.getByLabel("Codice lingua").fill("de");
  await panel.getByLabel("Traduci a partire da").selectOption("ufficiale");
  await panel.getByRole("button", { name: "Salva" }).click();
  await expect(panel.getByText("Salvato")).toBeVisible();
  await expect.poll(() => readFile("lingue-prova", "progetto.yaml")).toContain("base: ufficiale");
  await panel.getByRole("button", { name: "Chiudi" }).click();

  await preview(page).getByRole("button", { name: "inglese" }).click();
  await page.getByRole("menuitem", { name: /tedesco/ }).click();
  await expect(page.getByText("Anteprima · tedesco")).toBeVisible();
  const para = preview(page).locator("p[data-seg='p:0']");
  // the English is not approved yet: German waits
  await expect(para).toHaveAttribute("data-status", "queued", { timeout: 10_000 });

  await preview(page).getByRole("button", { name: "tedesco" }).click();
  await page.getByRole("menuitem", { name: /inglese/ }).click();
  const english = preview(page).locator("p[data-seg='p:0']");
  await english.hover();
  await page.getByRole("button", { name: "Approva" }).click();
  await preview(page).getByRole("button", { name: "inglese" }).click();
  await page.getByRole("menuitem", { name: /tedesco/ }).click();
  await expect(preview(page).locator("p[data-seg='p:0']")).toHaveText(
    "[EN] [EN] La pompa parte subito.",
    {
      timeout: 15_000,
    },
  );
});

test("the translation memory reuses an approved sentence and shows similar ones", async ({
  page,
}) => {
  await projectWithSection(page, "Memoria prova");
  await write(page, "La pompa principale parte subito.\n");
  const first = preview(page).locator("p[data-seg='p:0']");
  await expect(first).toHaveText("[EN] La pompa principale parte subito.", { timeout: 10_000 });
  await first.hover();
  await page.getByRole("button", { name: "Approva" }).click();
  await expect(first).toHaveAttribute("data-status", "approved");

  await addNode(page, "+ Sezione", "Seconda");
  await page.getByRole("button", { name: "Seconda", exact: true }).click();
  await expect(page.getByLabel("Testo della sezione")).toBeVisible();
  await write(page, "La pompa principale parte subito.\n");
  const second = preview(page).locator("p[data-seg='p:0']");
  await expect(second).toHaveText("[EN] La pompa principale parte subito.", { timeout: 10_000 });
  await second.hover();
  await page.getByRole("button", { name: "Memoria di traduzione" }).click();
  const box = page.getByRole("dialog", { name: "Memoria di traduzione" });
  await expect(box).toContainText("100%");
  await expect(box).toContainText("La pompa principale parte subito.");
});
