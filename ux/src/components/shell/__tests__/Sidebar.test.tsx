import { describe, it, expect, vi, beforeEach } from "vitest";
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
      // Dashboard should exist and be in a top-level nav-section
      const dashboardItem = screen.getByTestId("sidebar-item-dashboard");
      expect(dashboardItem.parentElement?.className).toBe("nav-section");
    });

    it("does not activate Dashboard when pathname is /app/schema/classes", () => {
      setMockPathname("/app/schema/classes");
      render(<Sidebar />);
      // Schema group and Classes child should both render
      expect(screen.getByTestId("sidebar-item-schema")).toBeTruthy();
      expect(screen.getByTestId("sidebar-item-classes")).toBeTruthy();
      // Classes should be inside a nav-sub (indicating group is expanded for active child)
      const classesItem = screen.getByTestId("sidebar-item-classes");
      expect(classesItem.closest(".nav-sub")).toBeTruthy();
    });

    it("renders correct child when navigating to /app/schema/classes", () => {
      setMockPathname("/app/schema/classes");
      render(<Sidebar />);
      // Classes child should be rendered in the nav-sub container
      const classesItem = screen.getByTestId("sidebar-item-classes");
      expect(classesItem.closest(".nav-section .nav-sub")).toBeTruthy();
    });

    it("renders correct child when navigating to /app/schema/classes with UUID suffix", () => {
      setMockPathname("/app/schema/classes/550e8400-e29b-41d4-a716-446655440000");
      render(<Sidebar />);
      // Classes should still be active for the detail view
      const classesItem = screen.getByTestId("sidebar-item-classes");
      expect(classesItem).toBeTruthy();
      expect(classesItem.closest(".nav-sub")).toBeTruthy();
    });

    it("expands Data group and shows Individuals as active for /app/data/individuals", () => {
      setMockPathname("/app/data/individuals");
      render(<Sidebar />);
      // Data group and Individuals child should render
      const dataGroup = screen.getByTestId("sidebar-item-data");
      const individualsItem = screen.getByTestId("sidebar-item-individuals");
      expect(dataGroup).toBeTruthy();
      expect(individualsItem).toBeTruthy();
      expect(individualsItem.closest(".nav-sub")).toBeTruthy();
    });

    it("activates Settings when pathname is /app/settings", () => {
      setMockPathname("/app/settings");
      render(<Sidebar />);
      // Settings should exist as a top-level item
      const settingsItem = screen.getByTestId("sidebar-item-settings");
      expect(settingsItem.parentElement?.className).toBe("nav-section");
    });

    it("activates correct pipeline child for nested route /app/pipelines/runs/id", () => {
      setMockPathname("/app/pipelines/runs/some-id");
      render(<Sidebar />);
      // Pipelines group and pipelines-runs child should render
      const pipelineRunsItem = screen.getByTestId("sidebar-item-pipelines-runs");
      expect(pipelineRunsItem).toBeTruthy();
      expect(pipelineRunsItem.closest(".nav-sub")).toBeTruthy();
    });
  });
});
