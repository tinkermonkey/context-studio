import { describe, it, expect } from "vitest";
import { firstRejectionDetail, deleteFailureMessage } from "@/api/mutationErrors";
import { ApiError } from "@/api/client/interceptors";

function rejected(reason: unknown): PromiseRejectedResult {
  return { status: "rejected", reason };
}
function fulfilled(value: unknown = undefined): PromiseFulfilledResult<unknown> {
  return { status: "fulfilled", value };
}

describe("firstRejectionDetail", () => {
  it("returns the backend detail from an ApiError", () => {
    const detail = "Cannot delete class X: it has 1 subclass(es)";
    expect(firstRejectionDetail([rejected(new ApiError("Unprocessable Entity", 422, detail))])).toBe(
      detail,
    );
  });

  it("falls back to a plain Error message", () => {
    expect(firstRejectionDetail([rejected(new Error("network down"))])).toBe("network down");
  });

  it("uses a generic fallback for non-Error reasons", () => {
    expect(firstRejectionDetail([rejected("weird")])).toBe("An unexpected error occurred.");
  });

  it("reports the first rejection, ignoring fulfilled results", () => {
    const results = [
      fulfilled(),
      rejected(new ApiError("Conflict", 409, "first reason")),
      rejected(new ApiError("Conflict", 409, "second reason")),
    ];
    expect(firstRejectionDetail(results)).toBe("first reason");
  });
});

describe("deleteFailureMessage", () => {
  it("returns just the detail when nothing succeeded", () => {
    const results = [rejected(new ApiError("Unprocessable Entity", 422, "Cannot delete: it has 2 class(es)"))];
    expect(deleteFailureMessage(results, 1)).toBe("Cannot delete: it has 2 class(es)");
  });

  it("prefixes the surviving/failed counts on a partial bulk failure", () => {
    const results = [fulfilled(), rejected(new ApiError("Unprocessable Entity", 422, "blocked"))];
    expect(deleteFailureMessage(results, 2)).toBe("1 deleted, 1 could not be removed. blocked");
  });
});
