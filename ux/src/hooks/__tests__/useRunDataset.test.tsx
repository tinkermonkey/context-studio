import type { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "@/test/test-utils";
import { ontologyService } from "@/api/services/ontology";
import { createDataset } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { useRunDataset } from "../useRunDataset";

const alpha = createDataset({ id: "ds-a", taxonomy_id: "tax-a", identifier: "alpha" });
const beta = createDataset({ id: "ds-b", taxonomy_id: "tax-a", identifier: "beta" });

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

function runDataset(datasets: ReturnType<typeof createDataset>[], taxonomyId?: string) {
  vi.spyOn(ontologyService, "listDatasets").mockResolvedValue(datasets);
  return renderHook(() => useRunDataset(taxonomyId), { wrapper });
}

describe("useRunDataset", () => {
  afterEach(() => vi.restoreAllMocks());

  it("leaves a taxonomy's only dataset to the server", async () => {
    const { result } = runDataset([alpha], "tax-a");
    await waitFor(() => expect(result.current.datasets).toEqual([alpha]));
    expect(result.current.required).toBe(false);
    expect(result.current.missing).toBe(false);
    expect(result.current.ready).toBe(true);
    expect(result.current.fields).toEqual({});
  });

  it("is not ready while the taxonomy's datasets are being read", async () => {
    let serve: (d: ReturnType<typeof createDataset>[]) => void = () => {};
    vi.spyOn(ontologyService, "listDatasets").mockImplementation(
      () => new Promise((resolve) => (serve = resolve)),
    );
    const { result } = renderHook(() => useRunDataset("tax-a"), { wrapper });
    // Not "nothing required": whether one must be named is not known yet.
    expect(result.current.loading).toBe(true);
    expect(result.current.ready).toBe(false);
    expect(result.current.required).toBe(false);

    act(() => serve([alpha, beta]));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.required).toBe(true);
    expect(result.current.ready).toBe(false);
    act(() => result.current.select("ds-a"));
    expect(result.current.ready).toBe(true);
  });

  it("reports a list that could not be read and is never ready", async () => {
    vi.spyOn(ontologyService, "listDatasets").mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useRunDataset("tax-a"), { wrapper });
    await waitFor(() => expect(result.current.loadError).toBe("boom"));
    expect(result.current.loading).toBe(false);
    expect(result.current.ready).toBe(false);
    expect(result.current.datasets).toEqual([]);
    expect(result.current.fields).toEqual({});
  });

  it("requires a choice among several datasets and sends the chosen one", async () => {
    const { result } = runDataset([alpha, beta], "tax-a");
    await waitFor(() => expect(result.current.required).toBe(true));
    expect(result.current.missing).toBe(true);
    expect(result.current.fields).toEqual({});

    act(() => result.current.select("ds-b"));
    expect(result.current.dataset).toEqual(beta);
    expect(result.current.missing).toBe(false);
    expect(result.current.fields).toEqual({ dataset_id: "ds-b" });
  });

  it("does not keep a choice that is not one of the taxonomy's datasets", async () => {
    const { result } = runDataset([alpha, beta], "tax-a");
    await waitFor(() => expect(result.current.required).toBe(true));
    act(() => result.current.select("ds-of-another-taxonomy"));
    expect(result.current.dataset).toBeUndefined();
    expect(result.current.missing).toBe(true);
  });

  it("offers nothing until a taxonomy is chosen", async () => {
    const { result } = runDataset([alpha, beta]);
    await waitFor(() => expect(ontologyService.listDatasets).toHaveBeenCalled());
    expect(result.current.datasets).toEqual([]);
    expect(result.current.required).toBe(false);
    expect(result.current.loading).toBe(false);
    expect(result.current.ready).toBe(true);
  });
});
