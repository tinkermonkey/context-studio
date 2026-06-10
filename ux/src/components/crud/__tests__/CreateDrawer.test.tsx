import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { CreateDrawer } from "../CreateDrawer";

// ─── mutation mocks ──────────────────────────────────────────────────────────

const mockCreateTaxonomy = vi.fn();
const mockCreateScheme = vi.fn();
const mockCreateClass = vi.fn();
const mockCreateProperty = vi.fn();
const mockCreateIndividual = vi.fn();
const mockCreateRelationship = vi.fn();

vi.mock("@/api/hooks/ontology/useTaxonomies", () => ({
  useCreateTaxonomy: () => ({ mutateAsync: mockCreateTaxonomy }),
  useTaxonomies: () => ({
    data: { items: [{ id: "tax-1", title: "Biology" }] },
  }),
}));

vi.mock("@/api/hooks/ontology/useSchemes", () => ({
  useCreateScheme: () => ({ mutateAsync: mockCreateScheme }),
  useSchemes: () => ({
    data: {
      items: [{ id: "sch-1", title: "Cell Biology", taxonomy_id: "tax-1" }],
    },
  }),
}));

vi.mock("@/api/hooks/ontology/useClasses", () => ({
  useCreateClass: () => ({ mutateAsync: mockCreateClass }),
  useClasses: () => ({
    data: { items: [{ id: "cls-1", title: "Neuron" }] },
  }),
}));

vi.mock("@/api/hooks/ontology/useProperties", () => ({
  useCreateProperty: () => ({ mutateAsync: mockCreateProperty }),
  useProperties: () => ({
    data: {
      items: [{ id: "prop-1", identifier: "has_part", title: "Has Part" }],
    },
  }),
}));

vi.mock("@/api/hooks/ontology/useIndividuals", () => ({
  useCreateIndividual: () => ({ mutateAsync: mockCreateIndividual }),
}));

vi.mock("@/api/hooks/ontology/useRelationships", () => ({
  useCreateRelationship: () => ({ mutateAsync: mockCreateRelationship }),
}));

// SuggestField has pipeline hooks — mock them to prevent test noise
vi.mock("@/api/hooks/pipeline/usePipelineMutations", () => ({
  useRunPipeline: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApplyRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/api/hooks/pipeline/usePipelineRuns", () => ({
  usePipelineRun: () => ({ data: null }),
  usePipelineCandidates: () => ({ data: [] }),
}));

// ─── helpers ─────────────────────────────────────────────────────────────────

function renderDrawer(props: Record<string, any> = {}) {
  const onClose = vi.fn();
  const onSuccess = vi.fn();
  const result = render(
    <CreateDrawer
      entityType="taxonomy"
      isOpen={true}
      onClose={onClose}
      onSuccess={onSuccess}
      {...props}
    />,
  );
  return { ...result, onClose, onSuccess };
}

beforeEach(() => {
  mockCreateTaxonomy.mockReset();
  mockCreateScheme.mockReset();
  mockCreateClass.mockReset();
  mockCreateProperty.mockReset();
  mockCreateIndividual.mockReset();
  mockCreateRelationship.mockReset();
});

// ─── tests ───────────────────────────────────────────────────────────────────

describe("CreateDrawer", () => {
  describe("data-testid", () => {
    it("renders create-drawer testid", () => {
      renderDrawer();
      expect(screen.getByTestId("create-drawer")).toBeInTheDocument();
    });

    it("renders create-drawer-panel with full variant", () => {
      renderDrawer({ variant: "full" });
      expect(screen.getByTestId("create-drawer-panel")).toBeInTheDocument();
    });

    it("renders create-drawer-inline with inline variant", () => {
      renderDrawer({ variant: "inline" });
      expect(screen.getByTestId("create-drawer-inline")).toBeInTheDocument();
    });

    it("accepts custom testId", () => {
      renderDrawer({ "data-testid": "my-drawer" });
      expect(screen.getByTestId("my-drawer")).toBeInTheDocument();
    });

    it("returns null when isOpen is false", () => {
      renderDrawer({ isOpen: false });
      expect(screen.queryByTestId("create-drawer")).not.toBeInTheDocument();
    });
  });

  describe("create button disabled state (FR-9)", () => {
    it("is disabled when form is incomplete", () => {
      renderDrawer({ entityType: "taxonomy" });
      expect(screen.getByTestId("create-drawer-create-btn")).toBeDisabled();
    });

    it("is enabled once all required fields are filled", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "taxonomy" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "My Tax");
      expect(screen.getByTestId("create-drawer-create-btn")).not.toBeDisabled();
    });

    it("becomes disabled again when required field is cleared", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "taxonomy" });
      const input = screen.getByTestId("create-drawer-title-input");
      await user.type(input, "My Tax");
      expect(screen.getByTestId("create-drawer-create-btn")).not.toBeDisabled();
      await user.clear(input);
      expect(screen.getByTestId("create-drawer-create-btn")).toBeDisabled();
    });

    it("is disabled for scheme when taxonomy is not selected", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "scheme" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "My Scheme");
      expect(screen.getByTestId("create-drawer-create-btn")).toBeDisabled();
    });
  });

  describe("auto-slug behavior", () => {
    it("populates identifier from title automatically", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "taxonomy" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      const idInput = screen.getByTestId("create-drawer-identifier-input") as HTMLInputElement;
      expect(idInput.value).toBe("tax_life_sciences");
    });

    it("auto-slug uses prefix matching entity type", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "scheme" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "Cell Biology");
      const idInput = screen.getByTestId("create-drawer-identifier-input") as HTMLInputElement;
      expect(idInput.value).toBe("sch_cell_biology");
    });

    it("shows 're-link to title' hint when identifier is customized", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "taxonomy" });
      const idInput = screen.getByTestId("create-drawer-identifier-input");
      await user.type(idInput, "custom_id");
      expect(screen.getByTestId("create-drawer-relink-btn")).toBeInTheDocument();
    });

    it("re-links identifier to title when re-link button is clicked", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "taxonomy" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      const idInput = screen.getByTestId("create-drawer-identifier-input");
      await user.clear(idInput);
      await user.type(idInput, "custom_id");
      await user.click(screen.getByTestId("create-drawer-relink-btn"));
      expect((idInput as HTMLInputElement).value).toBe("tax_life_sciences");
    });

    it("relationship type shows no identifier field", () => {
      renderDrawer({ entityType: "relationship" });
      expect(screen.queryByTestId("create-drawer-identifier-input")).not.toBeInTheDocument();
    });
  });

  describe("progress meter", () => {
    it("shows unsatisfied chip for required title field initially", () => {
      renderDrawer({ entityType: "taxonomy" });
      const chip = screen.getAllByRole("generic").find(
        (el) => el.getAttribute("aria-label") === "title: required",
      );
      expect(chip).toBeInTheDocument();
    });

    it("chip becomes satisfied after filling title", async () => {
      const user = userEvent.setup();
      renderDrawer({ entityType: "taxonomy" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "Test");
      await waitFor(() => {
        const chip = screen.getAllByRole("generic").find(
          (el) => el.getAttribute("aria-label") === "title: satisfied",
        );
        expect(chip).toBeInTheDocument();
      });
    });
  });

  describe("entity type variants", () => {
    it("taxonomy: renders title and identifier fields", () => {
      renderDrawer({ entityType: "taxonomy" });
      expect(screen.getByTestId("create-drawer-title-input")).toBeInTheDocument();
      expect(screen.getByTestId("create-drawer-identifier-input")).toBeInTheDocument();
    });

    it("taxonomy: renders description SuggestField", () => {
      renderDrawer({ entityType: "taxonomy" });
      expect(screen.getByTestId("create-drawer-description-input")).toBeInTheDocument();
    });

    it("scheme: renders taxonomy select", () => {
      renderDrawer({ entityType: "scheme" });
      expect(screen.getByTestId("create-drawer-taxonomy-select")).toBeInTheDocument();
    });

    it("class: renders concept scheme select", () => {
      renderDrawer({ entityType: "class" });
      expect(screen.getByTestId("create-drawer-scheme-select")).toBeInTheDocument();
    });

    it("property: renders relevance segmented control", () => {
      renderDrawer({ entityType: "property" });
      expect(screen.getByTestId("create-drawer-relevance-control")).toBeInTheDocument();
    });

    it("individual: renders class multi-select list", () => {
      renderDrawer({ entityType: "individual" });
      expect(screen.getByTestId("create-drawer-classes-list")).toBeInTheDocument();
    });

    it("relationship: renders relationship builder", () => {
      renderDrawer({ entityType: "relationship" });
      expect(screen.getByTestId("create-drawer-relationship-builder")).toBeInTheDocument();
    });

    it("relationship: does not render title input", () => {
      renderDrawer({ entityType: "relationship" });
      expect(screen.queryByTestId("create-drawer-title-input")).not.toBeInTheDocument();
    });
  });

  describe("successful create — taxonomy", () => {
    it("calls mutateAsync with title and description", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockResolvedValue({ id: "tax-new", title: "Life Sciences" });

      renderDrawer({ entityType: "taxonomy" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() => {
        expect(mockCreateTaxonomy).toHaveBeenCalledWith({
          title: "Life Sciences",
          description: null,
        });
      });
    });

    it("calls onSuccess with the created entity", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockResolvedValue({ id: "tax-new", title: "Life Sciences" });
      const { onSuccess } = renderDrawer({ entityType: "taxonomy" });

      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith({ id: "tax-new", title: "Life Sciences" });
      });
    });

    it("calls onClose after success", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockResolvedValue({ id: "tax-new", title: "Life Sciences" });
      const { onClose } = renderDrawer({ entityType: "taxonomy" });

      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe("successful create — scheme", () => {
    it("calls mutateAsync with taxonomyId and title", async () => {
      const user = userEvent.setup();
      mockCreateScheme.mockResolvedValue({ id: "sch-new", title: "Cell Biology" });

      renderDrawer({ entityType: "scheme", initialTaxonomyId: "tax-1" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "Cell Biology");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() => {
        expect(mockCreateScheme).toHaveBeenCalledWith({
          taxonomyId: "tax-1",
          data: { title: "Cell Biology", description: null },
        });
      });
    });
  });

  describe("create another flow", () => {
    it("shows success banner after creating with 'create another' checked", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockResolvedValue({ id: "tax-new", title: "Life Sciences" });

      renderDrawer({ entityType: "taxonomy" });
      await user.click(screen.getByTestId("create-drawer-another-checkbox"));
      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("create-drawer-success")).toBeInTheDocument();
      });
    });

    it("resets title field after 'create another'", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockResolvedValue({ id: "tax-new", title: "Life Sciences" });

      renderDrawer({ entityType: "taxonomy" });
      await user.click(screen.getByTestId("create-drawer-another-checkbox"));
      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() => {
        const titleInput = screen.getByTestId("create-drawer-title-input") as HTMLInputElement;
        expect(titleInput.value).toBe("");
      });
    });

    it("does not call onClose when 'create another' is checked", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockResolvedValue({ id: "tax-new", title: "Life Sciences" });
      const { onClose } = renderDrawer({ entityType: "taxonomy" });

      await user.click(screen.getByTestId("create-drawer-another-checkbox"));
      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() =>
        expect(screen.getByTestId("create-drawer-success")).toBeInTheDocument(),
      );
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe("error handling", () => {
    it("shows error banner when mutation rejects", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockRejectedValue(new Error("Server error"));

      renderDrawer({ entityType: "taxonomy" });
      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("create-drawer-error")).toHaveTextContent("Server error");
      });
    });

    it("does not call onClose when mutation fails", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockRejectedValue(new Error("Server error"));
      const { onClose } = renderDrawer({ entityType: "taxonomy" });

      await user.type(screen.getByTestId("create-drawer-title-input"), "Life Sciences");
      await user.click(screen.getByTestId("create-drawer-create-btn"));

      await waitFor(() =>
        expect(screen.getByTestId("create-drawer-error")).toBeInTheDocument(),
      );
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe("cancel button", () => {
    it("calls onClose when cancel is clicked", async () => {
      const user = userEvent.setup();
      const { onClose } = renderDrawer();
      await user.click(screen.getByTestId("create-drawer-cancel-btn"));
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe("keyboard shortcuts", () => {
    it("Escape key calls onClose", async () => {
      const user = userEvent.setup();
      const { onClose } = renderDrawer();
      await user.keyboard("{Escape}");
      expect(onClose).toHaveBeenCalled();
    });

    it("Cmd+Enter submits when form is complete", async () => {
      const user = userEvent.setup();
      mockCreateTaxonomy.mockResolvedValue({ id: "tax-new", title: "Test" });
      const { onClose } = renderDrawer({ entityType: "taxonomy" });

      await user.type(screen.getByTestId("create-drawer-title-input"), "Test");
      await user.keyboard("{Meta>}{Enter}{/Meta}");

      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe("reset on open", () => {
    it("resets form when isOpen transitions from false to true", async () => {
      const user = userEvent.setup();
      const { rerender } = renderDrawer({ entityType: "taxonomy", isOpen: true });

      await user.type(screen.getByTestId("create-drawer-title-input"), "Some Title");

      act(() => {
        rerender(
          <CreateDrawer
            entityType="taxonomy"
            isOpen={false}
            onClose={vi.fn()}
          />,
        );
      });

      act(() => {
        rerender(
          <CreateDrawer
            entityType="taxonomy"
            isOpen={true}
            onClose={vi.fn()}
          />,
        );
      });

      const titleInput = screen.getByTestId("create-drawer-title-input") as HTMLInputElement;
      expect(titleInput.value).toBe("");
    });
  });

  describe("FormValues.relevance type", () => {
    it("property form renders relevance control with correct options", () => {
      renderDrawer({ entityType: "property" });
      expect(screen.getByTestId("create-drawer-relevance-control")).toBeInTheDocument();
    });
  });

  describe("initial values", () => {
    it("pre-fills title from initialValues", () => {
      renderDrawer({ entityType: "taxonomy", initialValues: { title: "Prefilled" } });
      const input = screen.getByTestId("create-drawer-title-input") as HTMLInputElement;
      expect(input.value).toBe("Prefilled");
    });

    it("pre-fills taxonomyId from initialTaxonomyId", () => {
      renderDrawer({ entityType: "scheme", initialTaxonomyId: "tax-1" });
      expect(screen.getByTestId("create-drawer-create-btn")).toBeDisabled();
    });
  });
});
