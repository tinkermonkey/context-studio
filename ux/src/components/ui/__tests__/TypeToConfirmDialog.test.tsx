import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { TypeToConfirmDialog } from "../TypeToConfirmDialog";

describe("TypeToConfirmDialog", () => {
  // ========================================================================
  // Render Tests
  // ========================================================================
  describe("rendering", () => {
    it("renders dialog content when open is true", () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete this item"
          message="This action is permanent."
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      expect(screen.getByText("Delete this item")).toBeInTheDocument();
      expect(screen.getByText("This action is permanent.")).toBeInTheDocument();
    });

    it("does not render dialog content when open is false", () => {
      render(
        <TypeToConfirmDialog
          open={false}
          onClose={vi.fn()}
          title="Delete"
          message="Sure?"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      expect(screen.queryByText("Delete")).not.toBeInTheDocument();
    });

    it("displays confirmText in monospace box", () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      expect(screen.getByText("delete")).toBeInTheDocument();
    });

    it("renders input field with placeholder", () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      expect(input).toHaveAttribute("placeholder", "Type the above to confirm");
    });

    it("renders custom confirm button label", () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          confirmLabel="Remove Permanently"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      expect(screen.getByText("Remove Permanently")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Button State Tests
  // ========================================================================
  describe("destructive button state", () => {
    it("disables confirm button initially", () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      expect(confirmButton).toBeDisabled();
    });

    it("enables confirm button when input matches confirmText exactly", async () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      const confirmButton = screen.getByTestId("confirm-dialog-confirm");

      expect(confirmButton).toBeDisabled();

      await userEvent.type(input, "delete");

      expect(confirmButton).not.toBeDisabled();
    });

    it("disables confirm button when input does not match confirmText", async () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      const confirmButton = screen.getByTestId("confirm-dialog-confirm");

      await userEvent.type(input, "wrong");

      expect(confirmButton).toBeDisabled();
    });

    it("disables confirm button when input is partially correct", async () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      const confirmButton = screen.getByTestId("confirm-dialog-confirm");

      await userEvent.type(input, "delet");

      expect(confirmButton).toBeDisabled();
    });

    it("re-disables confirm button when input becomes incorrect", async () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      const confirmButton = screen.getByTestId("confirm-dialog-confirm");

      await userEvent.type(input, "delete");
      expect(confirmButton).not.toBeDisabled();

      await userEvent.type(input, "x");
      expect(confirmButton).toBeDisabled();
    });
  });

  // ========================================================================
  // Interaction Tests
  // ========================================================================
  describe("interactions", () => {
    it("calls onClose when cancel button is clicked", async () => {
      const onClose = vi.fn();
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={onClose}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const cancelButton = screen.getByTestId("confirm-dialog-cancel");
      await userEvent.click(cancelButton);

      expect(onClose).toHaveBeenCalledOnce();
    });

    it("clears input field when cancel is clicked", async () => {
      const onClose = vi.fn();
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={onClose}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input") as HTMLInputElement;
      await userEvent.type(input, "delete");

      expect(input.value).toBe("delete");

      const cancelButton = screen.getByTestId("confirm-dialog-cancel");
      await userEvent.click(cancelButton);

      // Input should be cleared
      expect(input.value).toBe("");
    });

    it("calls onConfirm when confirm button is clicked with matching text", async () => {
      const onConfirm = vi.fn();
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={onConfirm}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      await userEvent.type(input, "delete");

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      expect(onConfirm).toHaveBeenCalledOnce();
    });

    it("does not call onConfirm when confirm button is disabled", async () => {
      const onConfirm = vi.fn();
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={onConfirm}
          onError={vi.fn()}
        />,
      );

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      // Button is disabled, so click should be ignored
      await userEvent.click(confirmButton);

      expect(onConfirm).not.toHaveBeenCalled();
    });

    it("calls onClose after onConfirm completes", async () => {
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      const onClose = vi.fn();

      render(
        <TypeToConfirmDialog
          open={true}
          onClose={onClose}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={onConfirm}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      await userEvent.type(input, "delete");

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
        <TypeToConfirmDialog
          open={true}
          onClose={onClose}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
        />,
      );

      await userEvent.keyboard("{Escape}");

      expect(onClose).toHaveBeenCalledOnce();
    });

    it("triggers confirm on Enter key when input matches", async () => {
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      const onClose = vi.fn();

      render(
        <TypeToConfirmDialog
          open={true}
          onClose={onClose}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={onConfirm}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      await userEvent.type(input, "delete");
      await userEvent.keyboard("{Enter}");

      await waitFor(() => {
        expect(onConfirm).toHaveBeenCalled();
      });

      expect(onClose).toHaveBeenCalled();
    });

    it("does not trigger confirm on Enter when input does not match", async () => {
      const onConfirm = vi.fn();

      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={onConfirm}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input");
      await userEvent.type(input, "wrong{Enter}");

      expect(onConfirm).not.toHaveBeenCalled();
    });

    it("clears input after successful confirmation", async () => {
      const onConfirm = vi.fn().mockResolvedValue(undefined);

      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={onConfirm}
          onError={vi.fn()}
        />,
      );

      const input = screen.getByTestId("type-confirm-input") as HTMLInputElement;
      await userEvent.type(input, "delete");

      const confirmButton = screen.getByTestId("confirm-dialog-confirm");
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(onConfirm).toHaveBeenCalled();
      });

      // Input should be cleared after confirmation
      expect(input.value).toBe("");
    });

    it("disables buttons when isLoading is true", () => {
      render(
        <TypeToConfirmDialog
          open={true}
          onClose={vi.fn()}
          title="Delete"
          message="Type 'delete' to confirm"
          confirmText="delete"
          onConfirm={vi.fn()}
          onError={vi.fn()}
          isLoading={true}
        />,
      );

      const cancelButton = screen.getByTestId("confirm-dialog-cancel");
      const confirmButton = screen.getByTestId("confirm-dialog-confirm");

      expect(cancelButton).toBeDisabled();
      expect(confirmButton).toBeDisabled();
    });
  });
});
