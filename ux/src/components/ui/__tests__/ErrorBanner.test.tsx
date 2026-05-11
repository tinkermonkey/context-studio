import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { ErrorBanner } from "../ErrorBanner";
import { ToastProvider, ToastViewport, useToasts } from "../Toast";
import { ReactNode } from "react";

function ToastTestWrapper({ children }: { children: ReactNode }) {
  const { toasts, dismiss } = useToasts();
  return (
    <>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </>
  );
}

describe("ErrorBanner", () => {
  let mockClipboardWriteText: ReturnType<typeof vi.fn>;
  let originalWriteText: any;

  beforeEach(() => {
    // Create a fresh mock for each test
    mockClipboardWriteText = vi.fn().mockResolvedValue(undefined);
    originalWriteText = navigator.clipboard?.writeText;

    // Replace writeText on the existing clipboard object
    if (navigator.clipboard) {
      Object.defineProperty(navigator.clipboard, "writeText", {
        value: mockClipboardWriteText,
        writable: true,
        configurable: true,
      });
    }
  });

  afterEach(() => {
    // Restore original writeText
    if (originalWriteText && navigator.clipboard) {
      Object.defineProperty(navigator.clipboard, "writeText", {
        value: originalWriteText,
        writable: true,
        configurable: true,
      });
    }
    vi.clearAllMocks();
  });

  const renderWithToasts = (component: ReactNode) => {
    return render(
      <ToastProvider>
        <ToastTestWrapper>{component}</ToastTestWrapper>
      </ToastProvider>,
    );
  };

  describe("compact mode", () => {
    it("displays retry button in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("displays daemon log button in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
    });

    it("displays both retry and logs buttons in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      const buttons = screen.getAllByRole("button");
      expect(buttons).toHaveLength(2);
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
    });

    it("displays logs button before retry button in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      const buttons = screen.getAllByRole("button");
      const logsButton = screen.getByRole("button", { name: /logs/i });
      const retryButton = screen.getByRole("button", { name: /retry/i });

      expect(buttons.indexOf(logsButton)).toBeLessThan(buttons.indexOf(retryButton));
    });
  });

  describe("full mode", () => {
    it("displays error message in full mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(<ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" />);

      expect(screen.getByText("Failed to load data")).toBeInTheDocument();
      expect(screen.getByText("Test error")).toBeInTheDocument();
    });

    it("displays both retry and logs buttons in full mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(<ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" />);

      const buttons = screen.getAllByRole("button");
      expect(buttons).toHaveLength(2);
      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("renders logs button before retry button", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(<ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" />);

      const buttons = screen.getAllByRole("button");
      const logsButton = screen.getByRole("button", { name: /logs/i });
      const retryButton = screen.getByRole("button", { name: /retry/i });

      expect(buttons.indexOf(logsButton)).toBeLessThan(buttons.indexOf(retryButton));
    });
  });

  describe("null error handling", () => {
    it("does not render when error is null", () => {
      const mockRetry = vi.fn();

      render(<ErrorBanner error={null} onRetry={mockRetry} message="Failed to load data" />);

      expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /logs/i })).not.toBeInTheDocument();
    });
  });

  describe("daemon log path", () => {
    it("uses default daemon log path when not provided", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
    });

    it("uses custom daemon log path when provided", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();
      const customPath = "/custom/path/to/logs.log";

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
          compact
          daemonLogPath={customPath}
        />,
      );

      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
    });
  });

  describe("clipboard copy behavior", () => {
    it("logs button is clickable in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      const logsButton = screen.getByRole("button", { name: /logs/i });
      expect(logsButton).toBeInTheDocument();
      expect(logsButton.title).toBe("Copy daemon log path");
    });

    it("logs button is clickable in full mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(<ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" />);

      const logsButton = screen.getByRole("button", { name: /logs/i });
      expect(logsButton).toBeInTheDocument();
      expect(logsButton.title).toBe("Copy daemon log path");
    });

    it("shows success toast when logs button is clicked in compact mode", async () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();
      const user = userEvent.setup();

      renderWithToasts(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      const logsButton = screen.getByRole("button", { name: /logs/i });
      await user.click(logsButton);

      await waitFor(() => {
        expect(screen.getByText("Log path copied to clipboard")).toBeInTheDocument();
      });
    });

    it("shows success toast when logs button is clicked in full mode", async () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();
      const user = userEvent.setup();

      renderWithToasts(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" />,
      );

      const logsButton = screen.getByRole("button", { name: /logs/i });
      await user.click(logsButton);

      await waitFor(() => {
        expect(screen.getByText("Log path copied to clipboard")).toBeInTheDocument();
      });
    });

    it("shows error toast when clipboard write fails", async () => {
      mockClipboardWriteText.mockRejectedValueOnce(new Error("Clipboard write failed"));

      const mockError = new Error("Test error");
      const mockRetry = vi.fn();
      const user = userEvent.setup();

      renderWithToasts(
        <ErrorBanner error={mockError} onRetry={mockRetry} message="Failed to load data" compact />,
      );

      const logsButton = screen.getByRole("button", { name: /logs/i });
      await user.click(logsButton);

      await waitFor(() => {
        expect(screen.getByText("Failed to copy log path")).toBeInTheDocument();
      });
    });
  });
});
