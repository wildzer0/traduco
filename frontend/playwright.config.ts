import { defineConfig } from "@playwright/test";

const PORT = 8765;

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  webServer: {
    // The backend serves the already built frontend (run `pnpm build` first, `make e2e` does it).
    command: `uv run --project ../backend uvicorn app.main:app --app-dir ../backend --port ${PORT}`,
    env: { TRADUCO_FRONTEND_DIST: "../frontend/dist" },
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
