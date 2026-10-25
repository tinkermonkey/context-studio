import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { setupServer } from "msw/node";
import { serverSideList } from "@/test/serverSideList";
import { createClass } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import {
  ENTITY_PICKER_RESULT_LIMIT,
  useEntitiesById,
  useEntityTypeQuery,
} from "../useEntityTypeQuery";

const classRequests: URLSearchParams[] = [];
const taxonomyRequests: URLSearchParams[] = [];
// More classes than one default page, so a client-side filter of the first
// 100 would miss the ones searched for below.
const classes = Array.from({ length: 150 }, (_, i) =>
  createClass({ id: `c${i}`, title: `Class ${String(i).padStart(3, "0")}` }),
);

const server = setupServer(
  serverSideList("/api/classes", classes, classRequests),
  serverSideList(
    "/api/taxonomies",
    [
      { id: "t1", title: "Documentation Robotics" },
      { id: "t2", title: "Life Sciences" },
    ],
    taxonomyRequests,
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  classRequests.length = 0;
  taxonomyRequests.length = 0;
});
afterAll(() => server.close());

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useEntityTypeQuery", () => {
  it("searches the server with the trimmed text, picker limit and title sort", async () => {
    const { result } = renderHook(() => useEntityTypeQuery("Class", "  Class 14  "), { wrapper });

    await waitFor(() => expect(result.current.data?.items.length).toBeGreaterThan(0));
    const last = classRequests.at(-1)!;
    expect(last.get("q")).toBe("Class 14");
    expect(last.get("limit")).toBe(String(ENTITY_PICKER_RESULT_LIMIT));
    expect(last.get("sort_by")).toBe("title");
    // Matches beyond the first 100 rows are found because the server filters.
    expect(result.current.data?.items.map((c) => c.title)).toContain("Class 149");
  });

  it("sends no request while the text is empty", async () => {
    const { result } = renderHook(() => useEntityTypeQuery("Class", "   "), { wrapper });

    await new Promise((r) => setTimeout(r, 400));
    expect(classRequests).toHaveLength(0);
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useEntitiesById", () => {
  it("resolves selected classes by ids, including ones past the first page", async () => {
    const { result } = renderHook(() => useEntitiesById("Class", ["c149", "c3"]), { wrapper });

    await waitFor(() => expect(result.current.data?.items).toHaveLength(2));
    expect(classRequests.at(-1)!.getAll("ids")).toEqual(["c149", "c3"]);
    expect(result.current.data?.items.map((c) => c.id).sort()).toEqual(["c149", "c3"]);
  });

  it("fetches small curated sets in full for types without an ids filter", async () => {
    const { result } = renderHook(() => useEntitiesById("Taxonomy", ["t2"]), { wrapper });

    await waitFor(() => expect(result.current.data?.items).toHaveLength(2));
    const last = taxonomyRequests.at(-1)!;
    expect(last.has("ids")).toBe(false);
    expect(Number(last.get("limit"))).toBeGreaterThanOrEqual(500);
  });

  it("sends no request when nothing is selected", async () => {
    renderHook(() => useEntitiesById("Class", []), { wrapper });

    await new Promise((r) => setTimeout(r, 50));
    expect(classRequests).toHaveLength(0);
  });
});
