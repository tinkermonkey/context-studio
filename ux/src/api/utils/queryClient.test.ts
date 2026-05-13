import { describe, it, expect, beforeEach, vi } from "vitest";
import { setGlobalErrorHandler, queryClient } from "./queryClient";

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

  it("has mutation error handler configured", () => {
    const options = queryClient.getDefaultOptions();
    expect(options.mutations?.onError).toBeDefined();
  });
});

describe("setGlobalErrorHandler", () => {
  beforeEach(() => {
    // Reset error handler
    setGlobalErrorHandler(() => {});
  });

  it("sets a global error handler function", () => {
    const mockHandler = vi.fn();
    setGlobalErrorHandler(mockHandler);

    // Get the error handler from query client options
    const options = queryClient.getDefaultOptions();
    const onError = options.mutations?.onError;

    // Trigger the error handler
    const testError = new Error("Test error");
    onError?.(testError, {}, undefined, {} as any);

    expect(mockHandler).toHaveBeenCalledWith("error", "Test error");
  });

  it("handles error with message from Error object", () => {
    const mockHandler = vi.fn();
    setGlobalErrorHandler(mockHandler);

    const options = queryClient.getDefaultOptions();
    const onError = options.mutations?.onError;

    const testError = new Error("Custom error message");
    onError?.(testError, {}, undefined, {} as any);

    expect(mockHandler).toHaveBeenCalledWith("error", "Custom error message");
  });

  it("handles non-Error objects with generic message", () => {
    const mockHandler = vi.fn();
    setGlobalErrorHandler(mockHandler);

    const options = queryClient.getDefaultOptions();
    const onError = options.mutations?.onError;

    onError?.("string error" as any, {}, undefined, {} as any);

    expect(mockHandler).toHaveBeenCalledWith("error", "An error occurred");
  });

  it("does not throw if no handler is set", () => {
    setGlobalErrorHandler(null as any);

    const options = queryClient.getDefaultOptions();
    const onError = options.mutations?.onError;

    expect(() => {
      onError?.(new Error("Test"), {}, undefined, {} as any);
    }).not.toThrow();
  });
});
