import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { pipelineService } from "@/api/services/pipeline";
import { GroundingSection } from "../GroundingSection";
import { RelationshipSuggester } from "../RelationshipSuggester";
import { SuggestField } from "../SuggestField";

function mockCompletedRun(candidates: unknown[]) {
  const runPipeline = vi.spyOn(pipelineService, "runPipeline").mockResolvedValue({
    id: "run-1",
    status: "pending",
  } as never);
  vi.spyOn(pipelineService, "getRun").mockResolvedValue({
    id: "run-1",
    status: "completed",
  } as never);
  vi.spyOn(pipelineService, "getCandidates").mockResolvedValue(candidates as never);
  return runPipeline;
}

describe("Class drawer suggester run requests", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("grounds the class by id, leaving the selection to the server", async () => {
    const runPipeline = mockCompletedRun([
      {
        candidate_type: "grounding",
        uri: "http://dbpedia.org/resource/Bicycle",
        label: "Bicycle",
        description: "A pedal-driven vehicle",
        source: "DBpedia",
        confidence: 0.93,
        provenance: [],
      },
    ]);

    renderWithProviders(<GroundingSection classId="cls-1" />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest grounding/ }));

    expect(runPipeline).toHaveBeenCalledWith("schema_node_grounding", {
      node_id: "cls-1",
    });
    const card = await screen.findByTestId("grounding-proposal-0");
    expect(card).toHaveClass("grounding-proposal-card");
    expect(within(card).getByText("Bicycle")).toHaveClass("grounding-proposal-name");
    expect(within(card).getByRole("button", { name: "Apply" })).toHaveAttribute(
      "data-testid",
      "grounding-add-0",
    );
  });

  it("refines connections with the class as scope, leaving the selection to the server", async () => {
    const runPipeline = mockCompletedRun([]);

    renderWithProviders(<RelationshipSuggester classId="cls-1" />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest relationships/ }));

    expect(runPipeline).toHaveBeenCalledWith("schema_node_connection_refinement", {
      scope_id: "cls-1",
    });
  });

  it("dismisses one relationship suggestion at a time though suggestions carry no uri", async () => {
    mockCompletedRun(
      ["Mitochondrion is part of Cell.", "Mitochondrion has part Cristae."].map((text) => ({
        candidate_type: "refinement",
        uri: "",
        label: "",
        description: text,
        source: "refinement_pipeline",
        confidence: 0.8,
        provenance: [],
      })),
    );

    renderWithProviders(<RelationshipSuggester classId="cls-1" />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest relationships/ }));
    const second = await screen.findByTestId("relationship-suggestion-1");
    expect(second).toHaveClass("relationship-suggestion-card");

    await userEvent.click(screen.getByTestId("relationship-dismiss-0"));

    expect(screen.queryByTestId("relationship-suggestion-0")).not.toBeInTheDocument();
    expect(screen.getByTestId("relationship-suggestion-1")).toHaveTextContent(
      "Mitochondrion has part Cristae.",
    );
  });

  it("refines the definition, leaving the selection to the server", async () => {
    const runPipeline = mockCompletedRun([]);

    renderWithProviders(<SuggestField entityId="cls-1" value="A vehicle." onChange={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest/ }));

    expect(runPipeline).toHaveBeenCalledWith("schema_node_definition_refinement", {
      node_id: "cls-1",
      current_definition: "A vehicle.",
    });
  });
});
