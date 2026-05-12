import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryHistory, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { ToastProvider } from "@/components/ui/Toast";

function createTestRouter() {
  const rootRoute = createRootRoute({
    component: (props) => props.children,
  });

  const appRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "app",
    component: (props) => props.children,
  });

  const referenceRoute = createRoute({
    getParentRoute: () => appRoute,
    path: "reference",
    component: (props) => props.children,
  });

  const workflowsRoute = createRoute({
    getParentRoute: () => referenceRoute,
    path: "workflows",
    validateSearch: (search: Record<string, unknown>) => ({
      selected: typeof search.selected === "string" ? search.selected : undefined,
    }),
  });

  const sourcesRoute = createRoute({
    getParentRoute: () => referenceRoute,
    path: "sources",
  });

  const routeTree = rootRoute.addChildren([
    appRoute.addChildren([
      referenceRoute.addChildren([workflowsRoute, sourcesRoute]),
    ]),
  ]);

  const memoryHistory = createMemoryHistory({
    initialEntries: ["/app/reference/workflows"],
  });

  return createRouter({
    routeTree,
    history: memoryHistory,
    scrollRestorationMaxAge: 0,
  });
}

export function TestApp() {
  const router = createTestRouter();
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return (
    <RouterProvider router={router}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <div>Test App</div>
        </ToastProvider>
      </QueryClientProvider>
    </RouterProvider>
  );
}

// Test it
render(<TestApp />);
console.log(screen.debug());
