import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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
}

function AllProviders({ children, queryClient }: AllProvidersProps) {
  const client = queryClient || createTestQueryClient();

  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

export function renderWithProviders(
  ui: ReactNode,
  {
    queryClient,
    ...renderOptions
  }: RenderOptions & { queryClient?: QueryClient } = {},
) {
  const testQueryClient = queryClient || createTestQueryClient();
  return render(ui, {
    wrapper: ({ children }) => (
      <AllProviders queryClient={testQueryClient}>
        {children}
      </AllProviders>
    ),
    ...renderOptions,
  });
}

export * from "@testing-library/react";
export { renderWithProviders as render };
