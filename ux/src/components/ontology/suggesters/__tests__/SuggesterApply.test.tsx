import type { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import { pipelineService } from "@/api/services/pipeline";
import { GroundingSection } from "../GroundingSection";
import { RelationshipSuggester } from "../RelationshipSuggester";
import { SuggestField } from "../SuggestField";

const { toastSpy } = vi.hoisted(() => ({ toastSpy: vi.fn() }));
vi.mock("@/components/ui/Toast", () => ({
  ToastProvider: ({ children }: { children: ReactNode }) => children,
  useToasts: () => ({ toast: toastSpy, toasts: [], dismiss: vi.fn() }),
}));

function mockCompletedRun(candidates: unknown[]) {
  vi.spyOn(pipelineService, "runPipeline").mockResolvedValue({
    id: "run-1",
    status: "pending",
  } as never);
  vi.spyOn(pipelineService, "getRun").mockResolvedValue({
    id: "run-1",
    status: "completed",
  } as never);
  vi.spyOn(pipelineService, "getCandidates").mockResolvedValue(candidates as never);
  return vi.spyOn(pipelineService, "applyRun").mockResolvedValue({
    relationships_created: 1,
    relationships_removed: 0,
    relationships_modified: 0,
    relationships_skipped: 0,
  } as never);
}

function refinement(candidateId: string, text: string, confidence: number) {
  return {
    candidate_id: candidateId,
    candidate_type: "refinement",
    uri: "",
    label: text,
    description: text,
    source: "refinement_pipeline",
    confidence,
    provenance: [],
  };
}

describe("Class drawer suggesters apply only the chosen candidate", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    toastSpy.mockClear();
  });

  it("applies one grounding by its candidate id", async () => {
    const applyRun = mockCompletedRun(
      ["Q1", "Q2"].map((q, i) => ({
        candidate_id: `grounding-${i}`,
        candidate_type: "grounding",
        uri: `http://www.wikidata.org/entity/${q}`,
        label: q,
        description: "",
        source: "Wikidata",
        confidence: i === 0 ? 0.9 : 0.5,
        provenance: [],
      })),
    );

    renderWithProviders(<GroundingSection classId="cls-1" />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest grounding/ }));
    await userEvent.click(await screen.findByTestId("grounding-add-1"));

    expect(applyRun).toHaveBeenCalledWith(
      "run-1",
      { node_id: "cls-1" },
      { accepted_candidate_ids: ["grounding-1"] },
    );
    expect(await screen.findByTestId("grounding-add-1")).toHaveTextContent("✓ Applied");
    expect(screen.getByTestId("grounding-add-0")).toHaveTextContent("Apply");
  });

  it("accepts one relationship suggestion by its candidate id", async () => {
    const applyRun = mockCompletedRun([
      refinement("refinement-0", "Add: Mitochondrion part of Cell", 0.6),
      refinement("refinement-1", "Remove: Mitochondrion subclass of Cell", 0.9),
    ]);

    renderWithProviders(<RelationshipSuggester classId="cls-1" />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest relationships/ }));
    const first = await screen.findByTestId("relationship-suggestion-0");
    await userEvent.click(within(first).getByRole("button", { name: "Accept" }));

    expect(applyRun).toHaveBeenCalledWith(
      "run-1",
      { node_id: "cls-1" },
      { accepted_candidate_ids: ["refinement-0"] },
    );
    expect(screen.queryByTestId("relationship-suggestion-0")).not.toBeInTheDocument();
    expect(screen.getByTestId("relationship-suggestion-1")).toHaveTextContent(
      "Remove: Mitochondrion subclass of Cell",
    );
  });

  it("says nothing changed when an accepted modify can't be applied", async () => {
    const applyRun = mockCompletedRun([
      refinement("refinement-0", "Modify: Mitochondrion part of Cell", 0.8),
    ]);
    applyRun.mockResolvedValue({
      relationships_created: 0,
      relationships_removed: 0,
      relationships_modified: 1,
      relationships_skipped: 0,
    } as never);

    renderWithProviders(<RelationshipSuggester classId="cls-1" />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest relationships/ }));
    const card = await screen.findByTestId("relationship-suggestion-0");
    await userEvent.click(within(card).getByRole("button", { name: "Accept" }));

    await waitFor(() =>
      expect(toastSpy).toHaveBeenLastCalledWith(
        "warning",
        expect.stringContaining("isn't supported yet; nothing changed"),
      ),
    );
    expect(toastSpy).not.toHaveBeenCalledWith("success", "Relationship applied");
  });

  it("replaces the definition with the chosen candidate", async () => {
    const applyRun = mockCompletedRun([
      refinement("refinement-0", "The best definition.", 0.9),
      refinement("refinement-1", "The chosen definition.", 0.7),
    ]);
    const onChange = vi.fn();

    renderWithProviders(<SuggestField entityId="cls-1" value="Old." onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /Suggest/ }));
    await screen.findByTestId("suggest-field-proposals");
    await userEvent.click(screen.getAllByRole("button", { name: "Replace" })[1]);

    expect(applyRun).toHaveBeenCalledWith(
      "run-1",
      { node_id: "cls-1" },
      { accepted_candidate_ids: ["refinement-1"] },
    );
    expect(onChange).toHaveBeenCalledWith("The chosen definition.");
  });

  it("appends a definition by editing the field, without applying the run", async () => {
    const applyRun = mockCompletedRun([refinement("refinement-0", "More detail.", 0.9)]);
    const onChange = vi.fn();
    const onCommit = vi.fn();

    renderWithProviders(
      <SuggestField entityId="cls-1" value="Old." onChange={onChange} onCommit={onCommit} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Suggest/ }));
    await screen.findByTestId("suggest-field-proposals");
    await userEvent.click(screen.getByRole("button", { name: "Append" }));

    expect(onChange).toHaveBeenCalledWith("Old.\n\nMore detail.");
    // Saved directly: the Append button unmounts, so a blur-save can't be relied on.
    expect(onCommit).toHaveBeenCalledWith("Old.\n\nMore detail.");
    expect(applyRun).not.toHaveBeenCalled();
  });

  it("hides Suggest when there is no class to refine", () => {
    renderWithProviders(
      <SuggestField value="" onChange={vi.fn()} testId="scheme-drawer-description-input" />,
    );

    expect(screen.getByTestId("scheme-drawer-description-input")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Suggest/ })).not.toBeInTheDocument();
  });
});
