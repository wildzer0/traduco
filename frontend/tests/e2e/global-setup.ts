import { rmSync } from "node:fs";
import { resolve } from "node:path";

export default function globalSetup() {
  // Fresh workspaces folder for every run; the server creates it on demand.
  rmSync(resolve(process.cwd(), ".e2e-workspaces"), { recursive: true, force: true });
  rmSync(resolve(process.cwd(), ".e2e-runtime"), { recursive: true, force: true });
}
