import type { ChildProcess } from "node:child_process";
import { expect, test } from "@playwright/test";
import { projectWithSection, startFakeLlm, stopFakeLlm } from "./helpers";

let llm: ChildProcess | null = null;

test.beforeEach(async () => {
  llm = await startFakeLlm();
});
test.afterEach(async () => {
  if (llm) await stopFakeLlm(llm);
  llm = null;
});

async function typeInMarkdown(page: import("@playwright/test").Page, text: string) {
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  const cm = page.locator(".cm-content");
  await cm.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText(text);
}

test("a written paragraph appears translated in the preview", async ({ page }) => {
  await projectWithSection(page, "Traduzione");
  await typeInMarkdown(page, "Premi `Invio` per **continuare**.\n");
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  // fake-llm answers "[EN] <text>"; code and bold survive untouched
  await expect(preview.locator("p")).toHaveText("[EN] Premi Invio per continuare.", {
    timeout: 8000,
  });
  await expect(preview.locator("p code")).toHaveText("Invio");
  await expect(preview.locator("p strong")).toHaveText("continuare");
  await expect(page.getByTestId("llm-indicator")).toHaveAttribute("data-online", "true");
});

test("editing one paragraph retranslates only that one", async ({ page }) => {
  await projectWithSection(page, "Solo uno");
  await typeInMarkdown(page, "Primo paragrafo.\n\nSecondo paragrafo.\n");
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator("p").nth(1)).toHaveText("[EN] Secondo paragrafo.", {
    timeout: 8000,
  });
  // the first paragraph keeps its translation while the second one is edited
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText(" Modificato.");
  await expect(preview.locator("p").nth(1)).toHaveText("[EN] Secondo paragrafo. Modificato.", {
    timeout: 8000,
  });
  await expect(preview.locator("p").first()).toHaveText("[EN] Primo paragrafo.");
});

test("with the model off the editor keeps working and translation resumes by itself", async ({
  page,
}) => {
  await projectWithSection(page, "Offline");
  await typeInMarkdown(page, "Primo.\n");
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator("p")).toHaveText("[EN] Primo.", { timeout: 8000 });

  if (llm) await stopFakeLlm(llm);
  llm = null;
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("Secondo mentre il modello è spento.\n");
  // saving is not blocked, the banner explains what is going on
  await expect(page.getByTestId("save-status")).toContainText("Salvato", { timeout: 8000 });
  await expect(page.getByText(/Modello non raggiungibile — la scrittura continua/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByTestId("llm-indicator")).toHaveAttribute("data-online", "false");

  llm = await startFakeLlm();
  await expect(preview.locator("p").nth(1)).toHaveText("[EN] Secondo mentre il modello è spento.", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("llm-indicator")).toHaveAttribute("data-online", "true");
});
