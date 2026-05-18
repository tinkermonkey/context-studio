import { describe, it, expect, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Sidebar } from "@/components/shell/Sidebar";

// Sidebar uses TanStack Router hooks — stub them out
let mockPathname = "/app";
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  useRouterState: () => ({ location: { pathname: mockPathname } }),
}));

// Helper to set pathname for tests
function setMockPathname(pathname: string) {
  mockPathname = pathname;
}

describe("Sidebar", () => {
  it("applies 'collapsed' class when collapsed prop is true", () => {
    render(<Sidebar collapsed onToggle={vi.fn()} />);
    expect(screen.getByTestId("sidebar")).toHaveClass("collapsed");
  });

  it("does not apply 'collapsed' class when collapsed prop is false", () => {
    render(<Sidebar collapsed={false} onToggle={vi.fn()} />);
    expect(screen.getByTestId("sidebar")).not.toHaveClass("collapsed");
  });

  it("calls onToggle when the toggle button is clicked", () => {
    const onToggle = vi.fn();
    render(<Sidebar collapsed={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("toggles from expanded to collapsed on button click", () => {
    const onToggle = vi.fn();
    const { rerender } = render(<Sidebar collapsed={false} onToggle={onToggle} />);
    expect(screen.getByTestId("sidebar")).not.toHaveClass("collapsed");

    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(onToggle).toHaveBeenCalledTimes(1);

    // Simulate parent updating the prop after toggle
    rerender(<Sidebar collapsed onToggle={onToggle} />);
    expect(screen.getByTestId("sidebar")).toHaveClass("collapsed");
  });

  describe("path matching and highlighting", () => {
    it("only Dashboard is active when pathname is exactly /app", () => {
      setMockPathname("/app");
      render(<Sidebar />);
      const dashboardItem = screen.getByTestId("sidebar-item-dashboard");
      expect(dashboardItem).toHaveAttribute("aria-current", "page");
      // Ensure other top-level items are not active
      expect(screen.getByTestId("sidebar-item-settings")).not.toHaveAttribute(
        "aria-current",
        "page"
      );
    });

    it("does not activate Dashboard when pathname is /app/schema/classes", () => {
      setMockPathname("/app/schema/classes");
      render(<Sidebar />);
      const dashboardItem = screen.getByTestId("sidebar-item-dashboard");
      const classesItem = screen.getByTestId("sidebar-item-classes");
      // Dashboard should NOT be active
      expect(dashboardItem).not.toHaveAttribute("aria-current", "page");
      // Classes should be the active child
      expect(classesItem).toHaveAttribute("aria-current", "page");
    });

    it("renders correct child when navigating to /app/schema/classes", () => {
      setMockPathname("/app/schema/classes");
      render(<Sidebar />);
      const classesItem = screen.getByTestId("sidebar-item-classes");
      // Classes child should be rendered in the nav-sub container
      expect(classesItem.closest(".nav-sub")).toBeTruthy();
      // Classes should be marked as active
      expect(classesItem).toHaveAttribute("aria-current", "page");
    });

    it("renders correct child when navigating to /app/schema/classes with UUID suffix", () => {
      setMockPathname("/app/schema/classes/550e8400-e29b-41d4-a716-446655440000");
      render(<Sidebar />);
      const classesItem = screen.getByTestId("sidebar-item-classes");
      // Classes should still be active for the detail view
      expect(classesItem).toHaveAttribute("aria-current", "page");
      expect(classesItem.closest(".nav-sub")).toBeTruthy();
    });

    it("expands Data group and shows Individuals as active for /app/data/individuals", () => {
      setMockPathname("/app/data/individuals");
      render(<Sidebar />);
      const dataGroup = screen.getByTestId("sidebar-item-data");
      const individualsItem = screen.getByTestId("sidebar-item-individuals");
      // Data group should be active
      expect(dataGroup).toHaveAttribute("aria-current", "page");
      // Individuals should be the active child
      expect(individualsItem).toHaveAttribute("aria-current", "page");
      expect(individualsItem.closest(".nav-sub")).toBeTruthy();
    });

    it("activates Settings when pathname is /app/settings", () => {
      setMockPathname("/app/settings");
      render(<Sidebar />);
      const settingsItem = screen.getByTestId("sidebar-item-settings");
      // Settings should be marked as active
      expect(settingsItem).toHaveAttribute("aria-current", "page");
    });

    it("activates correct pipeline child for nested route /app/pipelines/runs/id", () => {
      setMockPathname("/app/pipelines/runs/some-id");
      render(<Sidebar />);
      const pipelineRunsItem = screen.getByTestId("sidebar-item-pipelines-runs");
      const pipelinesAllItem = screen.getByTestId("sidebar-item-pipelines-all");
      // Run history should be the active child, not All pipelines
      expect(pipelineRunsItem).toHaveAttribute("aria-current", "page");
      expect(pipelinesAllItem).not.toHaveAttribute("aria-current", "page");
      expect(pipelineRunsItem.closest(".nav-sub")).toBeTruthy();
    });
  });
});
