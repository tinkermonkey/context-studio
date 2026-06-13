import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { CascadeDeleteDialog, type CascadeImpactData } from "../CascadeDeleteDialog";

const target = { id: "tax_abc", label: "My Taxonomy" };

const zeroImpact: CascadeImpactData = {
  totalCount: 0,
  stats: [],
  items: [],
};

const nonZeroImpact: CascadeImpactData = {
  totalCount: 3,
  stats: [
    { label: "Schemes", count: 2 },
    { label: "Classes", count: 1 },
  ],
  items: [
    { type: "scheme", label: "Scheme A", id: "sch_001" },
    { type: "scheme", label: "Scheme B", id: "sch_002" },
    { type: "class", label: "Class X", id: "cls_001" },
  ],
};

describe("CascadeDeleteDialog", () => {
  describe("data-testid presence", () => {
    it("has cascade-delete-dialog testid on modal", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-delete-dialog")).toBeInTheDocument();
    });

    it("has cascade-delete-content testid on body", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-delete-content")).toBeInTheDocument();
    });

    it("cancel button has cascade-delete-cancel testid", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-delete-cancel")).toBeInTheDocument();
    });

    it("confirm button has cascade-delete-confirm testid", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-delete-confirm")).toBeInTheDocument();
    });
  });

  describe("single entity title", () => {
    it("shows entity label in title", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByText('Delete "My Taxonomy"?')).toBeInTheDocument();
    });
  });

  describe("bulk delete title", () => {
    it("shows count and pluralized entity type in title", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          ids={["1", "2", "3"]}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByText("Delete 3 Taxonomies?")).toBeInTheDocument();
    });
  });

  describe("zero-impact state", () => {
    it("shows safe-to-remove callout", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByText(/Safe to remove/)).toBeInTheDocument();
    });

    it("does not show impact summary", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.queryByTestId("cascade-impact-summary")).not.toBeInTheDocument();
    });

    it("shows plain Delete label on confirm button", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-delete-confirm")).toHaveTextContent("Delete");
    });
  });

  describe("non-zero impact state", () => {
    it("shows warning callout", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={nonZeroImpact}
        />,
      );
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    it("shows impact summary", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={nonZeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-impact-summary")).toBeInTheDocument();
    });

    it("renders stat counts from impactData stats", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={nonZeroImpact}
        />,
      );
      expect(screen.getByText("Schemes")).toBeInTheDocument();
      expect(screen.getByText("Classes")).toBeInTheDocument();
    });

    it("shows affected items list", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={nonZeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-impact-items")).toBeInTheDocument();
      expect(screen.getByText("Scheme A")).toBeInTheDocument();
    });

    it("shows dependent count in confirm button label", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={nonZeroImpact}
        />,
      );
      expect(screen.getByTestId("cascade-delete-confirm")).toHaveTextContent(
        "Delete (+ 3 dependents)",
      );
    });

    it("caps the item list at 60 items", () => {
      const largeImpact: CascadeImpactData = {
        totalCount: 80,
        stats: [{ label: "Items", count: 80 }],
        items: Array.from({ length: 80 }, (_, i) => ({
          type: "class",
          label: `Class ${i + 1}`,
          id: `cls_${i + 1}`,
        })),
      };
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={largeImpact}
        />,
      );
      const items = screen.getAllByText(/Class \d+/);
      expect(items.length).toBe(60);
    });
  });

  describe("CSS classes", () => {
    it("content area has ce-cascade class", () => {
      const { container } = render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={nonZeroImpact}
        />,
      );
      expect(container.querySelector(".ce-cascade")).toBeInTheDocument();
    });

    it("stat items have ce-cascade__stat class", () => {
      const { container } = render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={nonZeroImpact}
        />,
      );
      expect(container.querySelectorAll(".ce-cascade__stat").length).toBe(2);
    });
  });

  describe("interactions", () => {
    it("calls onClose when Cancel is clicked", async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={onClose}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      await user.click(screen.getByTestId("cascade-delete-cancel"));
      expect(onClose).toHaveBeenCalled();
    });

    it("calls onConfirm when Delete is clicked", async () => {
      const user = userEvent.setup();
      const onConfirm = vi.fn();
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={onConfirm}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
        />,
      );
      await user.click(screen.getByTestId("cascade-delete-confirm"));
      expect(onConfirm).toHaveBeenCalled();
    });

    it("disables buttons while deleting", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
          isDeleting={true}
        />,
      );
      expect(screen.getByTestId("cascade-delete-cancel")).toBeDisabled();
      expect(screen.getByTestId("cascade-delete-confirm")).toBeDisabled();
    });

    it("shows Deleting… label while deleting", () => {
      render(
        <CascadeDeleteDialog
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          target={target}
          entityType="Taxonomy"
          impactData={zeroImpact}
          isDeleting={true}
        />,
      );
      expect(screen.getByTestId("cascade-delete-confirm")).toHaveTextContent("Deleting…");
    });
  });
});
