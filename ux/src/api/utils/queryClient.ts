import { QueryClient, MutationCache } from "@tanstack/react-query";

let toastFn: ((type: "error" | "success" | "info", message: string) => void) | null = null;

export function setGlobalErrorHandler(
  toast: (type: "error" | "success" | "info", message: string) => void,
) {
  toastFn = toast;
}

/**
 * Global safety-net toast for mutation errors. Mutations whose calling surface
 * shows its own error toast (with extra context or a bulk summary) opt out via
 * `meta: { skipGlobalErrorToast: true }` so the user never sees two toasts.
 */
export function handleMutationError(
  error: unknown,
  _variables: unknown,
  _context: unknown,
  mutation?: { meta?: Record<string, unknown> },
): void {
  if (mutation?.meta?.skipGlobalErrorToast) return;
  if (toastFn) {
    const message = error instanceof Error ? error.message : "An error occurred";
    toastFn("error", message);
  }
}

export const queryClient = new QueryClient({
  mutationCache: new MutationCache({ onError: handleMutationError }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
