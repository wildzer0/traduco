import { expect, test } from "@playwright/test";
import { createProject, openApp } from "./helpers";

test("welcome page loads and talks to the backend", async ({ page }) => {
  await openApp(page);
  await expect(page.getByRole("heading", { name: "Benvenuto in Traduco" })).toBeVisible();
  await expect(page.getByRole("contentinfo").getByRole("status")).toContainText("0.1.0");
});

test("theme can be switched to dark from settings", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: /Impostazioni|Settings/ }).click();
  await page.getByRole("combobox").nth(1).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("sidebar toggles with Ctrl+B inside a project", async ({ page }) => {
  await createProject(page, "Smoke");
  await page.keyboard.press("Control+b");
  await expect(page.getByRole("navigation", { name: "Capitoli" })).toBeHidden();
  await page.keyboard.press("Control+b");
  await expect(page.getByRole("navigation", { name: "Capitoli" })).toBeVisible();
});
