import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tabs } from "../Tabs";

vi.mock("@tinkermonkey/heimdall-ui", () => ({
  TabBar: ({ tabs, activeTabId, onSelectTab, className }: any) => (
    <div
      data-testid="heimdall-tab-bar"
      className={className}
      role="tablist"
      data-active={activeTabId}
    >
      {tabs.map((tab: any) => (
        <button
          key={tab.id}
          data-testid={`tab-${tab.id}`}
          role="tab"
          aria-selected={tab.id === activeTabId}
          onClick={() => onSelectTab(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined && <span> ({tab.count})</span>}
        </button>
      ))}
    </div>
  ),
}));

describe("Tabs", () => {
  const mockOnChange = vi.fn();

  const defaultTabs = [
    { id: "tab-1", label: "Tab 1" },
    { id: "tab-2", label: "Tab 2" },
    { id: "tab-3", label: "Tab 3" },
  ];

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  describe("rendering", () => {
    it("renders HeimdallTabBar component", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      expect(screen.getByTestId("heimdall-tab-bar")).toBeInTheDocument();
    });

    it("renders all provided tabs", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      expect(screen.getByText("Tab 1")).toBeInTheDocument();
      expect(screen.getByText("Tab 2")).toBeInTheDocument();
      expect(screen.getByText("Tab 3")).toBeInTheDocument();
    });

    it("renders single tab", () => {
      const singleTab = [{ id: "only-tab", label: "Only Tab" }];
      render(<Tabs tabs={singleTab} active="only-tab" onChange={mockOnChange} />);
      expect(screen.getByText("Only Tab")).toBeInTheDocument();
    });

    it("renders empty tabs array", () => {
      render(<Tabs tabs={[]} active="" onChange={mockOnChange} />);
      expect(screen.getByTestId("heimdall-tab-bar")).toBeInTheDocument();
      const tabs = screen.queryAllByRole("tab");
      expect(tabs).toHaveLength(0);
    });
  });

  describe("active tab state", () => {
    it("marks first tab as active when active prop is tab-1", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tab1 = screen.getByTestId("tab-tab-1");
      expect(tab1).toHaveAttribute("aria-selected", "true");
    });

    it("marks second tab as active when active prop is tab-2", () => {
      render(<Tabs tabs={defaultTabs} active="tab-2" onChange={mockOnChange} />);
      const tab2 = screen.getByTestId("tab-tab-2");
      expect(tab2).toHaveAttribute("aria-selected", "true");
    });

    it("marks only one tab as selected at a time", () => {
      render(<Tabs tabs={defaultTabs} active="tab-2" onChange={mockOnChange} />);
      const selectedTabs = screen.getAllByRole("tab", { selected: true });
      expect(selectedTabs).toHaveLength(1);
    });

    it("sets data-active attribute on tabbar", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tabBar = screen.getByTestId("heimdall-tab-bar");
      expect(tabBar).toHaveAttribute("data-active", "tab-1");
    });

    it("updates active tab when active prop changes", () => {
      const { rerender } = render(
        <Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />
      );
      expect(screen.getByTestId("tab-tab-1")).toHaveAttribute("aria-selected", "true");

      rerender(<Tabs tabs={defaultTabs} active="tab-2" onChange={mockOnChange} />);
      expect(screen.getByTestId("tab-tab-2")).toHaveAttribute("aria-selected", "true");
      expect(screen.getByTestId("tab-tab-1")).toHaveAttribute("aria-selected", "false");
    });
  });

  describe("tab click handling", () => {
    it("calls onChange with tab id when tab is clicked", () => {
      const { container } = render(
        <Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />
      );
      const tab2 = screen.getByTestId("tab-tab-2");
      tab2.click();
      expect(mockOnChange).toHaveBeenCalledWith("tab-2");
    });

    it("calls onChange once per click", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tab2 = screen.getByTestId("tab-tab-2");
      tab2.click();
      expect(mockOnChange).toHaveBeenCalledTimes(1);
    });

    it("calls onChange when clicking a different tab", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      screen.getByTestId("tab-tab-3").click();
      expect(mockOnChange).toHaveBeenCalledWith("tab-3");
    });

    it("handles clicking the active tab", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tab1 = screen.getByTestId("tab-tab-1");
      tab1.click();
      expect(mockOnChange).toHaveBeenCalledWith("tab-1");
    });
  });

  describe("tab count display", () => {
    it("renders count when provided", () => {
      const tabsWithCount = [
        { id: "tab-1", label: "Tab 1", count: 5 },
        { id: "tab-2", label: "Tab 2", count: 0 },
      ];
      render(<Tabs tabs={tabsWithCount} active="tab-1" onChange={mockOnChange} />);
      const tab1 = screen.getByTestId("tab-tab-1");
      const tab2 = screen.getByTestId("tab-tab-2");
      expect(tab1.textContent).toContain("5");
      expect(tab2.textContent).toContain("0");
    });

    it("does not render count when not provided", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      expect(screen.queryByText(/\(\d+\)/)).not.toBeInTheDocument();
    });

    it("renders count with large numbers", () => {
      const tabsWithLargeCount = [
        { id: "tab-1", label: "Tab 1", count: 999 },
      ];
      render(<Tabs tabs={tabsWithLargeCount} active="tab-1" onChange={mockOnChange} />);
      const tab1 = screen.getByTestId("tab-tab-1");
      expect(tab1.textContent).toContain("999");
    });
  });

  describe("className prop", () => {
    it("applies custom className to HeimdallTabBar", () => {
      render(
        <Tabs
          tabs={defaultTabs}
          active="tab-1"
          onChange={mockOnChange}
          className="custom-class"
        />
      );
      const tabBar = screen.getByTestId("heimdall-tab-bar");
      expect(tabBar).toHaveClass("custom-class");
    });

    it("renders without className when not provided", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tabBar = screen.getByTestId("heimdall-tab-bar");
      expect(tabBar.className).toBe("");
    });

    it("applies multiple classes", () => {
      render(
        <Tabs
          tabs={defaultTabs}
          active="tab-1"
          onChange={mockOnChange}
          className="class-1 class-2 class-3"
        />
      );
      const tabBar = screen.getByTestId("heimdall-tab-bar");
      expect(tabBar).toHaveClass("class-1");
      expect(tabBar).toHaveClass("class-2");
      expect(tabBar).toHaveClass("class-3");
    });
  });

  describe("accessibility", () => {
    it("renders tabs with role=tab", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs).toHaveLength(3);
    });

    it("sets aria-selected correctly for all tabs", () => {
      render(<Tabs tabs={defaultTabs} active="tab-2" onChange={mockOnChange} />);
      expect(screen.getByTestId("tab-tab-1")).toHaveAttribute("aria-selected", "false");
      expect(screen.getByTestId("tab-tab-2")).toHaveAttribute("aria-selected", "true");
      expect(screen.getByTestId("tab-tab-3")).toHaveAttribute("aria-selected", "false");
    });

    it("renders tabbar with role=tablist", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tabBar = screen.getByTestId("heimdall-tab-bar");
      expect(tabBar).toHaveAttribute("role", "tablist");
    });
  });

  describe("props forwarding", () => {
    it("forwards tabs to HeimdallTabBar", () => {
      const { container } = render(
        <Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />
      );
      expect(screen.getByText("Tab 1")).toBeInTheDocument();
      expect(screen.getByText("Tab 2")).toBeInTheDocument();
      expect(screen.getByText("Tab 3")).toBeInTheDocument();
    });

    it("forwards activeTabId to HeimdallTabBar", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      const tabBar = screen.getByTestId("heimdall-tab-bar");
      expect(tabBar).toHaveAttribute("data-active", "tab-1");
    });

    it("forwards onSelectTab callback to HeimdallTabBar", () => {
      render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
      screen.getByTestId("tab-tab-2").click();
      expect(mockOnChange).toHaveBeenCalledWith("tab-2");
    });
  });
});
