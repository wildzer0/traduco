import { expect, test } from "@playwright/test";
import { onDisk, projectWithSection, readFile } from "./helpers";

test("a CSV attached from the toolbar is shown as a table and kept in allegati/", async ({
  page,
}) => {
  await projectWithSection(page, "Allegati");
  await page.getByLabel("Testo della sezione").click();
  await page.getByTestId("attachment-input").setInputFiles({
    name: "Dati.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("Nome;Portata\nPompa 1;120\nPompa 2;80\n"),
  });
  await expect.poll(() => onDisk("allegati", "allegati/dati.csv")).toBe(true);
  const preview = page.getByRole("region", { name: "Anteprima tradotta" });
  await expect(preview.locator(".csv-table td", { hasText: "Pompa 2" })).toBeVisible();
  await expect(preview.locator(".csv-table th", { hasText: "Portata" })).toBeVisible();
  await expect
    .poll(() => readFile("allegati", "capitoli/01-cap/01-scopo.md"))
    .toContain("![dati](allegati/dati.csv)");
});
