import { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { QueryClient, QueryClientProvider, type QueryKey } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { QUERY_KEYS } from "@/api/config";
import { proposalsService } from "@/api/services/proposals";
import {
  useApplyChangeProposal,
  useRejectChangeProposal,
  useRevertChangeProposal,
} from "../useProposalMutations";

// Keys the app's own queries use, as their hooks build them.
const PROPOSAL_QUERIES: QueryKey[] = [
  QUERY_KEYS.changeProposals({ taxonomy_id: "tax-1", status: "open" }),
  QUERY_KEYS.changeProposal("proposal-1"),
];
const ONTOLOGY_QUERIES: QueryKey[] = [
  QUERY_KEYS.taxonomies,
  QUERY_KEYS.taxonomy("tax-1"),
  QUERY_KEYS.schemes("tax-1"),
  QUERY_KEYS.classes({ concept_scheme_id: "scheme-1" }),
  QUERY_KEYS.class("class-1"),
  QUERY_KEYS.schemeCounts("tax-1"),
  QUERY_KEYS.individuals({ class_id: "class-1" }),
  QUERY_KEYS.individual("ind-1", "relationships"),
  QUERY_KEYS.relationships({ source_id: "ind-1" }),
  QUERY_KEYS.properties,
  QUERY_KEYS.graphView,
  QUERY_KEYS.changes({ limit: 10 }),
];
const UNRELATED_QUERIES: QueryKey[] = [QUERY_KEYS.pipelineRuns(), QUERY_KEYS.health];

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  for (const queryKey of [...PROPOSAL_QUERIES, ...ONTOLOGY_QUERIES, ...UNRELATED_QUERIES]) {
    queryClient.setQueryData(queryKey, { cached: true });
  }
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const invalidated = (queryKey: QueryKey) =>
    queryClient.getQueryState(queryKey)?.isInvalidated ?? false;
  return { wrapper, invalidated };
}

describe("change proposal mutation invalidation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("apply marks the proposals and every ontology query stale", async () => {
    vi.spyOn(proposalsService, "applyProposal").mockResolvedValue({} as never);
    const { wrapper, invalidated } = setup();
    const { result } = renderHook(() => useApplyChangeProposal(), { wrapper });

    result.current.mutate({ id: "proposal-1", data: { operation_ids: ["op-1"] } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    for (const queryKey of [...PROPOSAL_QUERIES, ...ONTOLOGY_QUERIES]) {
      expect(invalidated(queryKey), JSON.stringify(queryKey)).toBe(true);
    }
    for (const queryKey of UNRELATED_QUERIES) {
      expect(invalidated(queryKey), JSON.stringify(queryKey)).toBe(false);
    }
  });

  it("revert marks the proposals and every ontology query stale", async () => {
    vi.spyOn(proposalsService, "revertProposal").mockResolvedValue({} as never);
    const { wrapper, invalidated } = setup();
    const { result } = renderHook(() => useRevertChangeProposal(), { wrapper });

    result.current.mutate("proposal-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    for (const queryKey of [...PROPOSAL_QUERIES, ...ONTOLOGY_QUERIES]) {
      expect(invalidated(queryKey), JSON.stringify(queryKey)).toBe(true);
    }
  });

  it("reject marks only the proposals stale", async () => {
    vi.spyOn(proposalsService, "rejectProposal").mockResolvedValue({} as never);
    const { wrapper, invalidated } = setup();
    const { result } = renderHook(() => useRejectChangeProposal(), { wrapper });

    result.current.mutate({ id: "proposal-1", data: {} });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    for (const queryKey of PROPOSAL_QUERIES) {
      expect(invalidated(queryKey), JSON.stringify(queryKey)).toBe(true);
    }
    for (const queryKey of [...ONTOLOGY_QUERIES, ...UNRELATED_QUERIES]) {
      expect(invalidated(queryKey), JSON.stringify(queryKey)).toBe(false);
    }
  });
});
