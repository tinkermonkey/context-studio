import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { BulkBar } from "../BulkBar";

const defaultActions = [{ id: "delete", label: "Delete", danger: true, icon: "trash" as const }];

describe("BulkBar", () => {
  describe("visibility", () => {
    it("renders nothing when count is 0", () => {
      render(
        <BulkBar
          count={0}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.queryByTestId("bulk-bar")).not.toBeInTheDocument();
    });

    it("renders when count is greater than 0", () => {
      render(
        <BulkBar
          count={3}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.getByTestId("bulk-bar")).toBeInTheDocument();
    });
  });

  describe("CSS classes", () => {
    it("root has csb-bar class", () => {
      const { container } = render(
        <BulkBar
          count={2}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(container.querySelector(".csb-bar")).toBeInTheDocument();
    });

    it("count badge has csb-bar__badge class", () => {
      const { container } = render(
        <BulkBar
          count={2}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(container.querySelector(".csb-bar__badge")).toBeInTheDocument();
    });
  });

  describe("ARIA roles", () => {
    it("root has toolbar role", () => {
      render(
        <BulkBar
          count={2}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.getByRole("toolbar")).toBeInTheDocument();
    });

    it("separators have separator role", () => {
      render(
        <BulkBar
          count={2}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.getAllByRole("separator").length).toBeGreaterThan(0);
    });

    it("clear button has aria-label", () => {
      render(
        <BulkBar
          count={2}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.getByRole("button", { name: "Clear selection" })).toBeInTheDocument();
    });
  });

  describe("content", () => {
    it("shows selected count badge", () => {
      render(
        <BulkBar
          count={5}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.getByText("5")).toBeInTheDocument();
    });

    it("pluralizes entity label for count > 1", () => {
      render(
        <BulkBar
          count={3}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.getByText(/Taxonomies selected/)).toBeInTheDocument();
    });

    it("keeps singular entity label for count === 1", () => {
      render(
        <BulkBar
          count={1}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={vi.fn()}
        />,
      );
      expect(screen.getByText(/Taxonomy selected/)).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("calls onAction with action id on action button click", async () => {
      const user = userEvent.setup();
      const onAction = vi.fn();
      render(
        <BulkBar
          count={2}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={onAction}
          onClear={vi.fn()}
        />,
      );
      await user.click(screen.getByTestId("bulk-action-delete"));
      expect(onAction).toHaveBeenCalledWith("delete");
    });

    it("calls onClear when clear button is clicked", async () => {
      const user = userEvent.setup();
      const onClear = vi.fn();
      render(
        <BulkBar
          count={2}
          entityLabel="Taxonomy"
          actions={defaultActions}
          onAction={vi.fn()}
          onClear={onClear}
        />,
      );
      await user.click(screen.getByTestId("bulk-bar-clear"));
      expect(onClear).toHaveBeenCalled();
    });
  });
});
