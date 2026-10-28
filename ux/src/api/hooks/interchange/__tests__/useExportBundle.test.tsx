import { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { interchangeService } from "@/api/services/interchange";
import { handleMutationError, setGlobalErrorHandler } from "@/api/utils/queryClient";
import { useExportBundle } from "../useExportBundle";

function setup() {
  const queryClient = new QueryClient({
    mutationCache: new MutationCache({ onError: handleMutationError }),
    defaultOptions: { mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return renderHook(() => useExportBundle(), { wrapper });
}

describe("useExportBundle", () => {
  afterEach(() => vi.restoreAllMocks());

  it("leaves the error toast to the caller, not the global safety net", async () => {
    const globalToast = vi.fn();
    setGlobalErrorHandler(globalToast);
    vi.spyOn(interchangeService, "exportBundle").mockRejectedValue(new Error("refused"));
    const { result } = setup();

    result.current.mutate("tax-1");

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("refused");
    expect(globalToast).not.toHaveBeenCalled();
  });
});
