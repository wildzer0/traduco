import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  type RouterHistory,
} from "@tanstack/react-router";
import { ProjectsPage } from "../features/projects/ProjectsPage";
import { AppShell } from "./AppShell";
import { Workspace } from "./Workspace";

const rootRoute = createRootRoute({ component: AppShell });
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ProjectsPage,
  validateSearch: (search: Record<string, unknown>): { c?: string } =>
    typeof search.c === "string" && search.c ? { c: search.c } : {},
});
const projectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/p/$projectId",
  component: Workspace,
  validateSearch: (search: Record<string, unknown>): { s?: string } =>
    typeof search.s === "string" && search.s ? { s: search.s } : {},
});

const routeTree = rootRoute.addChildren([indexRoute, projectRoute]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history });
}

export const router = createAppRouter();
export const memoryHistory = (path: string) => createMemoryHistory({ initialEntries: [path] });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
