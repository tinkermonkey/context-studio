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
import { ExportPanel } from "../ExportPanel";

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

    const { useInterchangeExport } = require("@/api/hooks/interchange");
    const { useTaxonomies } = require("@/api/hooks/taxonomies");
    const { useConceptSchemes } = require("@/api/hooks/conceptSchemes");

    useTaxonomies.mockReturnValue({
      data: [
        {
          id: "tax-1",
          title: "Test Taxonomy",
          description: "Test description",
        },
      ],
    });

    useConceptSchemes.mockReturnValue({
      data: [
        {
          id: "scheme-1",
          title: "Test Scheme",
          description: "Test description",
        },
      ],
    });

    useInterchangeExport.mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });
  });

  it("renders export panel with format selector", () => {
    render(<ExportPanel />);

    expect(screen.getByTestId("interchange-export-panel")).toBeInTheDocument();
    expect(screen.getByText("Export Format")).toBeInTheDocument();
  });

  it("has SKOS as default format", () => {
    render(<ExportPanel />);

    const formatSelect = screen.getByDisplayValue("skos") as HTMLSelectElement;
    expect(formatSelect).toBeInTheDocument();
  });

  it("allows changing export format", () => {
    render(<ExportPanel />);

    const formatSelect = screen.getByDisplayValue("skos") as HTMLSelectElement;
    fireEvent.change(formatSelect, { target: { value: "owl" } });

    expect((formatSelect as HTMLSelectElement).value).toBe("owl");
  });

  it("renders scope type selector", () => {
    render(<ExportPanel />);

    expect(screen.getByLabelText(/scope/i)).toBeInTheDocument();
  });

  it("shows taxonomy selector when taxonomy scope is selected", async () => {
    render(<ExportPanel />);

    const scopeSelect = screen.getByDisplayValue("whole_graph") as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "taxonomy" } });

    await waitFor(() => {
      expect(screen.getByText("Select Taxonomy")).toBeInTheDocument();
    });
  });

  it("shows scheme selector when scheme scope is selected", async () => {
    render(<ExportPanel />);

    const scopeSelect = screen.getByDisplayValue("whole_graph") as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "scheme" } });

    await waitFor(() => {
      expect(screen.getByText("Select Concept Scheme")).toBeInTheDocument();
    });
  });

  it("renders export button", () => {
    render(<ExportPanel />);

    const exportButton = screen.getByRole("button", { name: /export/i });
    expect(exportButton).toBeInTheDocument();
  });

  it("shows error when exporting taxonomy without selecting one", async () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockError = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: mockError,
      info: vi.fn(),
    });

    render(<ExportPanel />);

    const scopeSelect = screen.getByDisplayValue("whole_graph") as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "taxonomy" } });

    const exportButton = screen.getByRole("button", { name: /export/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(mockError).toHaveBeenCalledWith("Please select a taxonomy");
    });
  });

  it("shows error when exporting scheme without selecting one", async () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockError = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: mockError,
      info: vi.fn(),
    });

    render(<ExportPanel />);

    const scopeSelect = screen.getByDisplayValue("whole_graph") as HTMLSelectElement;
    fireEvent.change(scopeSelect, { target: { value: "scheme" } });

    const exportButton = screen.getByRole("button", { name: /export/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(mockError).toHaveBeenCalledWith(
        "Please select a concept scheme"
      );
    });
  });

  it("calls export mutation with correct parameters", async () => {
    const { useInterchangeExport } = require("@/api/hooks/interchange");
    const mockMutate = vi.fn();
    useInterchangeExport.mockReturnValue({
      mutate: mockMutate,
      isLoading: false,
    });

    render(<ExportPanel />);

    const exportButton = screen.getByRole("button", { name: /export/i });
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
});
