import { describe, it, expect } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useListPaging } from "../useListPaging";

describe("useListPaging", () => {
  it("starts on the first page, newest first, at the default page size", () => {
    const { result } = renderHook(() => useListPaging());
    expect(result.current.params).toEqual({
      limit: 50,
      offset: 0,
      q: undefined,
      sort_by: "created_at",
      sort_order: "desc",
    });
  });

  it("moves pages through the pager props and changes page size", () => {
    const { result } = renderHook(() => useListPaging());
    act(() => result.current.pagination(208).onPageChange(100));
    expect(result.current.params.offset).toBe(100);

    act(() => result.current.pagination(208).onPageSizeChange!(100));
    expect(result.current.params).toMatchObject({ limit: 100, offset: 0 });
  });

  it("debounces search into q and returns to the first page", async () => {
    const { result } = renderHook(() => useListPaging());
    act(() => result.current.pagination(208).onPageChange(50));
    act(() => result.current.setSearch("  neuron "));

    await waitFor(() => expect(result.current.params.q).toBe("neuron"));
    expect(result.current.params.offset).toBe(0);
    expect(result.current.hasSearch).toBe(true);
  });

  it("maps header sorts to sort params and restores the default on clear", () => {
    const { result } = renderHook(() => useListPaging());
    act(() => result.current.onSort("title", "asc"));
    expect(result.current.params).toMatchObject({ sort_by: "title", sort_order: "asc" });
    act(() => result.current.onSort("title", null));
    expect(result.current.params).toMatchObject({ sort_by: "created_at", sort_order: "desc" });
  });

  it("returns to the first page when the filter key changes", () => {
    const { result, rerender } = renderHook(({ filter }) => useListPaging(filter), {
      initialProps: { filter: "all" },
    });
    act(() => result.current.pagination(208).onPageChange(150));
    rerender({ filter: "scheme-1" });
    expect(result.current.params.offset).toBe(0);
  });

  it("steps back when the total shrinks below the current page", () => {
    const { result } = renderHook(() => useListPaging());
    act(() => result.current.pagination(208).onPageChange(200));
    act(() => result.current.clampToTotal(120));
    expect(result.current.params.offset).toBe(100);
  });
});
