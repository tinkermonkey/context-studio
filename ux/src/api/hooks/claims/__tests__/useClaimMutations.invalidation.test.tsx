import { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { QUERY_KEYS } from "@/api/config";
import { claimsService } from "@/api/services/claims";
import { claimOne } from "@/test/claimFixtures";
import { useClearClaimVerdict, useSetClaimVerdict } from "../useClaimMutations";

const LIST = QUERY_KEYS.claims("tax-1", { has_verdict: false, limit: 50, offset: 0 });
const OTHER = QUERY_KEYS.changeProposals();

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  for (const queryKey of [LIST, QUERY_KEYS.claim("claim-1"), OTHER]) {
    queryClient.setQueryData(queryKey, { cached: true });
  }
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
}

const judged = {
  ...claimOne,
  verdict: {
    validity: "real_defect" as const,
    rationale: "",
    adjudicated_by: "user",
    adjudicated_at: "2026-11-09T12:00:00Z",
  },
};

describe("claim verdict mutations", () => {
  afterEach(() => vi.restoreAllMocks());

  it("saving a verdict shows the returned claim and marks the claim lists stale", async () => {
    vi.spyOn(claimsService, "setVerdict").mockResolvedValue(judged);
    const { queryClient, wrapper } = setup();
    const { result } = renderHook(() => useSetClaimVerdict(), { wrapper });

    result.current.mutate({ id: "claim-1", data: { validity: "real_defect", rationale: "" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(queryClient.getQueryData(QUERY_KEYS.claim("claim-1"))).toEqual(judged);
    expect(queryClient.getQueryState(LIST)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(OTHER)?.isInvalidated).toBe(false);
  });

  it("clearing a verdict does the same", async () => {
    vi.spyOn(claimsService, "clearVerdict").mockResolvedValue(claimOne);
    const { queryClient, wrapper } = setup();
    const { result } = renderHook(() => useClearClaimVerdict(), { wrapper });

    result.current.mutate("claim-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(queryClient.getQueryData(QUERY_KEYS.claim("claim-1"))).toEqual(claimOne);
    expect(queryClient.getQueryState(LIST)?.isInvalidated).toBe(true);
  });
});
