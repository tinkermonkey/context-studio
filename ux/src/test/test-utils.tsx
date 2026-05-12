import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, RenderOptions } from "@testing-library/react";
import { RouterProvider, createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";
import { ToastProvider } from "@/components/ui/Toast";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

let testRouterInstance: ReturnType<typeof createTestRouter> | null = null;
let cachedTestComponent: ReactNode = null;

function createTestRouter(testComponent: ReactNode, initialPath?: string) {
  cachedTestComponent = testComponent;

  const rootRoute = createRootRoute({
    component: () => <Outlet />,
  });

  const appRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "app",
    component: () => <Outlet />,
  });

  const referenceRoute = createRoute({
    getParentRoute: () => appRoute,
    path: "reference",
    component: () => <Outlet />,
  });

  const workflowsRoute = createRoute({
    getParentRoute: () => referenceRoute,
    path: "workflows",
    validateSearch: (search: Record<string, unknown>) => ({
      selected: typeof search.selected === "string" ? search.selected : undefined,
    }),
    component: () => cachedTestComponent,
  });

  const sourcesRoute = createRoute({
    getParentRoute: () => referenceRoute,
    path: "sources",
    validateSearch: (search: Record<string, unknown>) => ({
      selected: typeof search.selected === "string" ? search.selected : undefined,
    }),
    component: () => cachedTestComponent,
  });

  const routeTree = rootRoute.addChildren([
    appRoute.addChildren([
      referenceRoute.addChildren([workflowsRoute, sourcesRoute]),
    ]),
  ]);

  const memoryHistory = createMemoryHistory({
    initialEntries: [initialPath || "/app/reference/workflows"],
  });

  return createRouter({
    routeTree,
    history: memoryHistory,
  });
}

interface AllProvidersProps {
  children: ReactNode;
  queryClient?: QueryClient;
  initialPath?: string;
}

function AllProviders({ children, queryClient, initialPath }: AllProvidersProps) {
  const client = queryClient || createTestQueryClient();
  const router = createTestRouter(children, initialPath);

  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  );
}

interface RenderWithProvidersOptions extends RenderOptions {
  queryClient?: QueryClient;
  initialPath?: string;
}

export function renderWithProviders(
  ui: ReactNode,
  { queryClient, initialPath, ...renderOptions }: RenderWithProvidersOptions = {},
) {
  const testQueryClient = queryClient || createTestQueryClient();

  // Auto-detect initialPath based on component type if not provided
  let resolvedInitialPath = initialPath;
  if (!resolvedInitialPath && typeof ui === "object" && ui !== null && "type" in ui) {
    const componentName = (ui.type as any)?.name || "";
    if (componentName.includes("Sources")) {
      resolvedInitialPath = "/app/reference/sources";
    } else if (componentName.includes("Workflow")) {
      resolvedInitialPath = "/app/reference/workflows";
    }
  }

  return render(ui, {
    wrapper: ({ children }) => (
      <AllProviders queryClient={testQueryClient} initialPath={resolvedInitialPath}>
        {children}
      </AllProviders>
    ),
    ...renderOptions,
  });
}

export * from "@testing-library/react";
export { renderWithProviders as render };
