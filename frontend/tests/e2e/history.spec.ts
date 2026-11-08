import { expect, test } from "@playwright/test";
import { projectWithSection, readFile, waitSaved } from "./helpers";

test("an earlier version of a section can be read and put back", async ({ page }) => {
  await projectWithSection(page, "Versioni");
  const editor = page.getByLabel("Testo della sezione");
  await editor.click();
  await page.keyboard.type("Testo scritto per sbaglio");
  await waitSaved(page);
  await page.getByRole("button", { name: "Versioni", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Versioni della sezione" });
  // the text before the first change is kept as a version
  await panel
    .getByRole("button")
    .filter({ hasText: /Scopo|title/ })
    .first()
    .click();
  await expect(panel.getByTestId("history-text")).toContainText("title: Scopo");
  await expect(panel.getByTestId("history-text")).not.toContainText("per sbaglio");
  await panel.getByRole("button", { name: "Ripristina questa versione" }).click();
  await expect
    .poll(() => readFile("versioni", "capitoli/01-cap/01-scopo.md"))
    .not.toContain("per sbaglio");
});
