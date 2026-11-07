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

import { readFileSync, writeFileSync } from "node:fs";

export const readFile = (id: string, rel: string) =>
  readFileSync(join(projectDir(id), rel), "utf8");
export const writeProjectFile = (id: string, rel: string, text: string) =>
  writeFileSync(join(projectDir(id), rel), text, "utf8");

/** Project with one chapter and one section, section open in the editor. */
export async function projectWithSection(page: Page, nome: string, section = "Scopo") {
  await createProject(page, nome);
  await addNode(page, "+ Capitolo", "Cap");
  await addNode(page, "+ Sezione", section);
  await page.getByRole("button", { name: section, exact: true }).click();
  await expect(page.getByLabel("Testo della sezione")).toBeVisible();
}

export async function waitSaved(page: Page) {
  await expect(page.getByTestId("save-status")).toContainText("Salvato");
}

export async function showSource(page: Page) {
  await page.getByRole("button", { name: "Mostra il sorgente" }).click();
  await expect(page.getByText("Anteprima · sorgente")).toBeVisible();
}

// --- fake OpenAI-compatible model server (tools/fake-llm) ---------------------------------------
import { type ChildProcess, spawn } from "node:child_process";
import { resolve } from "node:path";

export const FAKE_LLM_PORT = 11500;

/** Start the fake model on the port the e2e backend is configured to use; resolves when it answers. */
export async function startFakeLlm(env: Record<string, string> = {}): Promise<ChildProcess> {
  const backend = resolve(process.cwd(), "../backend");
  const python =
    process.platform === "win32"
      ? join(backend, ".venv", "Scripts", "python.exe")
      : join(backend, ".venv", "bin", "python");
  const child = spawn(python, ["-m", "fake_llm"], {
    cwd: resolve(process.cwd(), "../tools/fake-llm"),
    env: { ...process.env, FAKE_LLM_PORT: String(FAKE_LLM_PORT), ...env },
    stdio: "ignore",
  });
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${FAKE_LLM_PORT}/health`);
      if (r.ok) return child;
    } catch {
      // not listening yet
    }
    await new Promise((res) => setTimeout(res, 100));
  }
  child.kill();
  throw new Error("fake-llm did not start");
}

export async function stopFakeLlm(child: ChildProcess) {
  child.kill("SIGTERM");
  await new Promise((res) => (child.exitCode !== null ? res(null) : child.once("exit", res)));
}
