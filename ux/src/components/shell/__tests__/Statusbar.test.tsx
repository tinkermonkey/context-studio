import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Statusbar } from "../Statusbar";

vi.mock("@/api/hooks/admin", () => ({
  useHealth: vi.fn(),
}));

vi.mock("@/api/hooks/pipeline", () => ({
  usePipelines: vi.fn(),
}));

vi.mock("@/stores/executionStore", () => ({
  useExecutionStore: vi.fn(),
}));

vi.mock("@tinkermonkey/heimdall-ui", () => ({
  Statusbar: ({ left, right }: any) => (
    <div data-testid="heimdall-statusbar">
      <div data-testid="statusbar-left">{left}</div>
      <div data-testid="statusbar-right">{right}</div>
    </div>
  ),
}));

import * as healthModule from "@/api/hooks/admin";
import * as pipelineModule from "@/api/hooks/pipeline";
import * as executionModule from "@/stores/executionStore";

describe("Statusbar", () => {
  beforeEach(() => {
    vi.mocked(healthModule.useHealth).mockReturnValue({
      data: {
        status: "healthy",
        uptime_seconds: 600,
        database_connected: true,
      },
      isError: false,
    } as any);

    vi.mocked(executionModule.useExecutionStore).mockReturnValue({
      inFlightPipelineIds: new Set(),
    } as any);

    vi.mocked(pipelineModule.usePipelines).mockReturnValue({
      data: [],
      isError: false,
    } as any);
  });

  describe("health status display", () => {
    it("renders healthy status when API is healthy", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("healthy")).toBeInTheDocument();
    });

    it("renders degraded status when API is degraded", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "degraded", uptime_seconds: 600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("degraded")).toBeInTheDocument();
    });

    it("renders api offline status when health is error", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: undefined,
        isError: true,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("api offline")).toBeInTheDocument();
    });

    it("renders connecting status when health is undefined and not error", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: undefined,
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("connecting...")).toBeInTheDocument();
    });
  });

  describe("status pulse indicator", () => {
    it("applies error class to pulse when API is offline", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: undefined,
        isError: true,
      } as any);

      render(<Statusbar />);
      const pulse = screen.getByTestId("statusbar-left").querySelector(".status-pulse.error");
      expect(pulse).toBeInTheDocument();
    });

    it("applies warning class to pulse when API is degraded", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "degraded", uptime_seconds: 600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      const pulse = screen.getByTestId("statusbar-left").querySelector(".status-pulse.warning");
      expect(pulse).toBeInTheDocument();
    });

    it("applies no class to pulse when API is healthy", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      const pulse = screen.getByTestId("statusbar-left").querySelector(".status-pulse:not(.error):not(.warning):not(.idle)");
      expect(pulse).toBeInTheDocument();
    });

    it("applies idle class to pulse when connecting", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: undefined,
        isError: false,
      } as any);

      render(<Statusbar />);
      const pulse = screen.getByTestId("statusbar-left").querySelector(".status-pulse.idle");
      expect(pulse).toBeInTheDocument();
    });
  });

  describe("database status", () => {
    it("displays database connected message when connected", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("database connected")).toBeInTheDocument();
    });

    it("displays database unavailable message when not connected", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 600, database_connected: false },
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("database unavailable")).toBeInTheDocument();
    });

    it("displays cannot reach api message when API is offline", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: undefined,
        isError: true,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("cannot reach api")).toBeInTheDocument();
    });

    it("renders network icon when API is online", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      const left = screen.getByTestId("statusbar-left");
      const svg = left.querySelector("svg");
      expect(svg).toBeInTheDocument();
    });

    it("renders alert icon when API is offline", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: undefined,
        isError: true,
      } as any);

      render(<Statusbar />);
      const left = screen.getByTestId("statusbar-left");
      const svg = left.querySelector("svg");
      expect(svg).toBeInTheDocument();
    });
  });

  describe("uptime formatting", () => {
    it("converts 600 seconds to 10 minutes", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("up 10m")).toBeInTheDocument();
    });

    it("converts 3600 seconds to 60 minutes", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 3600, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("up 60m")).toBeInTheDocument();
    });

    it("rounds down fractional minutes", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: { status: "healthy", uptime_seconds: 650, database_connected: true },
        isError: false,
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("up 10m")).toBeInTheDocument();
    });

    it("does not display uptime when health data is unavailable", () => {
      vi.mocked(healthModule.useHealth).mockReturnValue({
        data: undefined,
        isError: true,
      } as any);

      render(<Statusbar />);
      const right = screen.getByTestId("statusbar-right");
      expect(right.textContent).not.toContain("up");
    });
  });

  describe("pipeline count display", () => {
    it("does not display pipeline count when no pipelines are running", () => {
      vi.mocked(executionModule.useExecutionStore).mockReturnValue({
        inFlightPipelineIds: new Set(),
      } as any);

      render(<Statusbar />);
      expect(screen.queryByText(/pipeline/i)).not.toBeInTheDocument();
    });

    it("displays singular pipeline text when one pipeline is running", () => {
      vi.mocked(executionModule.useExecutionStore).mockReturnValue({
        inFlightPipelineIds: new Set(["pipeline-1"]),
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("1 pipeline running")).toBeInTheDocument();
    });

    it("displays plural pipeline text when multiple pipelines are running", () => {
      vi.mocked(executionModule.useExecutionStore).mockReturnValue({
        inFlightPipelineIds: new Set(["pipeline-1", "pipeline-2", "pipeline-3"]),
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("3 pipelines running")).toBeInTheDocument();
    });

    it("displays running pulse indicator when pipelines are running", () => {
      vi.mocked(executionModule.useExecutionStore).mockReturnValue({
        inFlightPipelineIds: new Set(["pipeline-1"]),
      } as any);

      render(<Statusbar />);
      const right = screen.getByTestId("statusbar-right");
      const pulse = right.querySelector(".status-pulse.running");
      expect(pulse).toBeInTheDocument();
    });
  });

  describe("pipeline polling", () => {
    it("calls usePipelines with 5000ms interval when pipelines are running", () => {
      vi.mocked(executionModule.useExecutionStore).mockReturnValue({
        inFlightPipelineIds: new Set(["pipeline-1"]),
      } as any);

      render(<Statusbar />);
      expect(vi.mocked(pipelineModule.usePipelines)).toHaveBeenCalledWith(5000);
    });

    it("calls usePipelines with false when no pipelines are running", () => {
      vi.mocked(executionModule.useExecutionStore).mockReturnValue({
        inFlightPipelineIds: new Set(),
      } as any);

      render(<Statusbar />);
      expect(vi.mocked(pipelineModule.usePipelines)).toHaveBeenCalledWith(false);
    });
  });

  describe("right section content", () => {
    it("always displays encoding info", () => {
      render(<Statusbar />);
      const right = screen.getByTestId("statusbar-right");
      expect(right.textContent).toContain("UTF-8");
      expect(right.textContent).toContain("LF");
    });

    it("always displays local environment indicator", () => {
      render(<Statusbar />);
      expect(screen.getByText("local")).toBeInTheDocument();
    });

    it("renders check circle icon for local environment", () => {
      render(<Statusbar />);
      const right = screen.getByTestId("statusbar-right");
      const localText = screen.getByText("local");
      const icon = localText.parentElement?.querySelector("svg");
      expect(icon).toBeInTheDocument();
    });

    it("displays pipeline count when pipelines are running", () => {
      vi.mocked(executionModule.useExecutionStore).mockReturnValue({
        inFlightPipelineIds: new Set(["pipeline-1"]),
      } as any);

      render(<Statusbar />);
      expect(screen.getByText("1 pipeline running")).toBeInTheDocument();
    });
  });

  describe("statusbar layout", () => {
    it("renders heimdall statusbar", () => {
      render(<Statusbar />);
      expect(screen.getByTestId("heimdall-statusbar")).toBeInTheDocument();
    });

    it("renders left section with health and database info", () => {
      render(<Statusbar />);
      const left = screen.getByTestId("statusbar-left");
      expect(left.querySelector(".statusbar-group")).toBeInTheDocument();
      expect(left.textContent).toContain("api server");
    });

    it("renders right section with environment and uptime info", () => {
      render(<Statusbar />);
      const right = screen.getByTestId("statusbar-right");
      expect(right.querySelector(".statusbar-group")).toBeInTheDocument();
      expect(right.textContent).toContain("local");
    });
  });
});
