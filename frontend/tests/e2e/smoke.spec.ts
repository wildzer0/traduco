import { expect, type Page, test } from "@playwright/test";

/** The app is mounted (effects and keyboard listeners registered) once the backend answered. */
async function openApp(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText("0.1.0");
}

test("empty three-column layout loads and talks to the backend", async ({ page }) => {
  await openApp(page);
  await expect(page.getByRole("navigation")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("region")).toBeVisible();
  await expect(page.getByRole("status")).toContainText("0.1.0");
});

test("theme can be switched to dark from settings", async ({ page }) => {
  await openApp(page);
  const buttons = page.getByRole("button", { name: /Impostazioni|Settings/ });
  await buttons.click();
  await page.getByRole("combobox").nth(1).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("sidebar toggles with Ctrl+B", async ({ page }) => {
  await openApp(page);
  await expect(page.getByRole("navigation")).toBeVisible();
  await page.keyboard.press("Control+b");
  await expect(page.getByRole("navigation")).toBeHidden();
});
