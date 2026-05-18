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

  describe("tab rendering", () => {
    it("renders all tab labels", () => {
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      expect(screen.getByText("Tab 1")).toBeInTheDocument();
      expect(screen.getByText("Tab 2")).toBeInTheDocument();
      expect(screen.getByText("Tab 3")).toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    it("renders tablist role on container", () => {
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      expect(screen.getByRole("tablist")).toBeInTheDocument();
    });

    it("renders tabs with tab role", () => {
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs.length).toBe(3);
    });

    it("active tab has aria-selected true", () => {
      render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs[0]).toHaveAttribute("aria-selected", "true");
      expect(tabs[1]).toHaveAttribute("aria-selected", "false");
      expect(tabs[2]).toHaveAttribute("aria-selected", "false");
    });

    it("inactive tabs have aria-selected false", () => {
      render(<Tabs tabs={mockTabs} active="tab-2" onChange={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs[0]).toHaveAttribute("aria-selected", "false");
      expect(tabs[1]).toHaveAttribute("aria-selected", "true");
      expect(tabs[2]).toHaveAttribute("aria-selected", "false");
    });

    it("aria-selected updates when active tab changes", () => {
      const { rerender } = render(<Tabs tabs={mockTabs} active="tab-1" onChange={vi.fn()} />);
      const tabs = screen.getAllByRole("tab");
      expect(tabs[0]).toHaveAttribute("aria-selected", "true");
      expect(tabs[1]).toHaveAttribute("aria-selected", "false");

      rerender(<Tabs tabs={mockTabs} active="tab-2" onChange={vi.fn()} />);
      const updatedTabs = screen.getAllByRole("tab");
      expect(updatedTabs[0]).toHaveAttribute("aria-selected", "false");
      expect(updatedTabs[1]).toHaveAttribute("aria-selected", "true");
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
  });

  describe("empty state", () => {
    it("renders tablist when no tabs provided", () => {
      render(<Tabs tabs={[]} active="" onChange={vi.fn()} />);
      expect(screen.getByRole("tablist")).toBeInTheDocument();
    });
  });
});
