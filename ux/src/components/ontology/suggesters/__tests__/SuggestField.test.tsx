import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { pipelineService } from "@/api/services/pipeline";
import { SuggestField } from "../SuggestField";

describe("SuggestField", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads candidates once the API reports the run as lower-case 'completed'", async () => {
    vi.spyOn(pipelineService, "runPipeline").mockResolvedValue({
      id: "run-1",
      status: "pending",
    } as never);
    vi.spyOn(pipelineService, "getRun").mockResolvedValue({
      id: "run-1",
      status: "completed",
    } as never);
    const getCandidates = vi.spyOn(pipelineService, "getCandidates").mockResolvedValue([
      {
        candidate_type: "refinement",
        description: "A refined definition.",
        confidence: 0.8,
        source: "llm",
        provenance: [],
      },
    ] as never);

    renderWithProviders(
      <SuggestField entityId="cls-1" value="" onChange={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Suggest/ }));

    const proposals = await screen.findByTestId("suggest-field-proposals");
    expect(proposals).toHaveClass("suggest-field-proposals");
    expect(within(proposals).getByText("A refined definition.")).toHaveClass(
      "suggest-field-candidate-text",
    );
    expect(getCandidates).toHaveBeenCalledWith("run-1");
    expect(screen.queryByTestId("suggest-field-loading")).not.toBeInTheDocument();
  });

  it("shows the failure state for a lower-case 'failed' run", async () => {
    vi.spyOn(pipelineService, "runPipeline").mockResolvedValue({
      id: "run-2",
      status: "pending",
    } as never);
    vi.spyOn(pipelineService, "getRun").mockResolvedValue({
      id: "run-2",
      status: "failed",
      failure_reason: "provider error",
    } as never);
    const getCandidates = vi.spyOn(pipelineService, "getCandidates");

    renderWithProviders(
      <SuggestField entityId="cls-1" value="" onChange={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Suggest/ }));

    expect(await screen.findByTestId("suggest-field-error")).toHaveTextContent("provider error");
    expect(getCandidates).not.toHaveBeenCalled();
  });
});
