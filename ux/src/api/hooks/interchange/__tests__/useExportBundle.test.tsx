import { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { interchangeService } from "@/api/services/interchange";
import { handleMutationError, setGlobalErrorHandler } from "@/api/utils/queryClient";
import { ToastProvider, useToasts } from "@/components/ui/Toast";
import { useExportBundle } from "../useExportBundle";

function setup() {
  const queryClient = new QueryClient({
    mutationCache: new MutationCache({ onError: handleMutationError }),
    defaultOptions: { mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
  return renderHook(() => ({ exportBundle: useExportBundle(), toasts: useToasts().toasts }), {
    wrapper,
  });
}

describe("useExportBundle", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows one titled error toast of its own instead of the global one", async () => {
    const globalToast = vi.fn();
    setGlobalErrorHandler(globalToast);
    vi.spyOn(interchangeService, "exportBundle").mockRejectedValue(new Error("refused"));
    const { result } = setup();

    result.current.exportBundle.mutate("tax-1");

    await waitFor(() => expect(result.current.exportBundle.isError).toBe(true));
    expect(result.current.toasts).toMatchObject([
      { type: "error", title: "Bundle export failed", sub: "refused" },
    ]);
    expect(globalToast).not.toHaveBeenCalled();
  });
});
