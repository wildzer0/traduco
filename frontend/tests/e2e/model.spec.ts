import type { ChildProcess } from "node:child_process";
import { expect, test } from "@playwright/test";
import {
  createProject,
  projectWithSection,
  setModelState,
  startFakeLlm,
  stopFakeLlm,
} from "./helpers";

let llm: ChildProcess | null = null;
test.beforeEach(async () => {
  setModelState(null);
  llm = await startFakeLlm();
});
test.afterEach(async () => {
  setModelState(null);
  if (llm) await stopFakeLlm(llm);
  llm = null;
});

test("the first-run banner shows the download and goes away when the model is ready", async ({
  page,
}) => {
  setModelState({ state: "downloading", model: "gemma4:e4b", completed: 300, total: 1000 });
  await createProject(page, "Primo avvio");
  const banner = page.getByTestId("model-banner");
  await expect(banner).toContainText("Download del modello gemma4:e4b: 30%");
  await expect(banner).toContainText("Puoi già scrivere");
  setModelState({ state: "downloading", model: "gemma4:e4b", completed: 800, total: 1000 });
  await expect(banner).toContainText("80%", { timeout: 10_000 });
  setModelState({ state: "ready", model: "gemma4:e4b" });
  await expect(banner).toHaveCount(0, { timeout: 40_000 }); // polled every 30 s once not downloading
});

test("translation waits for the model instead of failing, then runs by itself", async ({
  page,
}) => {
  setModelState({ state: "downloading", model: "gemma4:e4b", completed: 1, total: 100 });
  await projectWithSection(page, "Attesa modello");
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End"); // Markdown mode shows the front matter too
  await page.keyboard.insertText("Un paragrafo da tradurre quando il modello sarà pronto.\n");
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.getByText(/Il modello è in download/)).toBeVisible({ timeout: 15_000 });
  // nothing was marked as failed while waiting
  await expect(preview.locator("[data-status='needs_review']")).toHaveCount(0);

  setModelState({ state: "ready", model: "gemma4:e4b" });
  await expect(preview.locator("p[data-seg='p:0']")).toHaveText(
    "[EN] Un paragrafo da tradurre quando il modello sarà pronto.",
    { timeout: 30_000 },
  );
});

test("without Ollama the banner says so and the editor keeps working", async ({ page }) => {
  setModelState({ state: "unavailable", model: "gemma4:e4b" });
  await projectWithSection(page, "Senza Ollama");
  await expect(page.getByTestId("model-banner")).toContainText("--llm builtin");
  await page.getByTestId("model-banner").getByRole("button", { name: "Nascondi" }).click();
  await expect(page.getByTestId("model-banner")).toHaveCount(0);
  await expect(page.getByLabel("Testo della sezione")).toBeVisible();
});

test("PDF and ODT are offered only when LibreOffice is installed", async ({ page, request }) => {
  await projectWithSection(page, "Formati");
  const caps = (await (await request.get("/api/capabilities")).json()) as {
    libreoffice: { available: boolean };
  };
  await page.getByRole("button", { name: "Esporta", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Esporta" });
  const pdf = panel.getByRole("option", { name: "PDF" });
  if (caps.libreoffice.available) {
    await expect(pdf).toBeEnabled();
  } else {
    await expect(pdf).toBeDisabled();
    await expect(panel).toContainText("PDF e ODT richiedono LibreOffice");
  }
  await expect(panel.getByRole("option", { name: "Word (.docx)" })).toBeEnabled();
});
