import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const PORT = 8765;
export const WORKSPACES = resolve(process.cwd(), ".e2e-workspaces");

export default defineConfig({
  testDir: "tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  workers: 1,
  use: { baseURL: `http://127.0.0.1:${PORT}`, locale: "it-IT" },
  webServer: {
    // The backend serves the already built frontend (run `pnpm build` first, `make e2e` does it).
    command: `uv run --project ../backend uvicorn app.main:app --app-dir ../backend --port ${PORT}`,
    env: {
      TRADUCO_FRONTEND_DIST: "../frontend/dist",
      TRADUCO_WORKSPACES_DIR: WORKSPACES,
      // tests start the fake model themselves (tests/e2e/helpers.ts) so they can switch it off
      TRADUCO_LLM_BASE_URL: "http://127.0.0.1:11500/v1",
      TRADUCO_LLM_MODEL: "fake-model",
    },
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
