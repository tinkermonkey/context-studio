import React from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter } from "@tanstack/react-router";

export function makeTestRouter() {
  // Minimal router for tests that need RouterProvider. Keep routeTree small to avoid app boot.
  const router = createRouter({
    routeTree: { path: "/", children: [] } as any,

    defaultPreload: "intent" as any,
  });
  // register for types - moved to top for test-only setup

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

  { queryClient, router } = {} as any,
) {
  const client = queryClient ?? makeTestQueryClient();
  const content = (
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>
  );
  if (router)
    return render(
      React.createElement(RouterProvider as any, { router }, content),
    );
  return render(content);
}

export * from "@testing-library/react";
