import { describe, it, expect } from "vitest";
import { hasRunStatus } from "../runStatus";

describe("hasRunStatus", () => {
  it("matches run status regardless of case", () => {
    expect(hasRunStatus("completed", "completed")).toBe(true);
    expect(hasRunStatus("COMPLETED", "completed")).toBe(true);
    expect(hasRunStatus("running", "pending", "running")).toBe(true);
  });

  it("is false for other or missing statuses", () => {
    expect(hasRunStatus("failed", "completed")).toBe(false);
    expect(hasRunStatus(undefined, "completed")).toBe(false);
    expect(hasRunStatus(null, "pending")).toBe(false);
  });
});
