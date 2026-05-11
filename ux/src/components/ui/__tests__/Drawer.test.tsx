import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { Drawer } from "../Drawer";

describe("Drawer", () => {
  describe("visibility", () => {
    it("does not render when open is false", () => {
      const { container } = render(
        <Drawer open={false} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      expect(container.querySelector(".drawer")).not.toBeInTheDocument();
    });

    it("renders when open is true", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      expect(container.querySelector(".drawer")).toBeInTheDocument();
    });

    it("toggles visibility when open prop changes", () => {
      const { container, rerender } = render(
        <Drawer open={false} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );

      expect(container.querySelector(".drawer")).not.toBeInTheDocument();

      rerender(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );

      expect(container.querySelector(".drawer")).toBeInTheDocument();
    });
  });

  describe("CSS class styling", () => {
    it("applies drawer class", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      expect(container.querySelector(".drawer")).toBeInTheDocument();
    });

    it("renders drawer-head", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      expect(container.querySelector(".drawer-head")).toBeInTheDocument();
    });

    it("renders drawer-body", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      expect(container.querySelector(".drawer-body")).toBeInTheDocument();
    });
  });

  describe("header", () => {
    it("renders title", () => {
      render(
        <Drawer open={true} onClose={vi.fn()} title="My Title">
          Content
        </Drawer>,
      );
      expect(screen.getByText("My Title")).toBeInTheDocument();
    });

    it("renders element title", () => {
      render(
        <Drawer open={true} onClose={vi.fn()} title={<strong>Bold</strong>}>
          Content
        </Drawer>,
      );
      expect(screen.getByText("Bold")).toBeInTheDocument();
    });

    it("renders drawer-actions container", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Title">
          Content
        </Drawer>,
      );
      expect(container.querySelector(".drawer-actions")).toBeInTheDocument();
    });

    it("renders close button with modal-x class", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Title">
          Content
        </Drawer>,
      );
      expect(container.querySelector(".modal-x")).toBeInTheDocument();
    });

    it("close button has aria-label", () => {
      render(
        <Drawer open={true} onClose={vi.fn()} title="Title">
          Content
        </Drawer>,
      );
      expect(screen.getByLabelText("Close drawer")).toBeInTheDocument();
    });
  });

  describe("content", () => {
    it("renders children in drawer-body", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          <p>Drawer content</p>
        </Drawer>,
      );
      const body = container.querySelector(".drawer-body");
      expect(body).toHaveTextContent("Drawer content");
    });
  });

  describe("autosave status", () => {
    it("does not render autosave status when autosaveState is idle", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          autosaveState="idle"
        >
          Content
        </Drawer>,
      );
      expect(screen.queryByTestId("drawer-autosave-status")).not.toBeInTheDocument();
    });

    it("renders drawer-autosave-status when autosaveState is saving", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          autosaveState="saving"
        >
          Content
        </Drawer>,
      );
      expect(screen.getByTestId("drawer-autosave-status")).toBeInTheDocument();
      expect(screen.getByText("Saving…")).toBeInTheDocument();
    });

    it("renders autosave status when autosaveState is saved", () => {
      const now = new Date();
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          autosaveState="saved"
          lastSavedAt={now}
        >
          Content
        </Drawer>,
      );
      expect(screen.getByTestId("drawer-autosave-status")).toBeInTheDocument();
      expect(screen.getByText(/Saved/)).toBeInTheDocument();
    });

    it("renders autosave status when autosaveState is error", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          autosaveState="error"
        >
          Content
        </Drawer>,
      );
      expect(screen.getByTestId("drawer-autosave-status")).toBeInTheDocument();
      expect(screen.getByText("Save failed")).toBeInTheDocument();
    });
  });

  describe("revert button", () => {
    it("does not render revert button by default", () => {
      render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      expect(
        screen.queryByRole("button", { name: "Revert" }),
      ).not.toBeInTheDocument();
    });

    it("renders revert button when isDirty and onRevert provided", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          isDirty={true}
          onRevert={vi.fn()}
        >
          Content
        </Drawer>,
      );
      expect(screen.getByTestId("drawer-revert-button")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Revert" })).toBeInTheDocument();
    });

    it("revert button has ghost variant", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          isDirty={true}
          onRevert={vi.fn()}
        >
          Content
        </Drawer>,
      );
      const button = screen.getByTestId("drawer-revert-button");
      expect(button).toHaveClass("btn-ghost");
      expect(button).toHaveClass("btn-sm");
    });

    it("calls onRevert when revert button clicked", async () => {
      const onRevert = vi.fn();
      const user = userEvent.setup();
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          isDirty={true}
          onRevert={onRevert}
        >
          Content
        </Drawer>,
      );
      const button = screen.getByTestId("drawer-revert-button");
      await user.click(button);
      expect(onRevert).toHaveBeenCalled();
    });

    it("does not render revert button when isDirty is false", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          isDirty={false}
          onRevert={vi.fn()}
        >
          Content
        </Drawer>,
      );
      expect(
        screen.queryByRole("button", { name: "Revert" }),
      ).not.toBeInTheDocument();
    });
  });

  describe("delete button", () => {
    it("does not render delete button by default", () => {
      render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      expect(
        screen.queryByRole("button", { name: "Delete" }),
      ).not.toBeInTheDocument();
    });

    it("renders delete button when onDelete provided", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          onDelete={vi.fn()}
        >
          Content
        </Drawer>,
      );
      expect(screen.getByTestId("drawer-delete-button")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });

    it("delete button has danger variant", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          onDelete={vi.fn()}
        >
          Content
        </Drawer>,
      );
      const button = screen.getByTestId("drawer-delete-button");
      expect(button).toHaveClass("btn-danger");
      expect(button).toHaveClass("btn-sm");
    });

    it("calls onDelete when delete button clicked", async () => {
      const onDelete = vi.fn();
      const user = userEvent.setup();
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          onDelete={onDelete}
        >
          Content
        </Drawer>,
      );
      const button = screen.getByTestId("drawer-delete-button");
      await user.click(button);
      expect(onDelete).toHaveBeenCalled();
    });
  });

  describe("header action", () => {
    it("renders headerAction when provided", () => {
      render(
        <Drawer
          open={true}
          onClose={vi.fn()}
          title="Drawer"
          headerAction={<span>Custom action</span>}
        >
          Content
        </Drawer>,
      );
      expect(screen.getByText("Custom action")).toBeInTheDocument();
    });

    it("does not render headerAction when not provided", () => {
      const { container } = render(
        <Drawer open={true} onClose={vi.fn()} title="Drawer">
          Content
        </Drawer>,
      );
      const actions = container.querySelector(".drawer-actions");
      expect(actions).not.toHaveTextContent("Custom action");
    });
  });

  describe("close interactions", () => {
    it("calls onClose when close button is clicked", async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(
        <Drawer open={true} onClose={onClose} title="Drawer">
          Content
        </Drawer>,
      );
      const closeBtn = screen.getByLabelText("Close drawer");
      await user.click(closeBtn);
      expect(onClose).toHaveBeenCalled();
    });
  });
});
