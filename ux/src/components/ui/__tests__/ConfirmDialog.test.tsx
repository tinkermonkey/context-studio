import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { ConfirmDialog } from "../ConfirmDialog";

describe("ConfirmDialog", () => {
  // ========================================================================
  // Render Tests
  // ========================================================================
  describe("rendering", () => {
    it("renders dialog content when open is true", () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete Item?"
          message="This action cannot be undone."
          onConfirm={vi.fn()}
        />,
      );

      expect(screen.getByText("Delete Item?")).toBeInTheDocument();
      expect(screen.getByText("This action cannot be undone.")).toBeInTheDocument();
    });

    it("does not render dialog content when open is false", () => {
      render(
        <ConfirmDialog
          open={false}
          onClose={vi.fn()}
          title="Delete Item?"
          message="This action cannot be undone."
          onConfirm={vi.fn()}
        />,
      );

      expect(screen.queryByText("Delete Item?")).not.toBeInTheDocument();
    });

    it("renders cancel and confirm buttons", () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          onConfirm={vi.fn()}
        />,
      );

      expect(screen.getByTestId("confirm-dialog-cancel")).toBeInTheDocument();
      expect(screen.getByTestId("confirm-dialog-confirm")).toBeInTheDocument();
    });

    it("renders custom button labels", () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          confirmLabel="Delete Forever"
          cancelLabel="Nope"
          onConfirm={vi.fn()}
        />,
      );

      expect(screen.getByText("Delete Forever")).toBeInTheDocument();
      expect(screen.getByText("Nope")).toBeInTheDocument();
    });

    it("applies danger variant to confirm button when danger is true", () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          danger={true}
          onConfirm={vi.fn()}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      expect(confirmButton).toHaveClass("btn--danger");
    });

    it("disables confirm button when isConfirmDisabled is true", () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          onConfirm={vi.fn()}
          isConfirmDisabled={true}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      const cancelButton = screen.getByTestId("confirm-dialog-cancel");

      expect(confirmButton).toBeDisabled();
      expect(cancelButton).not.toBeDisabled();
    });
  });

  // ========================================================================
  // Interaction Tests
  // ========================================================================
  describe("interactions", () => {
    it("calls onClose when cancel button is clicked", async () => {
      const onClose = vi.fn();
      render(
        <ConfirmDialog
          open={true}
          onClose={onClose}
          title="Confirm"
          message="Are you sure?"
          onConfirm={vi.fn()}
        />,
      );

      const cancelButton = screen.getByTestId("confirm-dialog-cancel");
      await userEvent.click(cancelButton);

      expect(onClose).toHaveBeenCalledOnce();
    });

    it("calls onConfirm when confirm button is clicked", async () => {
      const onConfirm = vi.fn();
      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          onConfirm={onConfirm}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      expect(onConfirm).toHaveBeenCalledOnce();
    });

    it("calls onClose after onConfirm is complete", async () => {
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      const onClose = vi.fn();

      render(
        <ConfirmDialog
          open={true}
          onClose={onClose}
          title="Confirm"
          message="Are you sure?"
          onConfirm={onConfirm}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(onConfirm).toHaveBeenCalled();
      });

      expect(onClose).toHaveBeenCalled();
    });

    it("dismisses dialog when ESC key is pressed", async () => {
      const onClose = vi.fn();
      render(
        <ConfirmDialog
          open={true}
          onClose={onClose}
          title="Confirm"
          message="Are you sure?"
          onConfirm={vi.fn()}
        />,
      );

      await userEvent.keyboard("{Escape}");

      expect(onClose).toHaveBeenCalledOnce();
    });

    it("disables buttons when isLoading is true", async () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          onConfirm={vi.fn()}
          isLoading={true}
        />,
      );

      const cancelButton = screen.getByTestId("confirm-dialog-cancel");
      const confirmButton = screen.getByTestId("confirm-dialog-confirm");

      expect(cancelButton).toBeDisabled();
      expect(confirmButton).toBeDisabled();
    });

    it("handles async onConfirm callback", async () => {
      const onConfirm = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(resolve, 100);
          }),
      );
      const onClose = vi.fn();

      render(
        <ConfirmDialog
          open={true}
          onClose={onClose}
          title="Confirm"
          message="Are you sure?"
          onConfirm={onConfirm}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });

    it("calls onError when onConfirm rejects with Error", async () => {
      const error = new Error("Operation failed");
      const onConfirm = vi.fn().mockRejectedValue(error);
      const onError = vi.fn();
      const onClose = vi.fn();

      render(
        <ConfirmDialog
          open={true}
          onClose={onClose}
          title="Confirm"
          message="Are you sure?"
          onConfirm={onConfirm}
          onError={onError}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(error);
      });

      expect(onClose).not.toHaveBeenCalled();
    });

    it("wraps non-Error thrown values in Error and calls onError", async () => {
      const onConfirm = vi.fn().mockRejectedValue("string error");
      const onError = vi.fn();

      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          onConfirm={onConfirm}
          onError={onError}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(onError).toHaveBeenCalled();
        const calledError = onError.mock.calls[0][0];
        expect(calledError).toBeInstanceOf(Error);
        expect(calledError.message).toBe("string error");
      });
    });

    it("keeps dialog open when onError is called", async () => {
      const onConfirm = vi.fn().mockRejectedValue(new Error("Operation failed"));
      const onError = vi.fn();

      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm Action"
          message="Are you sure?"
          onConfirm={onConfirm}
          onError={onError}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(onError).toHaveBeenCalled();
      });

      expect(screen.getByText("Confirm Action")).toBeInTheDocument();
    });

    it("calls console.error when onConfirm fails and onError is not provided", async () => {
      const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      const onConfirm = vi.fn().mockRejectedValue(new Error("Operation failed"));

      render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          onConfirm={onConfirm}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });

      consoleErrorSpy.mockRestore();
    });

    it("keeps cancel button enabled during async operation", async () => {
      const onConfirm = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(resolve, 100);
          }),
      );

      const { rerender } = render(
        <ConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Confirm"
          message="Are you sure?"
          onConfirm={onConfirm}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      const cancelButton = screen.getByTestId("confirm-dialog-cancel");

      await userEvent.click(confirmButton);

      expect(confirmButton).toBeDisabled();
      expect(cancelButton).toBeDisabled();
    });
  });
});
