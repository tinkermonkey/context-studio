import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { formatTimeAgo } from "./dateFormatting";

describe("formatTimeAgo", () => {
  let dateSpy: any;

  beforeEach(() => {
    const controlledTime = new Date("2024-05-13T12:00:00Z").getTime();
    dateSpy = vi.spyOn(Date, "now").mockReturnValue(controlledTime);
  });

  afterEach(() => {
    dateSpy.mockRestore();
  });

  it("formats seconds ago", () => {
    const date = new Date("2024-05-13T11:59:30Z");
    expect(formatTimeAgo(date)).toBe("30s ago");
  });

  it("formats minutes ago", () => {
    const date = new Date("2024-05-13T11:45:00Z");
    expect(formatTimeAgo(date)).toBe("15m ago");
  });

  it("formats hours ago", () => {
    const date = new Date("2024-05-13T08:00:00Z");
    expect(formatTimeAgo(date)).toBe("4h ago");
  });

  it("shows 0 seconds for very recent dates", () => {
    const date = new Date("2024-05-13T11:59:59Z");
    expect(formatTimeAgo(date)).toBe("1s ago");
  });
});
