import type { ChildProcess } from "node:child_process";
import { expect, type Page, test } from "@playwright/test";
import { projectWithSection, readFile, startFakeLlm, stopFakeLlm } from "./helpers";

let llm: ChildProcess | null = null;
test.beforeEach(async () => {
  llm = await startFakeLlm();
});
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

test("a suggestion is shown as a difference and the file changes only when applied", async ({
  page,
}) => {
  await projectWithSection(page, "Companion");
  await write(
    page,
    "Questo paragrafo descrive la pompa e il suo funzionamento.\n\nSecondo paragrafo invariato.\n",
  );
  const first = preview(page).locator("p[data-seg='p:0']");
  const second = preview(page).locator("p[data-seg='p:1']");
  await expect(second).toHaveText("[EN] Secondo paragrafo invariato.", { timeout: 10_000 });
  const before = readFile("companion", "capitoli/01-cap/01-scopo.md");

  await first.hover();
  await page.getByRole("button", { name: "Migliora il testo" }).click();
  await page.getByRole("button", { name: "Correggi" }).click();
  // the fake model echoes the text with a "[EN] " prefix: that is the proposed difference
  await expect(page.getByTestId("diff").locator("ins")).toContainText("[EN]");
  expect(readFile("companion", "capitoli/01-cap/01-scopo.md")).toBe(before); // nothing written yet

  await page.getByRole("button", { name: "Applica" }).click();
  await expect(page.locator(".cm-content")).toContainText("[EN] Questo paragrafo descrive");
  expect(readFile("companion", "capitoli/01-cap/01-scopo.md")).toContain(
    "[EN] Questo paragrafo descrive la pompa",
  );
  // only the edited paragraph is translated again
  await expect(first).toHaveText(
    "[EN] [EN] Questo paragrafo descrive la pompa e il suo funzionamento.",
    {
      timeout: 10_000,
    },
  );
  await expect(second).toHaveText("[EN] Secondo paragrafo invariato.");
});

test("the toolbar assistant works on the paragraph under the cursor", async ({ page }) => {
  await projectWithSection(page, "Cursore");
  await write(page, "Un paragrafo abbastanza lungo da essere migliorato dal modello.\n");
  await page.getByRole("button", { name: "Assistente di scrittura" }).click();
  await expect(page.getByRole("dialog", { name: "Assistente di scrittura" })).toBeVisible();
  await page.getByRole("button", { name: "Più conciso" }).click();
  await expect(page.getByRole("button", { name: "Applica" })).toBeVisible({ timeout: 10_000 });
});

test("the section check applies the requirement rules and lets the author dismiss", async ({
  page,
}) => {
  await projectWithSection(page, "Controllo");
  await write(page, "La pompa deve partire e la valvola deve chiudersi, ove possibile.\n");
  await page.getByRole("button", { name: "Controlla la sezione" }).click();
  const panel = page.getByRole("dialog", { name: "Controllo della sezione" });
  await panel.getByLabel(/Regole per i requisiti/).check();
  await panel.getByRole("button", { name: "Controlla", exact: true }).click();
  const items = panel.getByTestId("suggestion");
  await expect(items.first()).toBeVisible({ timeout: 15_000 });
  await expect(panel).toContainText("Più di una prescrizione");
  const n = await items.count();
  expect(n).toBeGreaterThanOrEqual(2); // two prescriptions in one sentence, and a vague word
  await items.first().getByRole("button", { name: "Ignora" }).click();
  await expect(items).toHaveCount(n - 1);
});

test("with the model off the assistant is disabled and the editor keeps working", async ({
  page,
}) => {
  await projectWithSection(page, "Modello spento");
  await write(page, "Un paragrafo qualunque per provare l'assistente.\n");
  if (llm) await stopFakeLlm(llm);
  llm = null;
  await page.keyboard.insertText("Altro testo.\n");
  await expect(page.getByTestId("llm-indicator")).toHaveAttribute("data-online", "false", {
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Assistente di scrittura" }).click();
  await expect(page.getByText(/l'assistente è disattivato/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Correggi" })).toBeDisabled();
  await expect(page.getByTestId("save-status")).toContainText("Salvato");
});
