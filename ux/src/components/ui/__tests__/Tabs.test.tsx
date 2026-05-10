import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { Tabs } from "../Tabs";

describe("Tabs", () => {
  const mockTabs = [
    { id: "tab-1", label: "Tab 1" },
    { id: "tab-2", label: "Tab 2" },
    { id: "tab-3", label: "Tab 3" },
  ];

  describe("CSS class styling", () => {
    it("applies tabs container class", () => {
      const { container } = render(
        <Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />,
      );
      expect(container.querySelector(".tabs")).toBeInTheDocument();
    });

    it("renders tab buttons with tab class", () => {
      const { container } = render(
        <Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />,
      );
      const tabButtons = container.querySelectorAll(".tab");
      expect(tabButtons.length).toBe(3);
    });

    it("applies active class to active tab", () => {
      const { container } = render(
        <Tabs tabs={mockTabs} active="tab-2" onChange={vi.fn()} />,
      );
      const tabs = container.querySelectorAll(".tab");
      const activeTab = tabs[1];
      expect(activeTab).toHaveClass("active");
    });

    it("does not apply active class to inactive tabs", () => {
      const { container } = render(
        <Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />,
      );
      const tabs = container.querySelectorAll(".tab");
      expect(tabs[1]).not.toHaveClass("active");
      expect(tabs[2]).not.toHaveClass("active");
    });
  });

  describe("tab content", () => {
    it("renders all tab labels", () => {
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      expect(screen.getByText("Tab 1")).toBeInTheDocument();
      expect(screen.getByText("Tab 2")).toBeInTheDocument();
      expect(screen.getByText("Tab 3")).toBeInTheDocument();
    });

    it("renders element labels", () => {
      const tabsWithElements = [
        { id: "tab-1", label: <strong>Bold</strong> },
        { id: "tab-2", label: "Tab 2" },
      ];
      render(<Tabs tabs={tabsWithElements} active="tab-1" onChange={vi.fn()} />);
      expect(screen.getByText("Bold")).toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    it("renders tabs as buttons", () => {
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      const buttons = screen.getAllByRole("button");
      expect(buttons.length).toBe(3);
    });

    it("buttons have button type", () => {
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      const buttons = screen.getAllByRole("button");
      buttons.forEach((btn) => {
        expect(btn).toHaveAttribute("type", "button");
      });
    });
  });

  describe("interactions", () => {
    it("calls onChange with correct tab id when tab is clicked", async () => {
      const onChange = vi.fn();
      const user = userEvent.setup();
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={onChange} />);

      await user.click(screen.getByText("Tab 2"));
      expect(onChange).toHaveBeenCalledWith("tab-2");
    });

    it("calls onChange with correct id for multiple tabs", async () => {
      const onChange = vi.fn();
      const user = userEvent.setup();
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={onChange} />);

      await user.click(screen.getByText("Tab 3"));
      expect(onChange).toHaveBeenCalledWith("tab-3");
    });

    it("updates active tab class when active prop changes", () => {
      const { container, rerender } = render(
        <Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />,
      );

      let tabs = container.querySelectorAll(".tab");
      expect(tabs[0]).toHaveClass("active");

      rerender(<Tabs tabs={mockTabs} active="tab-2" onChange={vi.fn()} />);
      tabs = container.querySelectorAll(".tab");
      expect(tabs[1]).toHaveClass("active");
      expect(tabs[0]).not.toHaveClass("active");
    });
  });

  describe("empty state", () => {
    it("renders empty container when no tabs provided", () => {
      const { container } = render(
        <Tabs tabs={[]} active="" onChange={vi.fn()} />,
      );
      expect(container.querySelector(".tabs")).toBeInTheDocument();
      expect(container.querySelectorAll(".tab").length).toBe(0);
    });
  });
});
