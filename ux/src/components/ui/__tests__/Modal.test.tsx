import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { Modal } from "../Modal";

describe("Modal", () => {
  describe("visibility", () => {
    it("does not render when open is false", () => {
      const { container } = render(
        <Modal open={false} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal")).not.toBeInTheDocument();
    });

    it("renders when open is true", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal")).toBeInTheDocument();
    });

    it("toggles visibility when open prop changes", () => {
      const { container, rerender } = render(
        <Modal open={false} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );

      expect(container.querySelector(".modal")).not.toBeInTheDocument();

      rerender(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );

      expect(container.querySelector(".modal")).toBeInTheDocument();
    });
  });

  describe("ARIA attributes", () => {
    it("has dialog role", () => {
      render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("has aria-modal attribute", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      const modal = container.querySelector("[role='dialog']");
      expect(modal).toHaveAttribute("aria-modal");
    });

    it("close button has aria-label", () => {
      render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(screen.getByLabelText("Close")).toBeInTheDocument();
    });
  });

  describe("CSS class styling", () => {
    it("applies modal-backdrop class", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal-backdrop")).toBeInTheDocument();
    });

    it("applies modal base class", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal")).toBeInTheDocument();
    });

    it("applies size variant classes", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal" size="lg">
          Content
        </Modal>,
      );
      const modal = container.querySelector(".modal");
      expect(modal).toHaveClass("modal-lg");
    });

    it("applies sm size class", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal" size="sm">
          Content
        </Modal>,
      );
      const modal = container.querySelector(".modal");
      expect(modal).toHaveClass("modal-sm");
    });

    it("applies default md size class", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      const modal = container.querySelector(".modal");
      expect(modal).toHaveClass("modal-md");
    });
  });

  describe("header structure", () => {
    it("renders modal-head class", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Title">
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal-head")).toBeInTheDocument();
    });

    it("renders modal-title", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Test Title">
          Content
        </Modal>,
      );
      const title = container.querySelector(".modal-title");
      expect(title).toBeInTheDocument();
      expect(title).toHaveTextContent("Test Title");
    });

    it("displays title text", () => {
      render(
        <Modal open={true} onClose={vi.fn()} title="Modal Title">
          Content
        </Modal>,
      );
      expect(screen.getByText("Modal Title")).toBeInTheDocument();
    });

    it("renders element title", () => {
      render(
        <Modal open={true} onClose={vi.fn()} title={<strong>Bold Title</strong>}>
          Content
        </Modal>,
      );
      expect(screen.getByText("Bold Title")).toBeInTheDocument();
    });
  });

  describe("subtitle", () => {
    it("renders modal-sub when subtitle provided", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Title" subtitle="Subtitle">
          Content
        </Modal>,
      );
      const sub = container.querySelector(".modal-sub");
      expect(sub).toBeInTheDocument();
      expect(sub).toHaveTextContent("Subtitle");
    });

    it("does not render modal-sub when subtitle not provided", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Title">
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal-sub")).not.toBeInTheDocument();
    });
  });

  describe("content", () => {
    it("renders children in modal-body", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          <p>Modal content</p>
        </Modal>,
      );
      const body = container.querySelector(".modal-body");
      expect(body).toHaveTextContent("Modal content");
    });

    it("renders multiple children", () => {
      render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          <p>First</p>
          <p>Second</p>
        </Modal>,
      );
      expect(screen.getByText("First")).toBeInTheDocument();
      expect(screen.getByText("Second")).toBeInTheDocument();
    });
  });

  describe("footer", () => {
    it("renders modal-foot when footer provided", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal" footer={<button>Save</button>}>
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal-foot")).toBeInTheDocument();
    });

    it("does not render modal-foot when footer not provided", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(container.querySelector(".modal-foot")).not.toBeInTheDocument();
    });

    it("renders footer content", () => {
      render(
        <Modal open={true} onClose={vi.fn()} title="Modal" footer={<button>Save</button>}>
          Content
        </Modal>,
      );
      expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    });
  });

  describe("close button", () => {
    it("renders close button with modal-x class", () => {
      const { container } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      const closeBtn = container.querySelector(".modal-x");
      expect(closeBtn).toBeInTheDocument();
    });

    it("close button calls onClose when clicked", async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(
        <Modal open={true} onClose={onClose} title="Modal">
          Content
        </Modal>,
      );
      const closeBtn = screen.getByLabelText("Close");
      await user.click(closeBtn);
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe("backdrop interactions", () => {
    it("calls onClose when backdrop is clicked", async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      const { container } = render(
        <Modal open={true} onClose={onClose} title="Modal">
          Content
        </Modal>,
      );
      const backdrop = container.querySelector(".modal-backdrop");
      if (backdrop) {
        await user.click(backdrop);
      }
      expect(onClose).toHaveBeenCalled();
    });

    it("does not close when modal content is clicked", async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(
        <Modal open={true} onClose={onClose} title="Modal">
          <button>Inner button</button>
        </Modal>,
      );
      const button = screen.getByRole("button", { name: "Inner button" });
      await user.click(button);
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe("document body overflow", () => {
    it("sets overflow hidden when modal opens", () => {
      render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(document.body.style.overflow).toBe("hidden");
    });

    it("restores overflow when modal closes", () => {
      const { rerender } = render(
        <Modal open={true} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(document.body.style.overflow).toBe("hidden");

      rerender(
        <Modal open={false} onClose={vi.fn()} title="Modal">
          Content
        </Modal>,
      );
      expect(document.body.style.overflow).not.toBe("hidden");
    });
  });
});
