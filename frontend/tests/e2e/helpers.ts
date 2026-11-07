import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { expect, type Page } from "@playwright/test";
import { WORKSPACES } from "../../playwright.config";

export const projectDir = (id: string) => join(WORKSPACES, id);
export const onDisk = (id: string, rel: string) => existsSync(join(projectDir(id), rel));
export const listDir = (id: string, rel: string) => readdirSync(join(projectDir(id), rel)).sort();

/** The app is mounted (effects and keyboard listeners registered) once the backend answered. */
export async function openApp(page: Page, path = "/") {
  await page.goto(path);
  await expect(page.getByRole("status")).toContainText("0.1.0");
}

export async function createProject(page: Page, nome: string) {
  await openApp(page);
  await page.getByRole("button", { name: "Crea progetto" }).click();
  await page.getByLabel("Nome del progetto").fill(nome);
  await page.getByRole("button", { name: "Crea", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Capitoli" })).toBeVisible();
}

/** Click "+ Chapter"/"+ Section", then name the new node in the inline input. */
export async function addNode(page: Page, button: "+ Capitolo" | "+ Sezione", title: string) {
  await page.getByRole("button", { name: button }).click();
  const input = page.getByRole("textbox", { name: "Rinomina" });
  await input.fill(title);
  await input.press("Enter");
  await expect(page.getByRole("button", { name: title, exact: true })).toBeVisible();
}
