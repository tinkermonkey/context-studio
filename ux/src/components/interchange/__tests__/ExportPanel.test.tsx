/**
 * Tests for ExportPanel component
 */

import React from "react";
import { fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import {
  renderWithProviders as render,
  screen,
} from "@/test/utils/renderWithProviders";

// Mock flowbite-react components
vi.mock("flowbite-react", async () => {
  const actual = await vi.importActual("flowbite-react");
  return {
    ...(actual as object),
    Select: (props: any) => {
      const { children, ...rest } = props;
      return React.createElement("select", rest, children);
    },
  };
});

import { ExportPanel } from "../ExportPanel";
import * as interchangeHooks from "@/api/hooks/interchange";
import * as taxonomyHooks from "@/api/hooks/taxonomies";
import * as conceptSchemeHooks from "@/api/hooks/conceptSchemes";
import * as toastHook from "@/hooks/useButterToast";

// Mock the API hooks
vi.mock("@/api/hooks/interchange", () => ({
  useInterchangeExport: vi.fn(),
}));

vi.mock("@/api/hooks/taxonomies", () => ({
  useTaxonomies: vi.fn(),
}));

vi.mock("@/api/hooks/conceptSchemes", () => ({
  useConceptSchemes: vi.fn(),
}));

vi.mock("@/hooks/useButterToast", () => ({
  useButterToast: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  })),
}));

describe("ExportPanel", () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks();

    vi.mocked(taxonomyHooks.useTaxonomies).mockReturnValue({
      data: [
        {
          id: "tax-1",
          title: "Test Taxonomy",
          description: "Test description",
        },
      ],
    } as any);

    vi.mocked(conceptSchemeHooks.useConceptSchemes).mockReturnValue({
      data: [
        {
          id: "scheme-1",
          title: "Test Scheme",
          description: "Test description",
        },
      ],
    } as any);

    vi.mocked(interchangeHooks.useInterchangeExport).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      isSuccess: false,
    } as any);
  });

  it("renders export panel with format selector", () => {
    render(<ExportPanel />);

    expect(screen.getByTestId("interchange-export-panel")).toBeInTheDocument();
    expect(screen.getByText("Export Format")).toBeInTheDocument();
  });

  it("has SKOS as default format", () => {
    render(<ExportPanel />);

    const formatSelect = screen.getByTestId(
      "interchange-export-format-select",
    ) as HTMLSelectElement;
    expect(formatSelect).toBeInTheDocument();
    expect(formatSelect.value).toBe("skos");
  });

  it("allows changing export format", () => {
    render(<ExportPanel />);

    const formatSelect = screen.getByTestId(
      "interchange-export-format-select",
    ) as HTMLSelectElement;
    fireEvent.change(formatSelect, { target: { value: "owl" } });

    expect((formatSelect as HTMLSelectElement).value).toBe("owl");
  });

  it("renders scope type selector", () => {
    render(<ExportPanel />);

    expect(
      screen.getByTestId("interchange-export-scope-picker"),
    ).toBeInTheDocument();
  });

  it("shows taxonomy selector when taxonomy scope is selected", async () => {
    render(<ExportPanel />);

    const scopeSelect = screen.getByTestId(
      "interchange-export-scope-picker",
    ) as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "taxonomy" } });

    await waitFor(() => {
      expect(screen.getByText("Select Taxonomy")).toBeInTheDocument();
    });
  });

  it("shows scheme selector when scheme scope is selected", async () => {
    render(<ExportPanel />);

    const scopeSelect = screen.getByTestId(
      "interchange-export-scope-picker",
    ) as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "scheme" } });

    await waitFor(() => {
      expect(screen.getByText("Select Concept Scheme")).toBeInTheDocument();
    });
  });

  it("renders export button", () => {
    render(<ExportPanel />);

    const exportButton = screen.getByRole("button", { name: /download/i });
    expect(exportButton).toBeInTheDocument();
  });

  it("shows error when exporting taxonomy without selecting one", async () => {
    const useButterToast = vi.mocked(toastHook.useButterToast);
    const mockError = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: mockError,
      info: vi.fn(),
      warning: vi.fn(),
      show: vi.fn(),
    } as any);

    render(<ExportPanel />);

    const scopeSelect = screen.getByTestId(
      "interchange-export-scope-picker",
    ) as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "taxonomy" } });

    const exportButton = screen.getByRole("button", { name: /download/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(mockError).toHaveBeenCalledWith("Please select a taxonomy");
    });
  });

  it("shows error when exporting scheme without selecting one", async () => {
    const useButterToast = vi.mocked(toastHook.useButterToast);
    const mockError = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: mockError,
      info: vi.fn(),
      warning: vi.fn(),
      show: vi.fn(),
    } as any);

    render(<ExportPanel />);

    const scopeSelect = screen.getByTestId(
      "interchange-export-scope-picker",
    ) as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "scheme" } });

    const exportButton = screen.getByRole("button", { name: /download/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(mockError).toHaveBeenCalledWith("Please select a concept scheme");
    });
  });

  it("calls export mutation with correct parameters", async () => {
    const useInterchangeExport = vi.mocked(
      interchangeHooks.useInterchangeExport,
    );
    const mockMutate = vi.fn();
    useInterchangeExport.mockReturnValue({
      mutate: mockMutate,
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      isSuccess: false,
    } as any);

    render(<ExportPanel />);

    const exportButton = screen.getByRole("button", { name: /download/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith({
        format: "skos",
        scope: { scope_type: "whole_graph" },
      });
    });
  });

  it("has data-testid for accessibility testing", () => {
    render(<ExportPanel />);

    expect(screen.getByTestId("interchange-export-panel")).toBeInTheDocument();
  });

  describe("Taxonomy selector states", () => {
    it("shows loading message while taxonomies are loading", async () => {
      vi.mocked(taxonomyHooks.useTaxonomies).mockReturnValue({
        isLoading: true,
        data: undefined,
        error: null,
      } as any);

      render(<ExportPanel />);

      const scopeSelect = screen.getByTestId(
        "interchange-export-scope-picker",
      ) as HTMLSelectElement;
      fireEvent.change(scopeSelect, { target: { value: "taxonomy" } });

      await waitFor(() => {
        expect(screen.getByText("Loading taxonomies...")).toBeInTheDocument();
      });
    });

    it("shows error message when taxonomy fetch fails", async () => {
      vi.mocked(taxonomyHooks.useTaxonomies).mockReturnValue({
        isLoading: false,
        data: undefined,
        error: new Error("Failed to fetch"),
      } as any);

      render(<ExportPanel />);

      const scopeSelect = screen.getByTestId(
        "interchange-export-scope-picker",
      ) as HTMLSelectElement;
      fireEvent.change(scopeSelect, { target: { value: "taxonomy" } });

      await waitFor(() => {
        expect(
          screen.getByText("Failed to load taxonomies"),
        ).toBeInTheDocument();
      });
    });

    it("shows empty message when no taxonomies are available", async () => {
      vi.mocked(taxonomyHooks.useTaxonomies).mockReturnValue({
        isLoading: false,
        data: [],
        error: null,
      } as any);

      render(<ExportPanel />);

      const scopeSelect = screen.getByTestId(
        "interchange-export-scope-picker",
      ) as HTMLSelectElement;
      fireEvent.change(scopeSelect, { target: { value: "taxonomy" } });

      await waitFor(() => {
        expect(
          screen.getByText("No taxonomies available"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Concept scheme selector states", () => {
    it("shows loading message while concept schemes are loading", async () => {
      vi.mocked(conceptSchemeHooks.useConceptSchemes).mockReturnValue({
        isLoading: true,
        data: undefined,
        error: null,
      } as any);

      render(<ExportPanel />);

      const scopeSelect = screen.getByTestId(
        "interchange-export-scope-picker",
      ) as HTMLSelectElement;
      fireEvent.change(scopeSelect, { target: { value: "scheme" } });

      await waitFor(() => {
        expect(
          screen.getByText("Loading concept schemes..."),
        ).toBeInTheDocument();
      });
    });

    it("shows error message when concept scheme fetch fails", async () => {
      vi.mocked(conceptSchemeHooks.useConceptSchemes).mockReturnValue({
        isLoading: false,
        data: undefined,
        error: new Error("Failed to fetch"),
      } as any);

      render(<ExportPanel />);

      const scopeSelect = screen.getByTestId(
        "interchange-export-scope-picker",
      ) as HTMLSelectElement;
      fireEvent.change(scopeSelect, { target: { value: "scheme" } });

      await waitFor(() => {
        expect(
          screen.getByText("Failed to load concept schemes"),
        ).toBeInTheDocument();
      });
    });

    it("shows empty message when no concept schemes are available", async () => {
      vi.mocked(conceptSchemeHooks.useConceptSchemes).mockReturnValue({
        isLoading: false,
        data: [],
        error: null,
      } as any);

      render(<ExportPanel />);

      const scopeSelect = screen.getByTestId(
        "interchange-export-scope-picker",
      ) as HTMLSelectElement;
      fireEvent.change(scopeSelect, { target: { value: "scheme" } });

      await waitFor(() => {
        expect(
          screen.getByText("No concept schemes available"),
        ).toBeInTheDocument();
      });
    });
  });
});
