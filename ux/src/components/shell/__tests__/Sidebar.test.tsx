import { describe, it, expect, vi } from "vitest";
import { buildSidebarProps } from "@/components/shell/Sidebar";

let mockPathname = "/app";
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  useRouterState: () => ({ location: { pathname: mockPathname } }),
}));

describe("Sidebar", () => {
  describe("buildSidebarProps", () => {
    it("returns props object with sections and collapsed state", () => {
      const mockSetCollapsed = vi.fn();
      const props = buildSidebarProps(false, mockSetCollapsed);
      
      expect(props).toBeDefined();
      expect(props.sections).toBeDefined();
      expect(props.collapsed).toBe(false);
      expect(props.onCollapse).toBe(mockSetCollapsed);
    });

    it("returns collapsed true when passed", () => {
      const mockSetCollapsed = vi.fn();
      const props = buildSidebarProps(true, mockSetCollapsed);
      
      expect(props.collapsed).toBe(true);
    });

    it("returns sections array with navigation items", () => {
      const mockSetCollapsed = vi.fn();
      const props = buildSidebarProps(false, mockSetCollapsed);
      
      expect(Array.isArray(props.sections)).toBe(true);
      expect(props.sections.length).toBeGreaterThan(0);
    });
  });
});
