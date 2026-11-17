import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { fireEvent, renderHook } from "@testing-library/react";
import { useReviewClock } from "../useReviewClock";

const START = new Date("2026-11-17T10:00:00Z").getTime();

function at(offsetMs: number) {
  vi.setSystemTime(START + offsetMs);
}

describe("useReviewClock", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    at(0);
  });
  afterEach(() => vi.useRealTimers());

  it("times the selected element from its selection, through pointer and key activity", () => {
    const { result } = renderHook(() => useReviewClock());
    result.current.startElement("a");
    at(3_000);
    fireEvent.pointerMove(window);
    at(5_000);
    fireEvent.keyDown(window, { key: "j" });
    at(5_400);
    expect(result.current.spentOn("a")).toBe(5_400);
    expect(result.current.pageMs()).toBe(5_400);
  });

  it("restarts when another element is selected", () => {
    const { result } = renderHook(() => useReviewClock());
    result.current.startElement("a");
    at(4_000);
    fireEvent.pointerDown(window);
    result.current.startElement("b");
    at(6_000);
    expect(result.current.spentOn("b")).toBe(2_000);
    // Only the selected element is timed.
    expect(result.current.spentOn("a")).toBe(0);
    expect(result.current.pageMs()).toBe(6_000);
  });

  it("does not restart when the same element is selected again", () => {
    const { result } = renderHook(() => useReviewClock());
    result.current.startElement("a");
    at(4_000);
    result.current.startElement("a");
    at(7_000);
    expect(result.current.spentOn("a")).toBe(7_000);
  });

  it("leaves out an idle gap over two minutes", () => {
    const { result } = renderHook(() => useReviewClock());
    result.current.startElement("a");
    at(10_000);
    fireEvent.pointerMove(window);
    at(10_000 + 150_000);
    fireEvent.wheel(window);
    at(10_000 + 150_000 + 1_000);
    expect(result.current.spentOn("a")).toBe(11_000);
    expect(result.current.pageMs()).toBe(11_000);
  });

  it("stops timing after unmount", () => {
    const { result, unmount } = renderHook(() => useReviewClock());
    result.current.startElement("a");
    unmount();
    at(150_000);
    fireEvent.pointerMove(window);
    // The event no longer reaches the clock: the gap since start is idle.
    expect(result.current.spentOn("a")).toBe(0);
  });
});
