import { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { QUERY_KEYS } from "@/api/config";
import { proposalsService } from "@/api/services/proposals";
import {
  useApplyChangeProposal,
  useRejectChangeProposal,
  useRevertChangeProposal,
} from "../useProposalMutations";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper, invalidateSpy };
}

const ONTOLOGY_KEYS = [
  QUERY_KEYS.changeProposalsRoot,
  QUERY_KEYS.taxonomies,
  QUERY_KEYS.schemesRoot,
  QUERY_KEYS.classesRoot,
  QUERY_KEYS.individualsRoot,
  QUERY_KEYS.relationshipsRoot,
  QUERY_KEYS.properties,
  QUERY_KEYS.graph,
  QUERY_KEYS.changesRoot,
];

describe("change proposal mutation invalidation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("useApplyChangeProposal refreshes the proposals and the ontology", async () => {
    vi.spyOn(proposalsService, "applyProposal").mockResolvedValue({} as never);
    const { wrapper, invalidateSpy } = createWrapper();
    const { result } = renderHook(() => useApplyChangeProposal(), { wrapper });

    result.current.mutate({ id: "proposal-1", data: { operation_ids: ["op-1"] } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    for (const queryKey of ONTOLOGY_KEYS) {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey });
    }
  });

  it("useRevertChangeProposal refreshes the proposals and the ontology", async () => {
    vi.spyOn(proposalsService, "revertProposal").mockResolvedValue({} as never);
    const { wrapper, invalidateSpy } = createWrapper();
    const { result } = renderHook(() => useRevertChangeProposal(), { wrapper });

    result.current.mutate("proposal-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    for (const queryKey of ONTOLOGY_KEYS) {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey });
    }
  });

  it("useRejectChangeProposal refreshes only the proposals", async () => {
    vi.spyOn(proposalsService, "rejectProposal").mockResolvedValue({} as never);
    const { wrapper, invalidateSpy } = createWrapper();
    const { result } = renderHook(() => useRejectChangeProposal(), { wrapper });

    result.current.mutate({ id: "proposal-1", data: {} });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: QUERY_KEYS.changeProposalsRoot });
  });
});
