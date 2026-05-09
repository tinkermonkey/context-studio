import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useAutosave } from "../useAutosave";
import { createTestQueryClient } from "@/test/test-utils";
import { QueryClientProvider } from "@tanstack/react-query";

describe("useAutosave", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  function renderHookWithProviders<T>(hook: () => T) {
    const queryClient = createTestQueryClient();
    return renderHook(hook, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });
  }

  describe("initialization", () => {
    it("starts in idle state with no last saved timestamp", () => {
      const mockMutationFn = vi.fn();
      const { result } = renderHookWithProviders(() =>
        useAutosave({
          data: { title: "test" },
          mutationFn: mockMutationFn,
        }),
      );

      expect(result.current.status).toBe("idle");
      expect(result.current.lastSavedAt).toBeNull();
      expect(result.current.lastError).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(mockMutationFn).not.toHaveBeenCalled();
    });
  });

  describe("skip first render and debouncing", () => {
    it("does not trigger save on initial mount", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      renderHookWithProviders(() =>
        useAutosave({
          data: { title: "initial data" },
          mutationFn: mockMutationFn,
        }),
      );

      await new Promise(resolve => setTimeout(resolve, 300));
      expect(mockMutationFn).not.toHaveBeenCalled();
    });

    it("saves on second render after debounce period", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      let dataValue = { title: "initial" };

      const { rerender } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      expect(mockMutationFn).not.toHaveBeenCalled();

      dataValue = { title: "updated" };
      rerender();

      await new Promise(resolve => setTimeout(resolve, 300));

      expect(mockMutationFn).toHaveBeenCalled();
    });

    it("debounces rapid changes", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      let dataValue = { title: "v1" };

      const { rerender } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      dataValue = { title: "v2" };
      rerender();

      await new Promise(resolve => setTimeout(resolve, 50));

      dataValue = { title: "v3" };
      rerender();

      await new Promise(resolve => setTimeout(resolve, 50));

      dataValue = { title: "v4" };
      rerender();

      await new Promise(resolve => setTimeout(resolve, 300));

      expect(mockMutationFn).toHaveBeenCalledOnce();
    });

    it("respects custom debounceMs option", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      let dataValue = { title: "v1" };

      const { rerender } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
          debounceMs: 500,
        }),
      );

      dataValue = { title: "v2" };
      rerender();

      await new Promise(resolve => setTimeout(resolve, 300));
      expect(mockMutationFn).not.toHaveBeenCalled();

      await new Promise(resolve => setTimeout(resolve, 300));
      expect(mockMutationFn).toHaveBeenCalled();
    });
  });

  describe("status transitions", () => {
    it("transitions through idle → saving → saved → idle", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      let dataValue = { title: "v1" };

      const { rerender, result } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      expect(result.current.status).toBe("idle");

      dataValue = { title: "v2" };
      rerender();

      await waitFor(
        () => {
          expect(["saving", "saved"]).toContain(result.current.status);
        },
        { timeout: 500 },
      );

      await waitFor(
        () => {
          expect(result.current.status).toBe("saved");
        },
        { timeout: 500 },
      );

      await new Promise(resolve => setTimeout(resolve, 1600));

      expect(result.current.status).toBe("idle");
    });
  });

  describe("lastSavedAt timestamp", () => {
    it("sets lastSavedAt on successful save", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      let dataValue = { title: "v1" };

      const { rerender, result } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      expect(result.current.lastSavedAt).toBeNull();

      dataValue = { title: "v2" };
      rerender();

      await waitFor(
        () => {
          expect(result.current.lastSavedAt).not.toBeNull();
        },
        { timeout: 500 },
      );
    });

    it("updates lastSavedAt across multiple saves", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      let dataValue = { title: "v1" };

      const { rerender, result } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      dataValue = { title: "v2" };
      rerender();

      await waitFor(
        () => {
          expect(result.current.status).toBe("saved");
        },
        { timeout: 500 },
      );

      const firstSavedAt = result.current.lastSavedAt;

      await new Promise(resolve => setTimeout(resolve, 1600));

      expect(result.current.status).toBe("idle");

      dataValue = { title: "v3" };
      rerender();

      await waitFor(
        () => {
          expect(result.current.lastSavedAt).not.toBe(firstSavedAt);
        },
        { timeout: 500 },
      );
    });
  });

  describe("error handling", () => {
    it("sets status to error and captures error on failure", async () => {
      const testError = new Error("Save failed");
      const mockMutationFn = vi.fn().mockRejectedValue(testError);
      let dataValue = { title: "v1" };

      const { rerender, result } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      dataValue = { title: "v2" };
      rerender();

      await waitFor(
        () => {
          expect(result.current.status).toBe("error");
        },
        { timeout: 500 },
      );

      expect(result.current.lastError?.message).toBe("Save failed");
    });

    it("calls onError callback when mutation fails", async () => {
      const testError = new Error("Save failed");
      const mockMutationFn = vi.fn().mockRejectedValue(testError);
      const onError = vi.fn();
      let dataValue = { title: "v1" };

      const { rerender } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
          onError,
        }),
      );

      dataValue = { title: "v2" };
      rerender();

      await waitFor(
        () => {
          expect(onError).toHaveBeenCalledWith(expect.any(Error));
        },
        { timeout: 500 },
      );

      expect(onError).toHaveBeenCalledWith(testError);
    });

    it("blocks save attempts when in error state", async () => {
      const testError = new Error("Save failed");
      const mockMutationFn = vi.fn()
        .mockRejectedValueOnce(testError)
        .mockResolvedValueOnce(undefined);

      let dataValue = { title: "v1" };

      const { rerender, result } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      dataValue = { title: "v2" };
      rerender();

      await waitFor(
        () => {
          expect(result.current.status).toBe("error");
        },
        { timeout: 500 },
      );

      const initialCallCount = mockMutationFn.mock.calls.length;

      dataValue = { title: "v3" };
      rerender();

      await new Promise(resolve => setTimeout(resolve, 300));

      expect(mockMutationFn).toHaveBeenCalledTimes(initialCallCount);
      expect(result.current.status).toBe("error");
    });
  });

  describe("manual save", () => {
    it("allows immediate save via save() method", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHookWithProviders(() =>
        useAutosave({
          data: { title: "test" },
          mutationFn: mockMutationFn,
        }),
      );

      await act(async () => {
        result.current.save();
      });

      await waitFor(
        () => {
          expect(mockMutationFn).toHaveBeenCalled();
        },
        { timeout: 500 },
      );
    });

    it("manual save triggers state transitions", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHookWithProviders(() =>
        useAutosave({
          data: { title: "test" },
          mutationFn: mockMutationFn,
        }),
      );

      expect(result.current.status).toBe("idle");

      result.current.save();

      await waitFor(
        () => {
          expect(["saving", "saved"]).toContain(result.current.status);
        },
        { timeout: 500 },
      );
    });
  });

  describe("cleanup", () => {
    it("clears debounce timeout on unmount", async () => {
      const mockMutationFn = vi.fn().mockResolvedValue(undefined);
      let dataValue = { title: "v1" };

      const { rerender, unmount } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      dataValue = { title: "v2" };
      rerender();
      unmount();

      await new Promise(resolve => setTimeout(resolve, 300));
      expect(mockMutationFn).not.toHaveBeenCalled();
    });
  });

  describe("isLoading flag", () => {
    it("reflects mutation pending state", async () => {
      const mockMutationFn = vi.fn(
        () =>
          new Promise<void>((resolve) => {
            setTimeout(() => resolve(), 100);
          }),
      );

      let dataValue = { title: "v1" };

      const { rerender, result } = renderHookWithProviders(() =>
        useAutosave({
          data: dataValue,
          mutationFn: mockMutationFn,
        }),
      );

      expect(result.current.isLoading).toBe(false);

      dataValue = { title: "v2" };
      rerender();

      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(true);
        },
        { timeout: 500 },
      );

      await new Promise(resolve => setTimeout(resolve, 150));

      expect(result.current.isLoading).toBe(false);
    });
  });
});
