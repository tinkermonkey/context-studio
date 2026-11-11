import { describe, expect, it } from "vitest";
import { formatDate } from "@/components/entity/EntityPageParts";

describe("formatDate", () => {
  it("shows the local calendar date, not the UTC one", () => {
    // Late evening and just after midnight local time fall on another UTC
    // day in most zones; the page should still show the local date.
    const lateEvening = new Date(2026, 10, 11, 23, 30);
    const afterMidnight = new Date(2026, 10, 12, 0, 30);
    expect(formatDate(lateEvening.toISOString())).toBe("2026-11-11");
    expect(formatDate(afterMidnight.toISOString())).toBe("2026-11-12");
  });

  it("shows an em dash for a missing or invalid timestamp", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("")).toBe("—");
    expect(formatDate("not a date")).toBe("—");
  });
});
