import { expect, type Page, test } from "@playwright/test";
import { onDisk, openApp } from "./helpers";

async function newProject(page: Page, name: string) {
  await page.getByRole("button", { name: "Crea progetto" }).click();
  await page.getByLabel("Nome del progetto").fill(name);
  await page.getByRole("button", { name: "Crea", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Capitoli" })).toBeVisible();
}

async function newFolder(page: Page, name: string) {
  await page.getByRole("button", { name: "Nuova cartella" }).first().click();
  await page.getByLabel("Nome della cartella").fill(name);
  await page.getByRole("button", { name: "Crea", exact: true }).click();
}

test("folders inside folders, search, copy, drag, delete and restore", async ({ page }) => {
  await openApp(page);

  // a folder, and a folder inside it
  await newFolder(page, "Clienti");
  await page
    .getByRole("navigation", { name: "Cartelle" })
    .getByRole("button", { name: /^Clienti/ })
    .first()
    .click();
  await newFolder(page, "ACME");
  await expect(page.getByRole("navigation", { name: "Dove sei" })).toContainText("Clienti");

  // a project made while looking inside "Clienti" goes there
  await newProject(page, "Manuale zebra");
  await page.getByRole("button", { name: "Tutti i progetti" }).first().click();
  const tree = page.getByRole("navigation", { name: "Cartelle" });
  await tree
    .getByRole("button", { name: /^Clienti/ })
    .first()
    .click();
  const row = page.getByTestId("project-row").filter({ hasText: "Manuale zebra" });
  await expect(row).toBeVisible();
  await expect(row).toContainText("nessuna"); // no issue yet
  await expect(row).toContainText("ora"); // changed just now

  // search finds it from the top, and says where it is
  await page.getByRole("button", { name: "Tutti i progetti" }).first().click();
  await page.getByRole("searchbox").fill("zebra");
  await expect(page.getByTestId("project-row")).toHaveCount(1);
  await expect(page.getByTestId("project-row")).toContainText("Clienti");
  await page.getByRole("searchbox").fill("");

  // a copy
  await tree
    .getByRole("button", { name: /^Clienti/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Azioni su Manuale zebra" }).click();
  await page.getByRole("menuitem", { name: "Duplica…" }).click();
  await page.getByLabel("Nome della copia").fill("Manuale zebra v2");
  await page.getByRole("button", { name: "Duplica", exact: true }).click();
  await expect(page.getByTestId("project-row")).toHaveCount(2);
  expect(onDisk("manuale-zebra-v2", "progetto.yaml")).toBe(true);

  // drag the copy onto the sub-folder
  const copy = page.getByTestId("project-row").filter({ hasText: "Manuale zebra v2" });
  const card = page.getByRole("button", { name: /^ACME/ }).last();
  await copy.dragTo(card);
  await expect(page.getByTestId("project-row")).toHaveCount(1);
  await card.click();
  await expect(page.getByTestId("project-row")).toContainText("Manuale zebra v2");

  // delete: it asks, then goes to the trash and comes back
  await page.getByRole("button", { name: "Azioni su Manuale zebra v2" }).click();
  await page.getByRole("menuitem", { name: "Elimina…" }).click();
  await page.getByRole("button", { name: "Sposta nel cestino" }).click();
  await expect(page.getByTestId("project-row")).toHaveCount(0);
  expect(onDisk("manuale-zebra-v2", "progetto.yaml")).toBe(false);
  await page.getByRole("button", { name: /Cestino/ }).click();
  const trash = page.getByRole("dialog", { name: "Cestino" });
  await expect(trash).toContainText("Manuale zebra v2");
  await trash.getByRole("button", { name: "Ripristina" }).click();
  await trash.getByRole("button", { name: "Chiudi" }).click();
  expect(onDisk("manuale-zebra-v2", "progetto.yaml")).toBe(true);
});

test("the project page and the list are one click apart", async ({ page }) => {
  await openApp(page);
  await newProject(page, "Avanti e indietro");
  await page.getByRole("button", { name: "Tutti i progetti" }).first().click();
  await expect(page.getByRole("heading", { name: "Progetti" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("navigation", { name: "Capitoli" })).toBeVisible();
});
