import { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import { ApiError } from "@/api/client/interceptors";
import { useDeleteClass } from "../useClasses";
import { useDeleteProperty } from "../useProperties";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper, invalidateSpy };
}

describe("delete mutation error-path invalidation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("useDeleteClass invalidates the class and scheme lists when the delete is rejected", async () => {
    vi.spyOn(ontologyService, "deleteClass").mockRejectedValue(
      new ApiError("Cannot delete: it has 2 subclass(es)", 409, "Cannot delete: it has 2 subclass(es)"),
    );
    const { wrapper, invalidateSpy } = createWrapper();

    const { result } = renderHook(() => useDeleteClass(), { wrapper });

    result.current.mutate("class-001");

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: QUERY_KEYS.classesRoot });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: QUERY_KEYS.schemesRoot });
  });

  it("useDeleteProperty invalidates the property list when the delete is rejected", async () => {
    vi.spyOn(ontologyService, "deleteProperty").mockRejectedValue(
      new ApiError(
        "Cannot delete: still referenced by relationships",
        409,
        "Cannot delete: still referenced by relationships",
      ),
    );
    const { wrapper, invalidateSpy } = createWrapper();

    const { result } = renderHook(() => useDeleteProperty(), { wrapper });

    result.current.mutate("prop-001");

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: QUERY_KEYS.properties });
  });
});
