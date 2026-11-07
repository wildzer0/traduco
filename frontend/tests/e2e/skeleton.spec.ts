import { rmSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { listDir, onDisk, openApp, projectDir, readFile } from "./helpers";

test("a project created from the ECSS skeleton has the prescribed structure and tracks conformity", async ({
  page,
}) => {
  await openApp(page);
  await page.getByRole("button", { name: "Crea progetto" }).click();
  await page.getByLabel("Nome del progetto").fill("Specifica");
  await page
    .getByLabel("Struttura iniziale")
    .selectOption({ label: "Specifica dei requisiti tecnici (stile ECSS)" });
  await page.getByRole("button", { name: "Crea", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Capitoli" })).toBeVisible();

  // structure on disk
  expect(listDir("specifica", "capitoli")).toEqual([
    "01-introduzione",
    "02-documenti",
    "03-descrizione-del-sistema",
    "04-requisiti",
    "05-tracciabilita",
  ]);
  expect(listDir("specifica", "capitoli/01-introduzione")).toContain("01-scopo-e-ambito.md");
  expect(readFile("specifica", "capitoli/01-introduzione/01-scopo-e-ambito.md")).toContain(
    "scheletro: scopo",
  );

  // every mandatory section is still empty
  const summary = page.getByTestId("skeleton-summary");
  await expect(summary).toContainText("da sistemare");
  await page.getByRole("button", { name: /Scheletro/ }).click();
  await expect(page.getByRole("button", { name: /Scopo e ambito\s*Vuota/ })).toBeVisible();

  // a deleted mandatory section is reported as missing and can be recreated
  rmSync(join(projectDir("specifica"), "capitoli/01-introduzione/01-scopo-e-ambito.md"));
  await expect(page.getByRole("button", { name: /Scopo e ambito\s*Mancante/ })).toBeVisible();
  await page.getByRole("button", { name: "Crea le sezioni mancanti" }).click();
  await expect(page.getByRole("button", { name: /Scopo e ambito\s*Mancante/ })).toHaveCount(0);
  expect(onDisk("specifica", "capitoli/01-introduzione/01-scopo-e-ambito.md")).toBe(true);
});

test("an invalid skeleton file is refused with its line number", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "Crea progetto" }).click();
  await page.getByLabel("Nome del progetto").fill("Scheletro rotto");
  await page.getByLabel("Struttura iniziale").selectOption("@file");
  await page.getByLabel("File scheletro (YAML)").setInputFiles({
    name: "rotto.yaml",
    mimeType: "text/yaml",
    buffer: Buffer.from("nome: X\nnodi:\n  - id: a\n    titolo: A\n"),
  });
  await page.getByRole("button", { name: "Crea", exact: true }).click();
  await expect(page.getByRole("alert").first()).toContainText("riga 3");
  expect(onDisk("scheletro-rotto", "progetto.yaml")).toBe(false);
});
