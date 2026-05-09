import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RootRoute, Router, RouterProvider } from "@tanstack/react-router";
import { render, RenderOptions } from "@testing-library/react";
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

interface AllProvidersProps {
  children: ReactNode;
  queryClient?: QueryClient;
  includeRouter?: boolean;
}

function AllProviders({ children, queryClient, includeRouter = false }: AllProvidersProps) {
  const client = queryClient || createTestQueryClient();

  const content = (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );

  if (!includeRouter) {
    return content;
  }

  const rootRoute = new RootRoute({
    component: () => content,
  });

  const router = new Router({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: ['/'] }),
  });

  return <RouterProvider router={router} />;
}

export function renderWithProviders(
  ui: ReactNode,
  {
    queryClient,
    includeRouter = false,
    ...renderOptions
  }: RenderOptions & { queryClient?: QueryClient; includeRouter?: boolean } = {},
) {
  const testQueryClient = queryClient || createTestQueryClient();
  return render(ui, {
    wrapper: ({ children }) => (
      <AllProviders queryClient={testQueryClient} includeRouter={includeRouter}>
        {children}
      </AllProviders>
    ),
    ...renderOptions,
  });
}

export * from "@testing-library/react";
export { renderWithProviders as render };
