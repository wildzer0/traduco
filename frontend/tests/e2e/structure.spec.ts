import { expect, test } from "@playwright/test";
import { addNode, createProject, listDir, onDisk } from "./helpers";

test("project, 2 chapters and 3 sections created from the UI produce the expected files", async ({
  page,
}) => {
  await createProject(page, "Struttura");
  await addNode(page, "+ Capitolo", "Introduzione");
  await addNode(page, "+ Sezione", "Scopo");
  await addNode(page, "+ Sezione", "Ambito");
  await addNode(page, "+ Capitolo", "Installazione");
  await addNode(page, "+ Sezione", "Requisiti");

  expect(listDir("struttura", "capitoli")).toEqual(["01-introduzione", "02-installazione"]);
  expect(listDir("struttura", "capitoli/01-introduzione")).toEqual([
    "01-scopo.md",
    "02-ambito.md",
    "_capitolo.yaml",
  ]);
  expect(listDir("struttura", "capitoli/02-installazione")).toEqual([
    "01-requisiti.md",
    "_capitolo.yaml",
  ]);
  expect(onDisk("struttura", "progetto.yaml")).toBe(true);
});

test("dragging a section above its sibling renumbers the files", async ({ page }) => {
  await createProject(page, "Riordino");
  await addNode(page, "+ Capitolo", "Cap");
  await addNode(page, "+ Sezione", "Uno");
  await addNode(page, "+ Sezione", "Due");

  const handle = (title: string) =>
    page
      .locator("li", { has: page.getByRole("button", { name: title, exact: true }) })
      .getByRole("button", { name: "Trascina per spostare" });
  const from = await handle("Due").boundingBox();
  const to = await page.getByRole("button", { name: "Uno", exact: true }).boundingBox();
  if (!from || !to) throw new Error("rows not visible");

  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + from.width / 2, from.y - 4, { steps: 4 });
  await page.mouse.move(to.x + 20, to.y + 2, { steps: 12 });
  await page.mouse.up();

  await expect
    .poll(() => listDir("riordino", "capitoli/01-cap"))
    .toEqual(["01-due.md", "02-uno.md", "_capitolo.yaml"]);
  const buttons = page.locator("li button", { hasText: /^(Uno|Due)$/ });
  await expect(buttons.first()).toHaveText("Due");
});

test("deleting a section moves it to the trash folder", async ({ page }) => {
  await createProject(page, "Cestino");
  await addNode(page, "+ Capitolo", "Cap");
  await addNode(page, "+ Sezione", "Via");
  await page.getByRole("button", { name: "Via", exact: true }).click({ button: "right" });
  await page.getByRole("menuitem", { name: "Elimina" }).click();
  await expect(page.getByRole("button", { name: "Via", exact: true })).toBeHidden();
  expect(onDisk("cestino", "capitoli/01-cap/01-via.md")).toBe(false);
  expect(listDir("cestino", ".traduco/cestino")).toHaveLength(1);
});
