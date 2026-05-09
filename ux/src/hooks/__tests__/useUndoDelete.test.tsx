import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useUndoDelete } from "../useUndoDelete";

describe("useUndoDelete", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.runAllTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  describe("initialization", () => {
    it("starts with null deletedId and exposes performDelete and undo", () => {
      const onDelete = vi.fn();
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete }),
      );

      expect(result.current.deletedId).toBeNull();
      expect(typeof result.current.performDelete).toBe("function");
      expect(typeof result.current.undo).toBe("function");
    });
  });

  describe("performDelete scheduling", () => {
    it("schedules onDelete callback with correct delay", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, undoWindowMs: 1000 }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      expect(onDelete).not.toHaveBeenCalled();

      await act(async () => {
        vi.advanceTimersByTime(1100);
      });

      expect(onDelete).toHaveBeenCalledWith("test-id");
    });

    it("respects custom undoWindowMs", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, undoWindowMs: 5000 }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      await act(async () => {
        vi.advanceTimersByTime(5100);
      });

      expect(onDelete).toHaveBeenCalledWith("test-id");
    });

    it("uses 8000ms default when undoWindowMs not specified", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      await act(async () => {
        vi.advanceTimersByTime(8100);
      });

      expect(onDelete).toHaveBeenCalledWith("test-id");
    });

    it("replaces pending timeout for same ID", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, undoWindowMs: 1000 }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      await act(async () => {
        vi.advanceTimersByTime(600);
      });

      await act(async () => {
        result.current.performDelete("test-id");
      });

      await act(async () => {
        vi.advanceTimersByTime(1100);
      });

      expect(onDelete).toHaveBeenCalledTimes(1);
    });
  });

  describe("undo prevents deletion", () => {
    it("prevents deletion when undo called before timeout", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, undoWindowMs: 1000 }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      await act(async () => {
        vi.advanceTimersByTime(600);
      });

      await act(async () => {
        result.current.undo();
      });

      await act(async () => {
        vi.advanceTimersByTime(500);
      });

      expect(onDelete).not.toHaveBeenCalled();
    });

    it("is idempotent when called without pending delete", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete }),
      );

      await act(async () => {
        result.current.undo();
        result.current.undo();
      });

      expect(onDelete).not.toHaveBeenCalled();
    });
  });

  describe("module-level persistence", () => {
    it("deletion executes even after component unmounts", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result, unmount } = renderHook(() =>
        useUndoDelete({ onDelete, undoWindowMs: 1000 }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      unmount();

      await act(async () => {
        vi.advanceTimersByTime(1100);
      });

      expect(onDelete).toHaveBeenCalledWith("test-id");
    });

    it("multiple hook instances maintain separate pending deletes", async () => {
      const onDelete1 = vi.fn().mockResolvedValue(undefined);
      const onDelete2 = vi.fn().mockResolvedValue(undefined);

      const { result: result1 } = renderHook(() =>
        useUndoDelete({ onDelete: onDelete1, undoWindowMs: 1000 }),
      );

      const { result: result2 } = renderHook(() =>
        useUndoDelete({ onDelete: onDelete2, undoWindowMs: 1000 }),
      );

      await act(async () => {
        result1.current.performDelete("id-1");
        result2.current.performDelete("id-2");
      });

      await act(async () => {
        vi.advanceTimersByTime(1100);
      });

      expect(onDelete1).toHaveBeenCalledWith("id-1");
      expect(onDelete2).toHaveBeenCalledWith("id-2");
    });
  });

  describe("error handling", () => {
    it("calls onDeleteError when deletion rejects", async () => {
      const error = new Error("Delete failed");
      const onDelete = vi.fn().mockRejectedValue(error);
      const onDeleteError = vi.fn();

      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, onDeleteError, undoWindowMs: 100 }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      await act(async () => {
        vi.advanceTimersByTime(150);
      });

      expect(onDeleteError).toHaveBeenCalledWith("test-id", error);
    });

    it("converts non-Error rejections to Error", async () => {
      const onDelete = vi.fn().mockRejectedValue("String error");
      const onDeleteError = vi.fn();

      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, onDeleteError, undoWindowMs: 100 }),
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      await act(async () => {
        vi.advanceTimersByTime(150);
      });

      const passedError = onDeleteError.mock.calls[0][1];
      expect(passedError).toBeInstanceOf(Error);
      expect(passedError.message).toBe("String error");
    });
  });

  describe("edge cases", () => {
    it("handles empty string ID", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, undoWindowMs: 100 }),
      );

      await act(async () => {
        result.current.performDelete("");
      });

      await act(async () => {
        vi.advanceTimersByTime(150);
      });

      expect(onDelete).toHaveBeenCalledWith("");
    });

    it("handles rapid sequential deletes", async () => {
      const onDelete = vi.fn().mockResolvedValue(undefined);
      const { result } = renderHook(() =>
        useUndoDelete({ onDelete, undoWindowMs: 100 }),
      );

      await act(async () => {
        result.current.performDelete("id-1");
        result.current.performDelete("id-2");
        result.current.performDelete("id-3");
      });

      await act(async () => {
        vi.advanceTimersByTime(150);
      });

      expect(onDelete).toHaveBeenCalledTimes(3);
    });
  });

  describe("callback dependency updates", () => {
    it("uses the callback provided when delete was scheduled", async () => {
      const onDelete1 = vi.fn().mockResolvedValue(undefined);
      const onDelete2 = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ onDelete: fn }: any) =>
          useUndoDelete({ onDelete: fn, undoWindowMs: 100 }),
        { initialProps: { onDelete: onDelete1 } },
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      rerender({ onDelete: onDelete2 });

      await act(async () => {
        vi.advanceTimersByTime(150);
      });

      expect(onDelete1).toHaveBeenCalledWith("test-id");
      expect(onDelete2).not.toHaveBeenCalled();
    });

    it("uses the error callback provided when delete was scheduled", async () => {
      const error = new Error("Failed");
      const onDelete = vi.fn().mockRejectedValue(error);
      const onDeleteError1 = vi.fn();
      const onDeleteError2 = vi.fn();

      const { result, rerender } = renderHook(
        ({ onDeleteError: fn }: any) =>
          useUndoDelete({ onDelete, onDeleteError: fn, undoWindowMs: 100 }),
        { initialProps: { onDeleteError: onDeleteError1 } },
      );

      await act(async () => {
        result.current.performDelete("test-id");
      });

      rerender({ onDeleteError: onDeleteError2 });

      await act(async () => {
        vi.advanceTimersByTime(150);
      });

      expect(onDeleteError1).toHaveBeenCalledWith("test-id", error);
      expect(onDeleteError2).not.toHaveBeenCalled();
    });
  });
});
