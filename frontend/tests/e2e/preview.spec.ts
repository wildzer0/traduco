import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import {
  onDisk,
  projectWithSection as openSection,
  projectDir,
  showSource,
  waitSaved,
} from "./helpers";

/** These tests look at the rendered source, so they switch the preview to it first. */
async function projectWithSection(page: import("@playwright/test").Page, nome: string) {
  await openSection(page, nome);
  await showSource(page);
}

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

async function typeMarkdown(page: import("@playwright/test").Page, text: string) {
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  const cm = page.locator(".cm-content");
  await cm.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText(text);
}

test("the preview renders what is typed, without waiting for the save", async ({ page }) => {
  await projectWithSection(page, "Anteprima");
  await typeMarkdown(
    page,
    "\n# Titolo grande\n\nUn _paragrafo_ con **forza**.\n\n| a | b |\n| - | - |\n| 1 | 2 |\n",
  );
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator("h1")).toHaveText("Titolo grande");
  await expect(preview.locator("em")).toHaveText("paragrafo");
  await expect(preview.locator("strong")).toHaveText("forza");
  await expect(preview.locator("table td").first()).toHaveText("1");
});

test("raw HTML typed in a section is shown as text, never executed", async ({ page }) => {
  const errors: string[] = [];
  page.on("dialog", (d) => {
    errors.push(d.message());
    void d.dismiss();
  });
  await projectWithSection(page, "Sicurezza");
  await typeMarkdown(
    page,
    "\n<img src=x onerror=alert(1)>\n\n<script>alert(2)</script>\n\n[x](javascript:alert(3))\n",
  );
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator("p").first()).toContainText("<img src=x onerror=alert(1)>");
  await expect(preview.locator("img, script")).toHaveCount(0);
  await expect(preview.locator('a[href^="javascript:"]')).toHaveCount(0);
  await page.waitForTimeout(500);
  expect(errors).toEqual([]);
});

test("a pasted image appears in the preview and in img/", async ({ page }) => {
  await projectWithSection(page, "FotoPrev");
  await page.getByLabel("Testo della sezione").click();
  await page
    .getByTestId("image-input")
    .setInputFiles({ name: "Foto.png", mimeType: "image/png", buffer: PNG });
  await expect.poll(() => onDisk("fotoprev", "capitoli/01-cap/img/foto.png")).toBe(true);
  const img = page.getByRole("region", { name: "Anteprima tradotta" }).locator("img");
  await expect(img).toHaveAttribute("src", /assets\?path=capitoli%2F01-cap%2Fimg%2Ffoto\.png/);
  await expect
    .poll(() => img.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0))
    .toBe(true);
});

test("a Mermaid diagram is drawn in the preview and cached as PNG once saved", async ({ page }) => {
  await projectWithSection(page, "Diagrammi");
  const code = "flowchart LR\n  A[Inizio] --> B[Fine]";
  await typeMarkdown(page, `\n\`\`\`mermaid\n${code}\n\`\`\`\n`);
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator(".mermaid-block svg")).toBeVisible({ timeout: 20_000 });
  await expect(preview.locator(".mermaid-block svg")).toContainText("Inizio");
  await waitSaved(page);
  const hash = createHash("sha256").update(`${code}\n`).digest("hex");
  const png = join(projectDir("diagrammi"), `.traduco/cache/diagrams/${hash}.png`);
  await expect
    .poll(() => onDisk("diagrammi", `.traduco/cache/diagrams/${hash}.png`), { timeout: 20_000 })
    .toBe(true);
  const bytes = readFileSync(png);
  expect(bytes.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  expect(bytes.length).toBeGreaterThan(500);
  expect(onDisk("diagrammi", `.traduco/cache/diagrams/${hash}.svg`)).toBe(true);
});

test("an invalid diagram is flagged without breaking the preview", async ({ page }) => {
  await projectWithSection(page, "Rotto");
  await typeMarkdown(page, "\n```mermaid\nnon è un diagramma ???\n```\n\nTesto dopo.\n");
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator('.mermaid-block[data-state="error"]')).toBeVisible({
    timeout: 20_000,
  });
  await expect(preview).toContainText("Testo dopo.");
});

test("scrolling the editor scrolls the preview to the same block", async ({ page }) => {
  await projectWithSection(page, "Scorri");
  const lines = Array.from(
    { length: 60 },
    (_, i) => `## Capitolo ${i + 1}\n\nParagrafo del capitolo ${i + 1}.\n`,
  ).join("\n");
  await typeMarkdown(page, `\n${lines}`);
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator("h2")).toHaveCount(60);
  const editorScroll = page.getByRole("main").locator(".editor-scroll");
  await editorScroll.evaluate((el) => {
    el.scrollTop = el.scrollHeight / 2;
  });
  const previewScroll = preview.locator(".editor-scroll");
  await expect.poll(() => previewScroll.evaluate((el) => el.scrollTop)).toBeGreaterThan(200);
  // the heading at the top of the preview is (about) the one at the top of the editor
  const topHeading = await previewScroll.evaluate((box) => {
    const top = box.getBoundingClientRect().top;
    const hs = [...box.querySelectorAll("h2")];
    return hs.find((h) => h.getBoundingClientRect().bottom > top)?.textContent ?? "";
  });
  const n = Number(topHeading.replace(/\D/g, ""));
  expect(n).toBeGreaterThan(15);
  expect(n).toBeLessThan(45);
});
