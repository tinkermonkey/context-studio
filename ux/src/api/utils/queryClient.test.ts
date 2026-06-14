import { describe, it, expect, beforeEach, vi } from "vitest";
import { setGlobalErrorHandler, queryClient, handleMutationError } from "./queryClient";

describe("queryClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("has correct default query options", () => {
    const options = queryClient.getDefaultOptions();
    expect(options.queries?.staleTime).toBe(5 * 60 * 1000);
    expect(options.queries?.gcTime).toBe(10 * 60 * 1000);
    expect(options.queries?.retry).toBe(1);
    expect(options.queries?.refetchOnWindowFocus).toBe(false);
  });

  it("registers a mutation error handler on the mutation cache", () => {
    expect(queryClient.getMutationCache().config.onError).toBe(handleMutationError);
  });
});

describe("handleMutationError", () => {
  beforeEach(() => {
    setGlobalErrorHandler(() => {});
  });

  it("toasts the message from an Error object", () => {
    const mockHandler = vi.fn();
    setGlobalErrorHandler(mockHandler);

    handleMutationError(new Error("Custom error message"), {}, undefined, { meta: {} });

    expect(mockHandler).toHaveBeenCalledWith("error", "Custom error message");
  });

  it("toasts a generic message for non-Error values", () => {
    const mockHandler = vi.fn();
    setGlobalErrorHandler(mockHandler);

    handleMutationError("string error", {}, undefined, { meta: {} });

    expect(mockHandler).toHaveBeenCalledWith("error", "An error occurred");
  });

  it("does NOT toast when the mutation opts out via meta.skipGlobalErrorToast", () => {
    const mockHandler = vi.fn();
    setGlobalErrorHandler(mockHandler);

    handleMutationError(new Error("handled locally"), {}, undefined, {
      meta: { skipGlobalErrorToast: true },
    });

    expect(mockHandler).not.toHaveBeenCalled();
  });

  it("does not throw if no handler is set", () => {
    setGlobalErrorHandler(null as unknown as () => void);
    expect(() => {
      handleMutationError(new Error("Test"), {}, undefined, { meta: {} });
    }).not.toThrow();
  });
});
