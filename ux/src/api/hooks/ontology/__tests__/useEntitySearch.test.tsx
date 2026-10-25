import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { setupServer } from "msw/node";
import { serverSideList } from "@/test/serverSideList";
import { createClass, createIndividual } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { useClassSearch, useIndividualSearch } from "../useEntitySearch";
import { useClassesByIds } from "../useClasses";
import { useEntityCounts } from "../useEntityCounts";

const classRequests: URLSearchParams[] = [];
const individualRequests: URLSearchParams[] = [];
const classes = [
  createClass({ id: "c1", title: "Neuron" }),
  createClass({ id: "c2", title: "Glia" }),
];

const server = setupServer(
  serverSideList("/api/classes", classes, classRequests),
  serverSideList(
    "/api/individuals",
    [createIndividual({ id: "i1", title: "Ada" })],
    individualRequests,
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  classRequests.length = 0;
  individualRequests.length = 0;
});
afterAll(() => server.close());

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useClassSearch", () => {
  it("sends the trimmed text as q with the picker limit, sorted by title", async () => {
    const { result } = renderHook(() => useClassSearch("  neu  "), { wrapper });

    await waitFor(() => expect(result.current.data?.items).toHaveLength(1));
    const last = classRequests.at(-1)!;
    expect(last.get("q")).toBe("neu");
    expect(last.get("limit")).toBe("20");
    expect(last.get("sort_by")).toBe("title");
    expect(result.current.data?.items[0].title).toBe("Neuron");
  });

  it("omits q for empty text (lists the first classes)", async () => {
    const { result } = renderHook(() => useClassSearch(""), { wrapper });

    await waitFor(() => expect(result.current.data?.items).toHaveLength(2));
    expect(classRequests.at(-1)!.has("q")).toBe(false);
  });

  it("debounces typing into one request for the final text", async () => {
    const { rerender } = renderHook(({ text }) => useClassSearch(text), {
      wrapper,
      initialProps: { text: "g" },
    });
    rerender({ text: "gl" });
    rerender({ text: "gli" });

    await waitFor(() => expect(classRequests.map((r) => r.get("q"))).toContain("gli"));
    // The intermediate keystroke never reached the server.
    expect(classRequests.map((r) => r.get("q"))).not.toContain("gl");
  });

  it("does not request while disabled", async () => {
    renderHook(() => useClassSearch("neu", undefined, { enabled: false }), { wrapper });
    await new Promise((r) => setTimeout(r, 350));
    expect(classRequests).toHaveLength(0);
  });
});

describe("useIndividualSearch", () => {
  it("searches individuals server-side with q", async () => {
    const { result } = renderHook(() => useIndividualSearch("ad"), { wrapper });

    await waitFor(() => expect(result.current.data?.items).toHaveLength(1));
    expect(individualRequests.at(-1)!.get("q")).toBe("ad");
  });
});

describe("useClassesByIds", () => {
  it("requests exactly the de-duplicated, sorted ids", async () => {
    const { result } = renderHook(() => useClassesByIds(["c2", "c1", "c2", null]), { wrapper });

    await waitFor(() => expect(result.current.data?.items).toHaveLength(2));
    const last = classRequests.at(-1)!;
    expect(last.getAll("ids")).toEqual(["c1", "c2"]);
    expect(last.get("limit")).toBe("2");
  });

  it("skips the request when there are no ids", async () => {
    renderHook(() => useClassesByIds([undefined]), { wrapper });
    await new Promise((r) => setTimeout(r, 50));
    expect(classRequests).toHaveLength(0);
  });
});

describe("useEntityCounts", () => {
  it("reads totals from limit=1 requests and skips individuals when schemaOnly", async () => {
    server.use(
      serverSideList("/api/taxonomies", []),
      serverSideList("/api/schemes", []),
      serverSideList("/api/properties", []),
      serverSideList("/api/relationships", []),
    );
    const { result } = renderHook(() => useEntityCounts({ schemaOnly: true }), { wrapper });

    await waitFor(() => expect(result.current.classes).toBe(2));
    expect(classRequests.every((r) => r.get("limit") === "1")).toBe(true);
    expect(individualRequests).toHaveLength(0);
    expect(result.current.individuals).toBeUndefined();
  });
});
