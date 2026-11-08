import { expect, type Page, test } from "@playwright/test";
import { projectWithSection, waitSaved } from "./helpers";

const width = (page: Page, selector: string) =>
  page.evaluate((sel) => document.querySelector(sel)?.getBoundingClientRect().width ?? 0, selector);

async function drag(page: Page, name: string, dx: number) {
  const handle = page.getByRole("separator", { name });
  const box = await handle.boundingBox();
  if (!box) throw new Error(`no handle: ${name}`);
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx / 2, y, { steps: 4 });
  await page.mouse.move(x + dx, y, { steps: 4 });
  await page.mouse.up();
}

test("the sidebar and the preview can be resized, and the sizes are remembered", async ({
  page,
}) => {
  await projectWithSection(page, "Layout prova");
  const nav = 'nav[aria-label="Capitoli"]';
  const before = await width(page, nav);
  await drag(page, "Larghezza della barra laterale", 120);
  const wider = await width(page, nav);
  expect(wider).toBeGreaterThan(before + 90);

  const editor = 'main[aria-label="Editor"]';
  const editorBefore = await width(page, editor);
  await drag(page, "Larghezza di editor e anteprima", -150);
  expect(await width(page, editor)).toBeLessThan(editorBefore - 100);

  await page.reload();
  await expect(page.getByLabel("Testo della sezione")).toBeVisible();
  expect(Math.abs((await width(page, nav)) - wider)).toBeLessThan(3);
  // double click puts the sidebar back
  await page.getByRole("separator", { name: "Larghezza della barra laterale" }).dblclick();
  expect(Math.abs((await width(page, nav)) - before)).toBeLessThan(3);

  // from the keyboard
  const handle = page.getByRole("separator", { name: "Larghezza della barra laterale" });
  await handle.focus();
  await page.keyboard.press("ArrowRight");
  expect(await width(page, nav)).toBeGreaterThan(before + 10);
});

test("a long panel keeps its title and close button in view", async ({ page }) => {
  await projectWithSection(page, "Pannello lungo");
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  const lines = Array.from(
    { length: 70 },
    (_, i) =>
      `FOO-REQ-${String(i + 1).padStart(5, "0")} Il sistema deve fare la cosa numero ${i + 1}.`,
  );
  await page.keyboard.insertText(`${lines.join("\n\n")}\n`);
  await waitSaved(page);

  await page.getByRole("button", { name: "Requisiti", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Requisiti e riferimenti" });
  await expect(panel).toContainText("FOO-REQ-00070");
  await panel.getByText("FOO-REQ-00070").first().scrollIntoViewIfNeeded();
  const close = panel.getByRole("button", { name: "Chiudi" });
  const box = await close.boundingBox();
  expect(box && box.y >= 0 && box.y < 80).toBe(true); // still at the top of the window
  await close.click();
  await expect(panel).toHaveCount(0);
});

test("a panel can be made wider by dragging its edge", async ({ page }) => {
  await projectWithSection(page, "Pannello largo");
  await page.getByRole("button", { name: "Requisiti", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Requisiti e riferimenti" });
  const before = (await panel.boundingBox())?.width ?? 0;
  await drag(page, "Larghezza del pannello", -200);
  expect((await panel.boundingBox())?.width ?? 0).toBeGreaterThan(before + 150);
});

test("from a project one can go back to the list of projects", async ({ page }) => {
  await projectWithSection(page, "Torna indietro");
  await page.getByRole("button", { name: "Tutti i progetti" }).click();
  await expect(page.getByRole("button", { name: "Crea progetto" })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe("/");
});
