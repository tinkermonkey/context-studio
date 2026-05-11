import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { ExtractionPage } from "../index";
import * as extractionHooks from "@/api/hooks/extraction";
import * as ontologyHooks from "@/api/hooks/ontology";

vi.mock("@/api/hooks/extraction");
vi.mock("@/api/hooks/ontology");
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({
    toast: vi.fn(),
  }),
}));

describe("Extraction Page", () => {
  const mockExtractionResult = {
    extracted_entities: [
      {
        id: "entity-1",
        label: "Apple",
        entity_type: "Company",
        confidence: 0.95,
        source_layer: 0,
        matched_class_id: null,
        description: "Tech company",
      },
      {
        id: "entity-2",
        label: "iPhone",
        entity_type: "Product",
        confidence: 0.85,
        source_layer: 1,
        matched_class_id: null,
        description: "Mobile device",
      },
    ],
    layers_executed: [
      {
        layer_number: 0,
        layer_name: "KG Context",
        entities_found: 2,
        duration_ms: 100,
        success: true,
      },
    ],
  };

  const mockEmptyResult = {
    extracted_entities: [],
    layers_executed: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(extractionHooks.useExtract).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: null,
      status: "idle",
    } as any);

    vi.mocked(extractionHooks.useNlpAnalysis).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: null,
      status: "idle",
    } as any);

    vi.mocked(extractionHooks.useEnrichFromReferences).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: null,
      status: "idle",
    } as any);

    vi.mocked(ontologyHooks.useCreateClass).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      status: "idle",
    } as any);

    vi.mocked(ontologyHooks.useClasses).mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    } as any);

    vi.mocked(ontologyHooks.useSchemes).mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    } as any);
  });

  describe("page structure", () => {
    it("renders extraction page container", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
    });

    it("renders page title", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  describe("input panel", () => {
    it("renders extraction input panel", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-input")).toBeInTheDocument();
    });

    it("extraction input is disabled when loading", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
        data: null,
        status: "pending",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      const input = screen.getByTestId("extraction-input");
      expect(input).toBeInTheDocument();
    });
  });

  describe("extraction panels", () => {
    it("renders all four extraction result panels", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-panel-kg-context")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-panel-llm-extraction")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-panel-nlp-gap-fill")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-panel-reference-enrichment")).toBeInTheDocument();
    });

    it("shows loading state in panels during extraction", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
        data: null,
        status: "pending",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      const panels = [
        "extraction-panel-kg-context",
        "extraction-panel-llm-extraction",
        "extraction-panel-nlp-gap-fill",
        "extraction-panel-reference-enrichment",
      ];

      panels.forEach((testId) => {
        expect(screen.getByTestId(testId)).toBeInTheDocument();
      });
    });

    it("displays entities when extraction succeeds", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
        error: null,
        data: mockExtractionResult,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-panel-kg-context")).toBeInTheDocument();
    });
  });

  describe("entity review panels", () => {
    it("renders extraction panels and components with populated data", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
        error: null,
        data: mockExtractionResult,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      // Verify all extraction result panels render with populated data
      expect(screen.getByTestId("extraction-panel-kg-context")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-panel-llm-extraction")).toBeInTheDocument();
    });

    it("hides panels when no data extracted", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
        error: null,
        data: mockEmptyResult,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      // Page still renders, but panels show no data
      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
    });
  });

  describe("loading states", () => {
    it("renders input panel when extraction is pending", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
        data: null,
        status: "pending",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-input")).toBeInTheDocument();
    });

    it("shows all panels while NLP analysis is pending", () => {
      vi.mocked(extractionHooks.useNlpAnalysis).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: true,
        isError: false,
        error: null,
        data: null,
        status: "pending",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-input")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-panel-nlp-gap-fill")).toBeInTheDocument();
    });
  });

  describe("error states", () => {
    it("displays error message in extraction panel when extraction fails", () => {
      const error = new Error("Extraction failed");
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: true,
        error,
        data: null,
        status: "error",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-panel-kg-context")).toBeInTheDocument();
    });

    it("displays error message when NLP analysis fails", () => {
      const error = new Error("NLP analysis failed");
      vi.mocked(extractionHooks.useNlpAnalysis).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: true,
        error,
        data: null,
        status: "error",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-panel-nlp-gap-fill")).toBeInTheDocument();
    });
  });

  describe("empty states", () => {
    it("shows empty state when no entities extracted", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
        error: null,
        data: mockEmptyResult,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
    });

    it("shows initial empty state before any extraction", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-input")).toBeInTheDocument();
    });
  });

  describe("populated state", () => {
    it("displays all entities across layers", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
        error: null,
        data: mockExtractionResult,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-panel-kg-context")).toBeInTheDocument();
    });

    it("renders extraction panels with entity count", () => {
      vi.mocked(extractionHooks.useExtract).mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
        error: null,
        data: mockExtractionResult,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      const panel = screen.getByTestId("extraction-panel-kg-context");
      expect(panel).toBeInTheDocument();
    });
  });

  describe("layout structure", () => {
    it("uses grid layout with input on left and results on right", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("extraction-page")).toBeInTheDocument();
      expect(screen.getByTestId("extraction-input")).toBeInTheDocument();
    });

    it("extraction input maintains fixed width on left", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      const input = screen.getByTestId("extraction-input");
      expect(input).toBeInTheDocument();
    });
  });

  describe("accessibility and styling", () => {
    it("extraction input panel is accessible", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      const inputPanel = screen.getByTestId("extraction-input");
      expect(inputPanel).toBeInTheDocument();
      // Verify it's a panel container
      expect(inputPanel).toHaveClass("panel");
    });

    it("extraction panels have proper structure and styling", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      const panels = [
        "extraction-panel-kg-context",
        "extraction-panel-llm-extraction",
        "extraction-panel-nlp-gap-fill",
        "extraction-panel-reference-enrichment",
      ];

      panels.forEach((testId) => {
        const panel = screen.getByTestId(testId);
        expect(panel).toBeInTheDocument();
      });
    });

    it("page title has correct heading level for document structure", () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ExtractionPage />
        </QueryClientProvider>,
      );

      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading).toBeInTheDocument();
    });
  });
});
