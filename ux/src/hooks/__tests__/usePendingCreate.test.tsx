import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { usePendingCreate } from "../usePendingCreate";
import type { EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import type { EntityType } from "@/components/crud/CreateDrawer";

function makeRef(overrides?: Partial<EntitySurfaceHandle>) {
  const startCreate = vi.fn();
  return {
    ref: { current: { startCreate, ...overrides } as EntitySurfaceHandle },
    startCreate,
  };
}

describe("usePendingCreate", () => {
  let rafSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    window.__CS_PENDING = undefined;
    // Synchronously run the rAF callback so we can assert after renderHook
    rafSpy = vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });
  });

  afterEach(() => {
    rafSpy.mockRestore();
    window.__CS_PENDING = undefined;
  });

  describe("when no pending state exists", () => {
    it("does not call startCreate when window.__CS_PENDING is undefined", () => {
      const { ref, startCreate } = makeRef();
      renderHook(() => usePendingCreate("taxonomy", ref));
      expect(startCreate).not.toHaveBeenCalled();
    });
  });

  describe("when pending type does not match", () => {
    it("does not call startCreate when types differ", () => {
      window.__CS_PENDING = { type: "scheme", ctx: { title: "Foo" } };
      const { ref, startCreate } = makeRef();
      renderHook(() => usePendingCreate("taxonomy", ref));
      expect(startCreate).not.toHaveBeenCalled();
    });

    it("leaves window.__CS_PENDING intact when types differ", () => {
      window.__CS_PENDING = { type: "scheme", ctx: { title: "Foo" } };
      const { ref } = makeRef();
      renderHook(() => usePendingCreate("taxonomy", ref));
      expect(window.__CS_PENDING).toBeDefined();
    });
  });

  describe("when pending type matches", () => {
    it("calls startCreate with ctx when type matches", () => {
      window.__CS_PENDING = { type: "taxonomy", ctx: { title: "My Tax" } };
      const { ref, startCreate } = makeRef();
      renderHook(() => usePendingCreate("taxonomy", ref));
      expect(startCreate).toHaveBeenCalledWith({ title: "My Tax" }, undefined);
    });

    it("forwards identifierDirty=true to startCreate", () => {
      window.__CS_PENDING = { type: "class", ctx: { title: "Cls" }, identifierDirty: true };
      const { ref, startCreate } = makeRef();
      renderHook(() => usePendingCreate("class", ref));
      expect(startCreate).toHaveBeenCalledWith({ title: "Cls" }, true);
    });

    it("forwards identifierDirty=false to startCreate", () => {
      window.__CS_PENDING = { type: "class", ctx: { title: "Cls" }, identifierDirty: false };
      const { ref, startCreate } = makeRef();
      renderHook(() => usePendingCreate("class", ref));
      expect(startCreate).toHaveBeenCalledWith({ title: "Cls" }, false);
    });

    it("clears window.__CS_PENDING after matching", () => {
      window.__CS_PENDING = { type: "taxonomy", ctx: { title: "My Tax" } };
      const { ref } = makeRef();
      renderHook(() => usePendingCreate("taxonomy", ref));
      expect(window.__CS_PENDING).toBeUndefined();
    });

    it("dispatches via requestAnimationFrame", () => {
      window.__CS_PENDING = { type: "taxonomy", ctx: {} };
      const { ref } = makeRef();
      rafSpy.mockRestore();
      rafSpy = vi.spyOn(window, "requestAnimationFrame").mockImplementation(() => 0);
      renderHook(() => usePendingCreate("taxonomy", ref));
      expect(rafSpy).toHaveBeenCalledOnce();
    });
  });

  describe("runs only on mount", () => {
    it("does not re-run when type prop changes", () => {
      window.__CS_PENDING = { type: "taxonomy", ctx: { title: "X" } };
      const { ref, startCreate } = makeRef();
      const { rerender } = renderHook(({ t }: { t: EntityType }) => usePendingCreate(t, ref), {
        initialProps: { t: "taxonomy" as EntityType },
      });
      rerender({ t: "scheme" });
      // Still called only once (on mount)
      expect(startCreate).toHaveBeenCalledTimes(1);
    });
  });
});
