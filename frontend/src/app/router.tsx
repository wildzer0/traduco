import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  type RouterHistory,
} from "@tanstack/react-router";
import { AppShell } from "./AppShell";
import { WelcomePage } from "./WelcomePage";
import { Workspace } from "./Workspace";

const rootRoute = createRootRoute({ component: AppShell });
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: WelcomePage,
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
