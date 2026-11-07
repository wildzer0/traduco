import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { Layout } from "./Layout";

const rootRoute = createRootRoute({ component: Layout });
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/" });

export const router = createRouter({ routeTree: rootRoute.addChildren([indexRoute]) });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
