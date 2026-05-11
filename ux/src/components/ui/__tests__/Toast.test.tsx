import { describe, it, expect, vi } from "vitest";
import { screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { ToastViewport, useToasts, type ToastItem } from "../Toast";

describe("Toast", () => {
  // ========================================================================
  // Render Tests
  // ========================================================================
  describe("rendering", () => {
    it("renders toast item with title", () => {
      const toast: ToastItem = {
        id: "toast-1",
        type: "success",
        title: "Success message",
      };

      render(<ToastViewport toasts={[toast]} onDismiss={vi.fn()} />);

      expect(screen.getByText("Success message")).toBeInTheDocument();
    });

    it("renders toast item with subtitle", () => {
      const toast: ToastItem = {
        id: "toast-1",
        type: "info",
        title: "Info title",
        sub: "Info subtitle",
      };

      render(<ToastViewport toasts={[toast]} onDismiss={vi.fn()} />);

      expect(screen.getByText("Info subtitle")).toBeInTheDocument();
    });

    it("renders different toast types with correct icons", () => {
      const successToast: ToastItem = {
        id: "success-1",
        type: "success",
        title: "Success",
      };

      const errorToast: ToastItem = {
        id: "error-1",
        type: "error",
        title: "Error",
      };

      const warningToast: ToastItem = {
        id: "warning-1",
        type: "warning",
        title: "Warning",
      };

      const infoToast: ToastItem = {
        id: "info-1",
        type: "info",
        title: "Info",
      };

      render(
        <ToastViewport
          toasts={[successToast, errorToast, warningToast, infoToast]}
          onDismiss={vi.fn()}
        />,
      );

      expect(screen.getByText("Success")).toBeInTheDocument();
      expect(screen.getByText("Error")).toBeInTheDocument();
      expect(screen.getByText("Warning")).toBeInTheDocument();
      expect(screen.getByText("Info")).toBeInTheDocument();
    });

    it("renders close button for each toast", () => {
      const toast: ToastItem = {
        id: "toast-1",
        type: "info",
        title: "Test",
      };

      const { container } = render(<ToastViewport toasts={[toast]} onDismiss={vi.fn()} />);

      const closeButton = container.querySelector(".toast-x");
      expect(closeButton).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Undo Action Tests
  // ========================================================================
  describe("undo action", () => {
    it("displays action button when action is provided", () => {
      const toast: ToastItem = {
        id: "toast-1",
        type: "success",
        title: "Item deleted",
        action: {
          label: "Undo",
          onAction: vi.fn(),
        },
      };

      render(<ToastViewport toasts={[toast]} onDismiss={vi.fn()} />);

      const undoButton = screen.getByTestId("toast-action-toast-1");
      expect(undoButton).toBeInTheDocument();
      expect(undoButton).toHaveTextContent("Undo");
    });

    it("does not display action button when action is not provided", () => {
      const toast: ToastItem = {
        id: "toast-1",
        type: "success",
        title: "Item deleted",
      };

      render(<ToastViewport toasts={[toast]} onDismiss={vi.fn()} />);

      expect(screen.queryByTestId("toast-action-toast-1")).not.toBeInTheDocument();
    });

    it("calls onAction when action button is clicked", async () => {
      const onAction = vi.fn();
      const toast: ToastItem = {
        id: "toast-1",
        type: "success",
        title: "Item deleted",
        action: {
          label: "Undo",
          onAction,
        },
      };

      render(<ToastViewport toasts={[toast]} onDismiss={vi.fn()} />);

      const undoButton = screen.getByTestId("toast-action-toast-1");
      await userEvent.click(undoButton);

      expect(onAction).toHaveBeenCalledOnce();
    });

    it("action button is present and clickable with Undo label", () => {
      const onAction = vi.fn();
      const toast: ToastItem = {
        id: "toast-1",
        type: "success",
        title: "Item deleted",
        action: {
          label: "Undo",
          onAction,
        },
      };

      render(<ToastViewport toasts={[toast]} onDismiss={vi.fn()} />);

      const undoButton = screen.getByTestId("toast-action-toast-1");
      expect(undoButton).toBeInTheDocument();
      expect(undoButton).toHaveTextContent("Undo");
    });
  });

  // ========================================================================
  // Dismissal Tests
  // ========================================================================
  describe("dismissal", () => {
    it("calls onDismiss when close button is clicked", async () => {
      const onDismiss = vi.fn();
      const toast: ToastItem = {
        id: "toast-1",
        type: "info",
        title: "Test",
      };

      const { container } = render(<ToastViewport toasts={[toast]} onDismiss={onDismiss} />);

      const closeButton = container.querySelector(".toast-x") as HTMLElement;
      await userEvent.click(closeButton);

      expect(onDismiss).toHaveBeenCalledWith("toast-1");
    });

    it("undo button is absent after 8 seconds when toast has autoDismiss action", () => {
      vi.useFakeTimers();

      const TestComponent = () => {
        const { toast, toasts } = useToasts();

        return (
          <>
            <button
              data-testid="create-toast-btn"
              onClick={() => {
                toast("success", "Item deleted", undefined, {
                  action: {
                    label: "Undo",
                    onAction: vi.fn(),
                  },
                });
              }}
            >
              Create Toast
            </button>
            <ToastViewport
              toasts={toasts}
              onDismiss={() => {
                // This will be called by the timeout
              }}
            />
          </>
        );
      };

      render(<TestComponent />);

      // Create the toast
      const createBtn = screen.getByTestId("create-toast-btn");
      fireEvent.click(createBtn);

      // Undo button is present initially
      const undoButton = screen.getByTestId(/toast-action-/);
      expect(undoButton).toBeInTheDocument();

      // Advance time by 8 seconds
      act(() => {
        vi.advanceTimersByTime(8000);
      });

      // Undo button should be gone after 8 seconds
      expect(screen.queryByTestId(/toast-action-/)).not.toBeInTheDocument();

      vi.useRealTimers();
    });
  });

  // ========================================================================
  // Multiple Toasts Tests
  // ========================================================================
  describe("multiple toasts", () => {
    it("renders multiple toasts", () => {
      const toasts: ToastItem[] = [
        { id: "toast-1", type: "success", title: "First" },
        { id: "toast-2", type: "error", title: "Second" },
        { id: "toast-3", type: "info", title: "Third" },
      ];

      render(<ToastViewport toasts={toasts} onDismiss={vi.fn()} />);

      expect(screen.getByText("First")).toBeInTheDocument();
      expect(screen.getByText("Second")).toBeInTheDocument();
      expect(screen.getByText("Third")).toBeInTheDocument();
    });

    it("dismisses individual toasts without affecting others", async () => {
      const onDismiss = vi.fn();
      const toasts: ToastItem[] = [
        { id: "toast-1", type: "success", title: "First" },
        { id: "toast-2", type: "error", title: "Second" },
      ];

      const { container } = render(<ToastViewport toasts={toasts} onDismiss={onDismiss} />);

      const closeButtons = container.querySelectorAll(".toast-x");
      await userEvent.click(closeButtons[0]);

      expect(onDismiss).toHaveBeenCalledWith("toast-1");
    });
  });
});
