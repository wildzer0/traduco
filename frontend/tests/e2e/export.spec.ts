import type { ChildProcess } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { createProject, onDisk, openApp, readFile, startFakeLlm, stopFakeLlm } from "./helpers";

let llm: ChildProcess | null = null;
test.beforeEach(async () => {
  llm = await startFakeLlm();
});
test.afterEach(async () => {
  if (llm) await stopFakeLlm(llm);
  llm = null;
});

const TEMPLATE = resolve(process.cwd(), "../examples/progetto-esempio/template/manuale.docx");

async function openExample(page: Page): Promise<string> {
  await openApp(page);
  await page.getByRole("button", { name: "Apri esempio" }).click();
  await expect(page.getByRole("navigation", { name: "Capitoli" })).toBeVisible();
  return new URL(page.url()).pathname.split("/")[2] ?? "";
}

async function zipText(path: string, entry: string): Promise<string> {
  // a .docx is a zip: the unzipped entry is found with the `unzip` available on the CI image and dev machines
  const { execFileSync } = await import("node:child_process");
  return execFileSync("unzip", ["-p", path, entry], { maxBuffer: 50 * 1024 * 1024 }).toString(
    "utf8",
  );
}

test("a company template is uploaded, analysed and its styles mapped", async ({ page }) => {
  await createProject(page, "Template prova");
  await page.getByRole("button", { name: "Template", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Template" });
  await drawer.getByLabel("File del template").setInputFiles(TEMPLATE);

  await expect(drawer.getByRole("list", { name: "Template del progetto" })).toContainText(
    "manuale",
  );
  await expect(drawer.getByText("predefinito", { exact: true })).toBeVisible();
  // what the analysis found
  await expect(drawer.getByText("{{CONTENUTO}}")).toBeVisible();
  await expect(drawer).toContainText("{{codice_documento}}");
  await expect(drawer).toContainText("{{cliente}}"); // inside a text box
  // the project metadata does not have those fields yet: the author is warned
  await expect(drawer.getByRole("alert")).toContainText("codice_documento");
  // the proposal picked the company styles
  await expect(drawer.getByLabel("Titolo 1")).toHaveValue("AziendaTitolo1");
  await expect(drawer.getByLabel("Tabella")).toHaveValue("AziendaTabella");
  // the mapping can be changed and is saved next to the template
  await drawer.getByLabel("Corpo del testo").selectOption("Normal");
  await drawer.getByRole("button", { name: "Salva la mappatura" }).click();
  await expect(drawer.getByRole("button", { name: "Salva la mappatura" })).toBeDisabled();
  expect(onDisk("template-prova", "template/manuale.docx")).toBe(true);
  await expect
    .poll(() => readFile("template-prova", "template/manuale.yaml"))
    .toContain("corpo: Normal");
  expect(readFile("template-prova", "progetto.yaml")).toContain("template_predefinito: manuale");
});

test("exporting the example gives a Word file with the cover, the fields and the translation", async ({
  page,
}) => {
  const id = await openExample(page);
  // the Mermaid diagram of "Collaudo" is drawn by the browser; open it once so it is cached
  await page.getByRole("button", { name: "Collaudo", exact: true }).click();
  await expect.poll(() => onDisk(id, ".traduco/cache/diagrams"), { timeout: 15_000 }).toBe(true);

  await page.getByRole("button", { name: "Esporta", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Esporta" });
  await panel.getByLabel("Cosa esportare").selectOption("project");
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 60_000 }),
    panel.getByRole("button", { name: "Esporta DOCX" }).click(),
  ]);
  const file = await download.path();
  expect(download.suggestedFilename()).toMatch(/\.docx$/);
  await expect(panel).toContainText("Documento pronto");

  const xml = await zipText(file, "word/document.xml");
  expect(xml).not.toContain("{{");
  expect(xml).toContain("DOC-2026-014"); // cover field
  expect(xml).toContain("[EN] Scopo del documento"); // the (fake) model's translation
  expect(xml).toContain("AziendaTitolo1"); // mapped style
  expect(xml).toContain("AziendaTabella");
  const header = await zipText(file, "word/header1.xml").catch(() => "");
  expect((xml + header).includes("DOC-2026-014")).toBe(true);
  expect(onDisk(id, "build")).toBe(true);
  expect(readFileSync(file).subarray(0, 2).toString()).toBe("PK");
});

test("a diagram that was never drawn stops the export and says where", async ({ page }) => {
  await openExample(page);
  await page.getByRole("button", { name: "Esporta", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Esporta" });
  await panel.getByLabel("Lingua").selectOption("sorgente");
  await panel.getByRole("button", { name: "Esporta DOCX" }).click();
  await expect(panel.getByRole("alert")).toContainText("Esportazione non riuscita", {
    timeout: 30_000,
  });
  await expect(panel.getByRole("alert")).toContainText("03-collaudo.md");
});
