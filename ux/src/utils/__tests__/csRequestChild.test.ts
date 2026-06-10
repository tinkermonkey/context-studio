import { describe, it, expect, vi, beforeEach } from "vitest";
import { csRequestChild } from "../csRequestChild";

declare global {
  interface Window {
    __CS_PENDING?: {
      type: string;
      ctx: Record<string, unknown>;
      identifierDirty?: boolean;
    };
  }
}

describe("csRequestChild", () => {
  beforeEach(() => {
    window.__CS_PENDING = undefined;
  });

  describe("window.__CS_PENDING", () => {
    it("sets type and ctx on window.__CS_PENDING", () => {
      csRequestChild(vi.fn(), "taxonomy", { title: "Foo" });
      expect(window.__CS_PENDING).toEqual(
        expect.objectContaining({ type: "taxonomy", ctx: { title: "Foo" } }),
      );
    });

    it("sets identifierDirty when provided", () => {
      csRequestChild(vi.fn(), "scheme", { title: "Bar" }, true);
      expect(window.__CS_PENDING?.identifierDirty).toBe(true);
    });

    it("sets identifierDirty=false when explicitly false", () => {
      csRequestChild(vi.fn(), "class", { title: "Baz" }, false);
      expect(window.__CS_PENDING?.identifierDirty).toBe(false);
    });

    it("leaves identifierDirty undefined when not provided", () => {
      csRequestChild(vi.fn(), "taxonomy", {});
      expect(window.__CS_PENDING?.identifierDirty).toBeUndefined();
    });
  });

  describe("navigation", () => {
    it("calls onNav after setting pending state", () => {
      const navOrder: string[] = [];
      const onNav = vi.fn(() => {
        navOrder.push(window.__CS_PENDING ? "after-set" : "before-set");
      });
      csRequestChild(onNav, "taxonomy", { title: "Test" });
      expect(onNav).toHaveBeenCalledOnce();
      expect(navOrder).toEqual(["after-set"]);
    });

    it("calls onNav exactly once", () => {
      const onNav = vi.fn();
      csRequestChild(onNav, "taxonomy", {});
      expect(onNav).toHaveBeenCalledTimes(1);
    });
  });
});
