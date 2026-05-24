import { describe, it, expect, vi } from "vitest";
import { buildStatusbarProps } from "../Statusbar";

vi.mock("@/api/hooks/admin", () => ({
  useHealth: vi.fn(),
}));

vi.mock("@/api/hooks/pipeline", () => ({
  usePipelines: vi.fn(),
}));

vi.mock("@/stores/executionStore", () => ({
  useExecutionStore: vi.fn(),
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

  describe("buildStatusbarProps", () => {
    it("returns props object with left and right sections", () => {
      const props = buildStatusbarProps();
      
      expect(props).toBeDefined();
      expect(props.left).toBeDefined();
      expect(props.right).toBeDefined();
    });

    it("includes ReactNode elements in left and right sections", () => {
      const props = buildStatusbarProps();
      
      expect(props.left).not.toBeNull();
      expect(props.right).not.toBeNull();
    });
  });
});
