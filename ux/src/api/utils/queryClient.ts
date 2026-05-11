import { QueryClient } from "@tanstack/react-query";

let toastFn: ((type: "error" | "success" | "info", message: string) => void) | null = null;

export function setGlobalErrorHandler(
  toast: (type: "error" | "success" | "info", message: string) => void,
) {
  toastFn = toast;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      onError: (error: unknown) => {
        if (toastFn) {
          const message = error instanceof Error ? error.message : "An error occurred";
          toastFn("error", message);
        }
      },
    },
  },
});
