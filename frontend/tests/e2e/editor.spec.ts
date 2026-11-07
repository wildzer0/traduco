import { expect, test } from "@playwright/test";
import { onDisk, projectWithSection, readFile, waitSaved, writeProjectFile } from "./helpers";

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const FILE = "capitoli/01-cap/01-scopo.md";

test("typing in Document mode autosaves the canonical Markdown", async ({ page }) => {
  await projectWithSection(page, "Digita");
  const editor = page.getByLabel("Testo della sezione");
  await editor.click();
  await page.keyboard.type("Primo paragrafo");
  await page.keyboard.press("Enter");
  await page.keyboard.type("Secondo");
  await waitSaved(page);
  await expect
    .poll(() => readFile("digita", FILE))
    .toBe("---\ntitle: Scopo\n---\n\nPrimo paragrafo\n\nSecondo\n");
});

test("toolbar bold and table work in Document mode and reach the file", async ({ page }) => {
  await projectWithSection(page, "Toolbar");
  await page.getByLabel("Testo della sezione").click();
  await page.keyboard.type("testo");
  await page.keyboard.press("Control+a");
  await page.getByRole("button", { name: "Grassetto" }).click();
  await waitSaved(page);
  await expect.poll(() => readFile("toolbar", FILE)).toContain("**testo**");
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Tabella" }).click();
  await expect
    .poll(() => readFile("toolbar", FILE))
    .toMatch(/\*\*testo\*\*\n\n\|[ ]+\|[ ]+\|\n\| :?-+/);
});

test("switching between Document and Markdown 10 times never changes the file", async ({
  page,
}) => {
  await projectWithSection(page, "Cambio");
  await page.getByLabel("Testo della sezione").click();
  await page.keyboard.type("Un paragrafo");
  await waitSaved(page);
  const before = readFile("cambio", FILE);
  for (let i = 0; i < 5; i++) {
    await page.getByRole("button", { name: "Markdown", exact: true }).click();
    await expect(page.locator(".cm-content")).toContainText("Un paragrafo");
    await page.keyboard.press("Control+/");
    await expect(page.locator(".ProseMirror")).toContainText("Un paragrafo");
  }
  await page.waitForTimeout(1500);
  expect(readFile("cambio", FILE)).toBe(before);
});

test("Markdown mode shows the whole file and saves in canonical form", async ({ page }) => {
  await projectWithSection(page, "Sorgente");
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  const cm = page.locator(".cm-content");
  await expect(cm).toContainText("title: Scopo");
  await cm.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\nTitolo\n=====\n\n*enfasi* e __forte__\n");
  await waitSaved(page);
  await expect
    .poll(() => readFile("sorgente", FILE))
    .toContain("# Titolo\n\n_enfasi_ e **forte**\n");
});

test("slash menu inserts a heading", async ({ page }) => {
  await projectWithSection(page, "Slash");
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  const cm = page.locator(".cm-content");
  await cm.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\n/titolo 2");
  await expect(page.getByRole("listbox", { name: "Inserisci" })).toBeVisible();
  await page.keyboard.press("Enter");
  await page.keyboard.type("Sezione");
  await waitSaved(page);
  await expect.poll(() => readFile("slash", FILE)).toContain("## Sezione");
});

test("an image chosen from the toolbar is stored in img/ and shown", async ({ page }) => {
  await projectWithSection(page, "Immagini");
  await page.getByLabel("Testo della sezione").click();
  await page
    .getByTestId("image-input")
    .setInputFiles({ name: "Schema.png", mimeType: "image/png", buffer: PNG });
  await expect.poll(() => onDisk("immagini", "capitoli/01-cap/img/schema.png")).toBe(true);
  await expect(page.locator(".ProseMirror img[data-original]")).toHaveAttribute(
    "src",
    /\/api\/projects\/immagini\/assets\?path=/,
  );
  await expect.poll(() => readFile("immagini", FILE)).toContain("![](img/schema.png)");
  const loaded = await page
    .locator(".ProseMirror img[data-original]")
    .evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0);
  expect(loaded).toBe(true);
});

test("a change made outside the app is loaded when there is nothing unsaved", async ({ page }) => {
  await projectWithSection(page, "Esterno");
  await page.getByLabel("Testo della sezione").click();
  await page.keyboard.type("Versione app");
  await waitSaved(page);
  writeProjectFile("esterno", FILE, "---\ntitle: Scopo\n---\n\nScritto da un altro editor\n");
  // Normally the WebSocket pushes it; where the file watcher polls (WSL, network drives) coming back
  // to the window is the fallback, so simulate that too.
  await page.waitForTimeout(2000);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.locator(".ProseMirror")).toContainText("Scritto da un altro editor", {
    timeout: 15_000,
  });
});

test("a clash between unsaved typing and an outside change offers reload or keep mine", async ({
  page,
}) => {
  await projectWithSection(page, "Conflitto");
  await page.getByLabel("Testo della sezione").click();
  await page.keyboard.type("Prima");
  await waitSaved(page);
  await page.keyboard.type(" e la mia aggiunta");
  writeProjectFile("conflitto", FILE, "---\ntitle: Scopo\n---\n\nVersione esterna\n");
  await expect(page.getByText("Questo file è stato modificato fuori dall'app.")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "Mantieni la mia versione" }).click();
  await waitSaved(page);
  await expect.poll(() => readFile("conflitto", FILE)).toContain("Prima e la mia aggiunta");
});
