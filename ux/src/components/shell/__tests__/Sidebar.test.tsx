import { describe, it, expect, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Sidebar } from "@/components/shell/Sidebar";

// Sidebar uses TanStack Router hooks — stub them out
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  useRouterState: () => ({ location: { pathname: "/app" } }),
}));

describe("Sidebar", () => {
  it("applies 'collapsed' as a discrete class when collapsed prop is true", () => {
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
    expect(screen.getByTestId("sidebar").className).not.toContain("collapsed");

    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(onToggle).toHaveBeenCalledTimes(1);

    // Simulate parent updating the prop after toggle
    rerender(<Sidebar collapsed onToggle={onToggle} />);
    expect(screen.getByTestId("sidebar")).toHaveClass("collapsed");
  });
});
