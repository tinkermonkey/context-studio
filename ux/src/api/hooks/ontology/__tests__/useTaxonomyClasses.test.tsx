import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { createClass } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { useTaxonomyClasses } from "../useClasses";

const requests: string[] = [];
const classes = [
  createClass({ id: "c1", title: "Actor", concept_scheme_id: "s-business", derived: true }),
  createClass({ id: "c2", title: "Service", concept_scheme_id: "s-application" }),
];

const server = setupServer(
  http.get("*/api/taxonomies/:id/classes", ({ request, params }) => {
    requests.push(new URL(request.url).pathname);
    return params.id === "missing"
      ? HttpResponse.json({ detail: "Taxonomy not found" }, { status: 404 })
      : HttpResponse.json(classes);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  requests.length = 0;
});
afterAll(() => server.close());

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useTaxonomyClasses", () => {
  it("loads every class of the taxonomy in one request", async () => {
    const { result } = renderHook(() => useTaxonomyClasses("tax-1"), { wrapper });

    expect(result.current.classes).toBeUndefined();
    expect(result.current.isSuccess).toBe(false);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.classes).toEqual(classes);
    expect(result.current.isError).toBe(false);
    expect(requests).toEqual(["/api/taxonomies/tax-1/classes"]);
  });

  it("requests nothing while disabled or without a taxonomy", async () => {
    const disabled = renderHook(() => useTaxonomyClasses("tax-1", false), { wrapper });
    const blank = renderHook(() => useTaxonomyClasses(""), { wrapper });

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(requests).toEqual([]);
    expect(disabled.result.current.classes).toBeUndefined();
    expect(blank.result.current.isSuccess).toBe(false);
  });

  it("reports a failed request", async () => {
    const { result } = renderHook(() => useTaxonomyClasses("missing"), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.classes).toBeUndefined();
    expect(result.current.isSuccess).toBe(false);
  });
});
