import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { TabBar } from "@tinkermonkey/heimdall-ui";

describe("Heimdall TabBar", () => {
  const mockTabs = [
    { id: "tab-1", label: "Tab 1" },
    { id: "tab-2", label: "Tab 2" },
    { id: "tab-3", label: "Tab 3" },
  ];

  describe("data-testid attributes", () => {
    it("renders with data-testid when provided", () => {
      render(
        <TabBar
          tabs={mockTabs}
          activeTabId="tab-1"
          onSelectTab={vi.fn()}
          data-testid="test-tabbar"
        />,
      );
      expect(screen.getByTestId("test-tabbar")).toBeInTheDocument();
    });

    it("renders without data-testid when not provided", () => {
      const { container } = render(
        <TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />,
      );
      const tabbar = container.querySelector("div");
      expect(tabbar?.getAttribute("data-testid")).toBeNull();
    });
  });

  describe("CSS class styling", () => {
    it("renders tab buttons", () => {
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs.length).toBe(3);
    });

    it("renders all tab labels", () => {
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />);
      expect(screen.getByText("Tab 1")).toBeInTheDocument();
      expect(screen.getByText("Tab 2")).toBeInTheDocument();
      expect(screen.getByText("Tab 3")).toBeInTheDocument();
    });

    it("applies className prop to container", () => {
      const { container } = render(
        <TabBar
          tabs={mockTabs}
          activeTabId="tab-1"
          onSelectTab={vi.fn()}
          className="custom-tabbar"
        />,
      );
      const wrapper = container.querySelector(".custom-tabbar");
      expect(wrapper).toBeInTheDocument();
    });

    it("combines multiple className values", () => {
      const { container } = render(
        <TabBar
          tabs={mockTabs}
          activeTabId="tab-1"
          onSelectTab={vi.fn()}
          className="custom-1 custom-2"
        />,
      );
      const wrapper = container.querySelector(".custom-1");
      expect(wrapper).toBeInTheDocument();
      expect(wrapper).toHaveClass("custom-2");
    });
  });

  describe("ARIA roles and attributes", () => {
    it("renders tablist role on container", () => {
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />);
      expect(screen.getByRole("tablist")).toBeInTheDocument();
    });

    it("renders tabs with tab role", () => {
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs.length).toBe(3);
    });

    it("active tab has aria-selected true", () => {
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs[0]).toHaveAttribute("aria-selected", "true");
      expect(tabs[1]).toHaveAttribute("aria-selected", "false");
      expect(tabs[2]).toHaveAttribute("aria-selected", "false");
    });

    it("inactive tabs have aria-selected false", () => {
      render(<TabBar tabs={mockTabs} activeTabId="tab-2" onSelectTab={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs[0]).toHaveAttribute("aria-selected", "false");
      expect(tabs[1]).toHaveAttribute("aria-selected", "true");
      expect(tabs[2]).toHaveAttribute("aria-selected", "false");
    });

    it("aria-selected updates when activeTabId changes", () => {
      const { rerender } = render(
        <TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />,
      );
      let tabs = screen.getAllByRole("tab");
      expect(tabs[0]).toHaveAttribute("aria-selected", "true");
      expect(tabs[1]).toHaveAttribute("aria-selected", "false");

      rerender(<TabBar tabs={mockTabs} activeTabId="tab-2" onSelectTab={vi.fn()} />);
      tabs = screen.getAllByRole("tab");
      expect(tabs[0]).toHaveAttribute("aria-selected", "false");
      expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    });
  });

  describe("interactions", () => {
    it("calls onSelectTab with correct tab id when tab is clicked", async () => {
      const onSelectTab = vi.fn();
      const user = userEvent.setup();
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={onSelectTab} />);

      await user.click(screen.getByText("Tab 2"));
      expect(onSelectTab).toHaveBeenCalledWith("tab-2");
    });

    it("calls onSelectTab with correct id for multiple tab clicks", async () => {
      const onSelectTab = vi.fn();
      const user = userEvent.setup();
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={onSelectTab} />);

      await user.click(screen.getByText("Tab 3"));
      expect(onSelectTab).toHaveBeenCalledWith("tab-3");
    });

    it("updates aria-selected when activeTabId prop changes", () => {
      const { rerender, container } = render(
        <TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />,
      );

      let tabs = container.querySelectorAll("[role=tab]");
      expect(tabs[0]).toHaveAttribute("aria-selected", "true");

      rerender(<TabBar tabs={mockTabs} activeTabId="tab-2" onSelectTab={vi.fn()} />);
      tabs = container.querySelectorAll("[role=tab]");
      expect(tabs[1]).toHaveAttribute("aria-selected", "true");
      expect(tabs[0]).toHaveAttribute("aria-selected", "false");
    });
  });

  describe("empty state", () => {
    it("renders empty tablist when no tabs provided", () => {
      render(<TabBar tabs={[]} activeTabId="" onSelectTab={vi.fn()} />);
      expect(screen.getByRole("tablist")).toBeInTheDocument();
      const tabs = screen.queryAllByRole("tab");
      expect(tabs.length).toBe(0);
    });
  });

  describe("tab labels", () => {
    it("renders all tab labels", () => {
      render(<TabBar tabs={mockTabs} activeTabId="tab-1" onSelectTab={vi.fn()} />);
      expect(screen.getByText("Tab 1")).toBeInTheDocument();
      expect(screen.getByText("Tab 2")).toBeInTheDocument();
      expect(screen.getByText("Tab 3")).toBeInTheDocument();
    });

    it("renders element labels", () => {
      const tabsWithElements = [
        { id: "tab-1", label: <strong>Bold Label</strong> },
        { id: "tab-2", label: "Tab 2" },
      ];
      render(
        <TabBar tabs={tabsWithElements} activeTabId="tab-1" onSelectTab={vi.fn()} />,
      );
      expect(screen.getByText("Bold Label")).toBeInTheDocument();
    });
  });
});
