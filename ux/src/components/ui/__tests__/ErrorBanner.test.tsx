import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { ErrorBanner } from "../ErrorBanner";

describe("ErrorBanner", () => {
  describe("compact mode", () => {
    it("displays retry button in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
          compact
        />
      );

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("displays daemon log button in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
          compact
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      );

      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
    });

    it("displays both retry and logs buttons in compact mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
          compact
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      );

      const buttons = screen.getAllByRole("button");
      expect(buttons).toHaveLength(2);
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
    });
  });

  describe("full mode", () => {
    it("displays error message in full mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
        />
      );

      expect(screen.getByText("Failed to load data")).toBeInTheDocument();
      expect(screen.getByText("Test error")).toBeInTheDocument();
    });

    it("displays both retry and logs buttons in full mode", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      );

      const buttons = screen.getAllByRole("button");
      expect(buttons).toHaveLength(2);
      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("renders logs button before retry button", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      );

      const buttons = screen.getAllByRole("button");
      const logsButton = screen.getByRole("button", { name: /logs/i });
      const retryButton = screen.getByRole("button", { name: /retry/i });

      expect(buttons.indexOf(logsButton)).toBeLessThan(buttons.indexOf(retryButton));
    });
  });

  describe("null error handling", () => {
    it("does not render when error is null", () => {
      const mockRetry = vi.fn();

      const { container } = render(
        <ErrorBanner
          error={null}
          onRetry={mockRetry}
          message="Failed to load data"
        />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe("daemon log path", () => {
    it("uses default daemon log path when not provided", () => {
      const mockError = new Error("Test error");
      const mockRetry = vi.fn();

      render(
        <ErrorBanner
          error={mockError}
          onRetry={mockRetry}
          message="Failed to load data"
          compact
        />
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
        />
      );

      expect(screen.getByRole("button", { name: /logs/i })).toBeInTheDocument();
    });
  });
});
