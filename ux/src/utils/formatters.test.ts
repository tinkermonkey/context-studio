import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { formatRelativeTime, formatDuration, formatConfidence } from "./formatters";

describe("formatRelativeTime", () => {
  let dateSpy: any;

  beforeEach(() => {
    const controlledTime = new Date("2024-05-13T12:00:00Z").getTime();
    dateSpy = vi.spyOn(Date, "now").mockReturnValue(controlledTime);
  });

  afterEach(() => {
    dateSpy.mockRestore();
  });

  it("formats as 'just now' for times less than a minute ago", () => {
    const date = new Date("2024-05-13T11:59:50Z");
    expect(formatRelativeTime(date)).toBe("just now");
  });

  it("formats minutes ago", () => {
    const date = new Date("2024-05-13T11:30:00Z");
    expect(formatRelativeTime(date)).toBe("30m ago");
  });

  it("formats hours ago", () => {
    const date = new Date("2024-05-13T08:00:00Z");
    expect(formatRelativeTime(date)).toBe("4h ago");
  });

  it("formats days ago", () => {
    const date = new Date("2024-05-10T12:00:00Z");
    expect(formatRelativeTime(date)).toBe("3d ago");
  });

  it("accepts ISO string dates", () => {
    const date = "2024-05-13T11:30:00Z";
    expect(formatRelativeTime(date)).toBe("30m ago");
  });

  it("returns 'unknown' for invalid dates", () => {
    expect(formatRelativeTime(new Date("invalid"))).toBe("unknown");
    expect(formatRelativeTime("not-a-date")).toBe("unknown");
  });
});

describe("formatDuration", () => {
  it("formats milliseconds", () => {
    expect(formatDuration(500)).toBe("500ms");
  });

  it("formats seconds with one decimal place", () => {
    expect(formatDuration(1500)).toBe("1.5s");
    expect(formatDuration(2000)).toBe("2.0s");
  });

  it("formats large durations in seconds", () => {
    expect(formatDuration(5000)).toBe("5.0s");
    expect(formatDuration(125000)).toBe("125.0s");
  });

  it("formats zero as 0ms", () => {
    expect(formatDuration(0)).toBe("0ms");
  });
});

describe("formatConfidence", () => {
  it("formats confidence as percentage", () => {
    expect(formatConfidence(0.95)).toBe("95%");
    expect(formatConfidence(0.5)).toBe("50%");
    expect(formatConfidence(1.0)).toBe("100%");
  });

  it("rounds to nearest percent", () => {
    expect(formatConfidence(0.954)).toBe("95%");
    expect(formatConfidence(0.956)).toBe("96%");
  });

  it("returns em-dash for null", () => {
    expect(formatConfidence(null)).toBe("—");
  });

  it("returns em-dash for undefined", () => {
    expect(formatConfidence(undefined)).toBe("—");
  });

  it("returns em-dash for NaN", () => {
    expect(formatConfidence(NaN)).toBe("—");
  });

  it("handles zero confidence", () => {
    expect(formatConfidence(0)).toBe("0%");
  });
});
