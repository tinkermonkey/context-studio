import type { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "@/test/test-utils";
import {
  pipelineService,
  type PipelineConfiguration,
  type PipelineImplementation,
} from "@/api/services/pipeline";
import {
  selectionRequestFields,
  usePipelineSelection,
  type PipelineSelectionOptions,
} from "../usePipelineSelection";

const TYPE = "individual_extraction";

const implementation = (
  id: string,
  overrides: Partial<PipelineImplementation> = {},
): PipelineImplementation => ({
  id,
  pipeline_type: TYPE,
  is_default: false,
  default_configuration: null,
  extracts_sources: false,
  ...overrides,
});

const configuration = (
  implementationId: string,
  configRef: string,
  overrides: Partial<PipelineConfiguration> = {},
): PipelineConfiguration => ({
  id: `${implementationId}:${configRef}`,
  config_ref: configRef,
  pipeline_type: TYPE,
  implementation_id: implementationId,
  name: configRef,
  provider: "anthropic",
  model: "model-a",
  enabled: true,
  version: 1,
  is_system: true,
  is_default: false,
  ...overrides,
});

// The default is deliberately not first: nothing may rely on list order for it.
const IMPLEMENTATIONS = [
  implementation("two_step", { extracts_sources: true }),
  implementation("text_only"),
  implementation("classic", { is_default: true, extracts_sources: true }),
  implementation("bare"),
];
const CONFIGURATIONS: Record<string, PipelineConfiguration[]> = {
  classic: [
    configuration("classic", "classic-alt"),
    configuration("classic", "classic-main", { is_default: true }),
    configuration("classic", "classic-off", { enabled: false }),
    // The same ref under two implementations: refs are unique per implementation only.
    configuration("classic", "cfg_shared"),
  ],
  two_step: [
    configuration("two_step", "cfg_shared"),
    configuration("two_step", "two-step-main", { is_default: true }),
  ],
  // Its default configuration is disabled; another one is enabled.
  text_only: [
    configuration("text_only", "text-only-off", { enabled: false, is_default: true }),
    configuration("text_only", "text-only-on"),
  ],
  // Nothing enabled at all.
  bare: [configuration("bare", "bare-off", { enabled: false, is_default: true })],
};

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

function select(options?: PipelineSelectionOptions) {
  vi.spyOn(pipelineService, "listImplementations").mockResolvedValue(IMPLEMENTATIONS);
  vi.spyOn(pipelineService, "listConfigurations").mockImplementation(
    async (_type, implId) => CONFIGURATIONS[implId],
  );
  return renderHook(() => usePipelineSelection(TYPE, options), { wrapper });
}

describe("usePipelineSelection", () => {
  afterEach(() => vi.restoreAllMocks());

  it("selects the implementation and configuration the API marks as default", async () => {
    const { result } = select();
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("classic-main"));
    expect(result.current.implementation?.id).toBe("classic");
    expect(result.current.implementations.map((i) => i.id)).toEqual([
      "two_step",
      "text_only",
      "classic",
      "bare",
    ]);
    expect(selectionRequestFields(result.current)).toEqual({
      implementation_id: "classic",
      configuration_ref: "classic-main",
    });
  });

  it("never offers a disabled configuration", async () => {
    const { result } = select();
    await waitFor(() => expect(result.current.configurations).toHaveLength(3));
    expect(result.current.configurations.map((c) => c.config_ref)).toEqual([
      "classic-alt",
      "classic-main",
      "cfg_shared",
    ]);
  });

  it("drops the chosen configuration when another implementation is chosen", async () => {
    const { result } = select();
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("classic-main"));

    act(() => result.current.selectConfiguration("classic-alt"));
    expect(result.current.configuration?.config_ref).toBe("classic-alt");

    act(() => result.current.selectImplementation("two_step"));
    expect(result.current.implementation?.id).toBe("two_step");
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("two-step-main"));
    expect(selectionRequestFields(result.current)).toEqual({
      implementation_id: "two_step",
      configuration_ref: "two-step-main",
    });
  });

  it("offers only the implementations the caller accepts", async () => {
    const { result } = select({ offers: (i) => i.extracts_sources === true });
    await waitFor(() => expect(result.current.implementation?.id).toBe("classic"));
    expect(result.current.implementations.map((i) => i.id)).toEqual(["two_step", "classic"]);
  });

  it("keeps the chosen configuration when its implementation is picked again", async () => {
    const { result } = select();
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("classic-main"));
    act(() => result.current.selectConfiguration("classic-alt"));

    // The real Select reports a pick of the item that is already selected.
    act(() => result.current.selectImplementation("classic"));
    expect(result.current.configuration?.config_ref).toBe("classic-alt");
  });

  it("does not carry a chosen ref over to another implementation that has the same ref", async () => {
    const { result } = select();
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("classic-main"));
    act(() => result.current.selectConfiguration("cfg_shared"));
    expect(result.current.configuration?.id).toBe("classic:cfg_shared");

    act(() => result.current.selectImplementation("two_step"));
    await waitFor(() => expect(result.current.configuration?.id).toBe("two_step:two-step-main"));
  });

  it("selects the first offered implementation when the default one is not offered", async () => {
    const { result } = select({ offers: (i) => !i.is_default });
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("two-step-main"));
    expect(result.current.implementation?.id).toBe("two_step");
    // Named explicitly: the server refuses to choose among what it was not offered.
    expect(selectionRequestFields(result.current)).toEqual({
      implementation_id: "two_step",
      configuration_ref: "two-step-main",
    });
  });

  it("falls back to the default when the chosen implementation stops being offered", async () => {
    vi.spyOn(pipelineService, "listImplementations").mockResolvedValue(IMPLEMENTATIONS);
    vi.spyOn(pipelineService, "listConfigurations").mockImplementation(
      async (_type, implId) => CONFIGURATIONS[implId],
    );
    const { result, rerender } = renderHook(
      ({ offers }: PipelineSelectionOptions) => usePipelineSelection(TYPE, { offers }),
      { wrapper, initialProps: {} as PipelineSelectionOptions },
    );
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("classic-main"));
    act(() => result.current.selectImplementation("text_only"));
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("text-only-on"));

    rerender({ offers: (i) => i.extracts_sources === true });
    expect(result.current.implementation?.id).toBe("classic");
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("classic-main"));
  });

  it("selects the first enabled configuration when the default one is disabled", async () => {
    const { result } = select();
    await waitFor(() => expect(result.current.implementation?.id).toBe("classic"));
    act(() => result.current.selectImplementation("text_only"));
    await waitFor(() => expect(result.current.configuration?.config_ref).toBe("text-only-on"));
    expect(result.current.configurations.map((c) => c.config_ref)).toEqual(["text-only-on"]);
    // Sent explicitly: left out, the server would refuse the disabled default.
    expect(selectionRequestFields(result.current)).toEqual({
      implementation_id: "text_only",
      configuration_ref: "text-only-on",
    });
  });

  it("selects no configuration for an implementation with none enabled", async () => {
    const { result } = select();
    await waitFor(() => expect(result.current.implementation?.id).toBe("classic"));
    act(() => result.current.selectImplementation("bare"));
    await waitFor(() =>
      expect(pipelineService.listConfigurations).toHaveBeenCalledWith(TYPE, "bare"),
    );
    expect(result.current.configurations).toEqual([]);
    expect(result.current.configuration).toBeUndefined();
    expect(selectionRequestFields(result.current)).toEqual({ implementation_id: "bare" });
  });

  it("reports a list that could not be read and selects nothing", async () => {
    vi.spyOn(pipelineService, "listImplementations").mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => usePipelineSelection(TYPE), { wrapper });
    await waitFor(() => expect(result.current.implementationsError).toBe("boom"));
    expect(result.current.implementation).toBeUndefined();
    expect(selectionRequestFields(result.current)).toEqual({});
  });
});
