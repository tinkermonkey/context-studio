import { describe, it, expect } from "vitest";
import { getStatusColor } from "./statusColorUtils";

describe("getStatusColor", () => {
  it("returns emerald for success status", () => {
    expect(getStatusColor("success")).toBe("emerald");
  });

  it("returns rose for error status", () => {
    expect(getStatusColor("error")).toBe("rose");
  });

  it("returns amber for timeout status", () => {
    expect(getStatusColor("timeout")).toBe("amber");
  });

  it("returns gray for unknown status", () => {
    expect(getStatusColor("unknown" as any)).toBe("gray");
  });
});
