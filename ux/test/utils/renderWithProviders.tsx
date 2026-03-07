import React from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter } from "@tanstack/react-router";

export function makeTestRouter() {
  // Minimal router for tests that need RouterProvider. Keep routeTree small to avoid app boot.
  const router = createRouter({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    routeTree: { path: "/", children: [] } as any,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    defaultPreload: "intent" as any,
  });
  // register for types - moved to top for test-only setup
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return router as any;
}

export function makeTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  { queryClient, router } = {} as any,
) {
  const client = queryClient ?? makeTestQueryClient();
  const content = (
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>
  );
  if (router)
    return render(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      React.createElement(RouterProvider as any, { router }, content),
    );
  return render(content);
}

export * from "@testing-library/react";
