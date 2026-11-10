import type { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "@/test/test-utils";
import { ontologyService } from "@/api/services/ontology";
import { createDataset } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { useDatasetScope } from "../useDatasetScope";

const mockNavigate = vi.hoisted(() => vi.fn());
let mockSearch: { dataset?: string } = {};
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => mockNavigate, useSearch: () => mockSearch };
});

const alphaDefault = createDataset({ id: "ds-a1", taxonomy_id: "tax-a", identifier: "default" });
const alphaSecond = createDataset({ id: "ds-a2", taxonomy_id: "tax-a", identifier: "second" });
const betaDefault = createDataset({ id: "ds-b1", taxonomy_id: "tax-b", identifier: "default" });

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

function scope(datasets: ReturnType<typeof createDataset>[], taxonomyId?: string) {
  vi.spyOn(ontologyService, "listDatasets").mockResolvedValue(datasets);
  return renderHook(() => useDatasetScope(taxonomyId), { wrapper });
}

describe("useDatasetScope", () => {
  beforeEach(() => {
    mockSearch = {};
  });
  afterEach(() => {
    vi.restoreAllMocks();
    mockNavigate.mockClear();
  });

  it("hides the selector when every taxonomy has one dataset", async () => {
    const { result } = scope([alphaDefault, betaDefault]);
    await waitFor(() => expect(result.current.datasets).toHaveLength(2));
    expect(result.current.showSelector).toBe(false);
    expect(result.current.selectedDatasetId).toBeUndefined();
  });

  it("shows the selector once a taxonomy has two datasets", async () => {
    const { result } = scope([alphaDefault, alphaSecond, betaDefault]);
    await waitFor(() => expect(result.current.showSelector).toBe(true));
  });

  it("scoped to a taxonomy, counts only that taxonomy's datasets", async () => {
    const { result } = scope([alphaDefault, alphaSecond, betaDefault], "tax-b");
    await waitFor(() => expect(result.current.datasets).toEqual([betaDefault]));
    expect(result.current.showSelector).toBe(false);
  });

  it("selects the dataset the URL names", async () => {
    mockSearch = { dataset: "ds-a2" };
    const { result } = scope([alphaDefault, alphaSecond]);
    // Before the datasets load, the URL's value already scopes the first requests.
    expect(result.current.selectedDatasetId).toBe("ds-a2");
    await waitFor(() => expect(result.current.selectedDataset).toEqual(alphaSecond));
    expect(result.current.selectedDatasetId).toBe("ds-a2");
  });

  it("ignores a dataset of another taxonomy or one that does not exist", async () => {
    mockSearch = { dataset: "ds-a2" };
    const other = scope([alphaDefault, alphaSecond, betaDefault], "tax-b");
    await waitFor(() => expect(other.result.current.datasets).toHaveLength(1));
    expect(other.result.current.selectedDatasetId).toBeUndefined();

    mockSearch = { dataset: "ds-gone" };
    const missing = scope([alphaDefault, alphaSecond]);
    await waitFor(() => expect(missing.result.current.datasets).toHaveLength(2));
    expect(missing.result.current.selectedDatasetId).toBeUndefined();
  });

  it("scopes nothing when the URL names a taxonomy's only dataset", async () => {
    // A link from elsewhere left it there; no selector would let the user clear it.
    mockSearch = { dataset: "ds-b1" };
    const { result } = scope([alphaDefault, alphaSecond, betaDefault]);
    await waitFor(() => expect(result.current.datasets).toHaveLength(3));
    expect(result.current.selectedDataset).toBeUndefined();
    expect(result.current.selectedDatasetId).toBeUndefined();
  });

  it("sets and clears the dataset in the URL, keeping the other parameters", async () => {
    const { result } = scope([alphaDefault, alphaSecond]);
    result.current.setDataset("ds-a1");
    result.current.setDataset(undefined);

    const [set, clear] = mockNavigate.mock.calls.map((call) => call[0]);
    expect(set).toMatchObject({ to: ".", replace: true });
    expect(set.search({ focus: "n1" })).toEqual({ focus: "n1", dataset: "ds-a1" });
    // An explicit undefined clears it (the /app route otherwise keeps it).
    const cleared = clear.search({ dataset: "ds-a1" });
    expect(Object.keys(cleared)).toEqual(["dataset"]);
    expect(cleared.dataset).toBeUndefined();
  });
});
