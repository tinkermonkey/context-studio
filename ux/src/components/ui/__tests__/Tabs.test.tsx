import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@/test/test-utils";
import { screen } from "@testing-library/react";
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

  it("forwards tabs prop to HeimdallTabBar", () => {
    render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
    expect(screen.getByText("Tab 1")).toBeInTheDocument();
    expect(screen.getByText("Tab 2")).toBeInTheDocument();
    expect(screen.getByText("Tab 3")).toBeInTheDocument();
  });

  it("forwards active prop as activeTabId to HeimdallTabBar", () => {
    render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
    const tabBar = screen.getByTestId("heimdall-tab-bar");
    expect(tabBar).toHaveAttribute("data-active", "tab-1");
  });

  it("forwards onChange callback as onSelectTab to HeimdallTabBar", () => {
    render(<Tabs tabs={defaultTabs} active="tab-1" onChange={mockOnChange} />);
    screen.getByTestId("tab-tab-2").click();
    expect(mockOnChange).toHaveBeenCalledWith("tab-2");
  });

  it("forwards className prop to HeimdallTabBar", () => {
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

  it("handles empty tabs array", () => {
    render(<Tabs tabs={[]} active="" onChange={mockOnChange} />);
    expect(screen.getByTestId("heimdall-tab-bar")).toBeInTheDocument();
    const tabs = screen.queryAllByRole("tab");
    expect(tabs).toHaveLength(0);
  });
});
