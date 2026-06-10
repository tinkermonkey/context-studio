import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { InlineInspector } from "../InlineInspector";

const defaultProps = {
  eyebrow: "Taxonomy",
  title: "Animals",
  mode: "view" as const,
  onEdit: vi.fn(),
  onDone: vi.fn(),
  onDelete: vi.fn(),
};

describe("InlineInspector", () => {
  describe("rendering", () => {
    it("applies data-testid to root element", () => {
      const { container } = render(
        <InlineInspector {...defaultProps} data-testid="my-inspector">
          Content
        </InlineInspector>,
      );
      expect(container.querySelector('[data-testid="my-inspector"]')).toHaveClass(
        "inline-inspector",
      );
    });

    it("renders eyebrow text", () => {
      render(<InlineInspector {...defaultProps}>Content</InlineInspector>);
      expect(screen.getByText("Taxonomy")).toBeInTheDocument();
    });

    it("renders title text", () => {
      render(<InlineInspector {...defaultProps}>Content</InlineInspector>);
      expect(screen.getByText("Animals")).toBeInTheDocument();
    });

    it("renders children", () => {
      render(
        <InlineInspector {...defaultProps}>
          <p>Inspector body</p>
        </InlineInspector>,
      );
      expect(screen.getByText("Inspector body")).toBeInTheDocument();
    });
  });

  describe("view mode actions", () => {
    it("shows edit button", () => {
      render(<InlineInspector {...defaultProps} mode="view">Content</InlineInspector>);
      expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
    });

    it("shows row menu", () => {
      render(<InlineInspector {...defaultProps} mode="view">Content</InlineInspector>);
      expect(screen.getByTestId("inline-inspector-row-menu")).toBeInTheDocument();
    });

    it("edit button calls onEdit", async () => {
      const onEdit = vi.fn();
      const user = userEvent.setup();
      render(
        <InlineInspector {...defaultProps} mode="view" onEdit={onEdit}>
          Content
        </InlineInspector>,
      );
      await user.click(screen.getByTestId("inline-inspector-edit-button"));
      expect(onEdit).toHaveBeenCalled();
    });

    it("row menu edit action calls onEdit", async () => {
      const onEdit = vi.fn();
      const user = userEvent.setup();
      const { container } = render(
        <InlineInspector {...defaultProps} mode="view" onEdit={onEdit}>
          Content
        </InlineInspector>,
      );
      await user.click(container.querySelector('[data-action="edit"]')!);
      expect(onEdit).toHaveBeenCalled();
    });

    it("row menu delete action calls onDelete", async () => {
      const onDelete = vi.fn();
      const user = userEvent.setup();
      const { container } = render(
        <InlineInspector {...defaultProps} mode="view" onDelete={onDelete}>
          Content
        </InlineInspector>,
      );
      await user.click(container.querySelector('[data-action="delete"]')!);
      expect(onDelete).toHaveBeenCalled();
    });

    it("row menu duplicate action calls onDuplicate when provided", async () => {
      const onDuplicate = vi.fn();
      const user = userEvent.setup();
      const { container } = render(
        <InlineInspector {...defaultProps} mode="view" onDuplicate={onDuplicate}>
          Content
        </InlineInspector>,
      );
      await user.click(container.querySelector('[data-action="duplicate"]')!);
      expect(onDuplicate).toHaveBeenCalled();
    });

    it("does not render duplicate menu item when onDuplicate is not provided", () => {
      const { container } = render(
        <InlineInspector {...defaultProps} mode="view">
          Content
        </InlineInspector>,
      );
      expect(container.querySelector('[data-action="duplicate"]')).not.toBeInTheDocument();
    });
  });

  describe("edit mode actions", () => {
    it("shows Done button", () => {
      render(<InlineInspector {...defaultProps} mode="edit">Content</InlineInspector>);
      expect(screen.getByTestId("inline-inspector-done-button")).toBeInTheDocument();
    });

    it("Done button calls onDone", async () => {
      const onDone = vi.fn();
      const user = userEvent.setup();
      render(
        <InlineInspector {...defaultProps} mode="edit" onDone={onDone}>
          Content
        </InlineInspector>,
      );
      await user.click(screen.getByTestId("inline-inspector-done-button"));
      expect(onDone).toHaveBeenCalled();
    });

    it("does not show inline edit button in edit mode", () => {
      render(<InlineInspector {...defaultProps} mode="edit">Content</InlineInspector>);
      expect(screen.queryByTestId("inline-inspector-edit-button")).not.toBeInTheDocument();
    });

    it("does not show row menu in edit mode", () => {
      render(<InlineInspector {...defaultProps} mode="edit">Content</InlineInspector>);
      expect(screen.queryByTestId("inline-inspector-row-menu")).not.toBeInTheDocument();
    });
  });

  describe("edit note", () => {
    it("shows default edit note in edit mode", () => {
      render(<InlineInspector {...defaultProps} mode="edit">Content</InlineInspector>);
      expect(screen.getByRole("note")).toHaveTextContent(
        "Editing — fields save automatically",
      );
    });

    it("shows custom editNote in edit mode", () => {
      render(
        <InlineInspector {...defaultProps} mode="edit" editNote="Auto-saving changes">
          Content
        </InlineInspector>,
      );
      expect(screen.getByRole("note")).toHaveTextContent("Auto-saving changes");
    });

    it("does not show edit note when editNote is false", () => {
      render(
        <InlineInspector {...defaultProps} mode="edit" editNote={false}>
          Content
        </InlineInspector>,
      );
      expect(screen.queryByRole("note")).not.toBeInTheDocument();
    });

    it("does not show edit note in view mode", () => {
      render(<InlineInspector {...defaultProps} mode="view">Content</InlineInspector>);
      expect(screen.queryByRole("note")).not.toBeInTheDocument();
    });
  });

  describe("autosave status", () => {
    it("renders autosave status container in edit mode", () => {
      render(<InlineInspector {...defaultProps} mode="edit">Content</InlineInspector>);
      expect(screen.getByTestId("inspector-autosave-status")).toBeInTheDocument();
    });

    it("shows saving spinner when autosaveStatus is saving", () => {
      const { container } = render(
        <InlineInspector {...defaultProps} mode="edit" autosaveStatus="saving">
          Content
        </InlineInspector>,
      );
      expect(container.querySelector(".spin")).toBeInTheDocument();
    });

    it("shows saved text when autosaveStatus is saved with a timestamp", () => {
      const savedAt = new Date(Date.now() - 5000);
      render(
        <InlineInspector
          {...defaultProps}
          mode="edit"
          autosaveStatus="saved"
          lastSavedAt={savedAt}
        >
          Content
        </InlineInspector>,
      );
      expect(screen.getByText(/Saved/)).toBeInTheDocument();
    });

    it("shows error icon when autosaveStatus is error", () => {
      const { container } = render(
        <InlineInspector {...defaultProps} mode="edit" autosaveStatus="error">
          Content
        </InlineInspector>,
      );
      expect(container.querySelector(".autosave-icon-error")).toBeInTheDocument();
    });
  });
});
