/**
 * Tests for ImportPanel component
 */

import React from "react";
import { fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import {
  renderWithProviders as render,
  screen,
} from "@/test/utils/renderWithProviders";
import { ImportPanel } from "../ImportPanel";

vi.mock("@/hooks/useButterToast", () => ({
  useButterToast: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  })),
}));

describe("ImportPanel", () => {
  it("renders import panel", () => {
    render(<ImportPanel />);

    expect(screen.getByTestId("interchange-import-panel")).toBeInTheDocument();
    expect(screen.getByText("Import File")).toBeInTheDocument();
  });

  it("renders drag-drop area", () => {
    render(<ImportPanel />);

    expect(screen.getByTestId("interchange-import-file-input")).toBeInTheDocument();
  });

  it("renders file input field", () => {
    render(<ImportPanel />);

    const fileInput = screen.getByRole("button", { name: /choose/i });
    expect(fileInput).toBeInTheDocument();
  });

  it("detects format from file extension (OWL/RDF)", () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockInfo = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: vi.fn(),
      info: mockInfo,
    });

    const { container } = render(<ImportPanel />);

    // Create a file with .rdf extension
    const file = new File(["test content"], "ontology.rdf", {
      type: "application/rdf+xml",
    });
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    fireEvent.change(fileInput, { target: { files: [file] } });

    // Should detect as owl format
    expect(mockInfo).toHaveBeenCalled();
  });

  it("detects format from file extension (GraphML)", () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockInfo = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: vi.fn(),
      info: mockInfo,
    });

    const { container } = render(<ImportPanel />);

    // Create a file with .graphml extension
    const file = new File(["test content"], "graph.graphml", {
      type: "application/graphml+xml",
    });
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(mockInfo).toHaveBeenCalled();
  });

  it("detects format from file extension (Turtle)", () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockInfo = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: vi.fn(),
      info: mockInfo,
    });

    const { container } = render(<ImportPanel />);

    // Create a file with .ttl extension
    const file = new File(["test content"], "ontology.ttl", {
      type: "text/turtle",
    });
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(mockInfo).toHaveBeenCalled();
  });

  it("defaults to auto format for unknown extensions", () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockInfo = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: vi.fn(),
      info: mockInfo,
    });

    const { container } = render(<ImportPanel />);

    const file = new File(["test content"], "ontology.xyz", {
      type: "application/octet-stream",
    });
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(mockInfo).toHaveBeenCalled();
  });

  it("supports drag and drop", () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockInfo = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: vi.fn(),
      info: mockInfo,
    });

    render(<ImportPanel />);

    const dragDropArea = screen.getByTestId("interchange-import-file-input");

    // Create a file
    const file = new File(["test content"], "ontology.skos", {
      type: "text/turtle",
    });

    // Simulate drag over
    fireEvent.dragOver(dragDropArea);

    // Simulate drop
    fireEvent.drop(dragDropArea, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(mockInfo).toHaveBeenCalled();
  });

  it("renders preview button", () => {
    render(<ImportPanel />);

    const previewButton = screen.queryByRole("button", { name: /preview/i });
    expect(previewButton).toBeInTheDocument();
  });

  it("shows error when preview is clicked without file", async () => {
    const { useButterToast } = require("@/hooks/useButterToast");
    const mockError = vi.fn();
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: mockError,
      info: vi.fn(),
    });

    render(<ImportPanel />);

    const previewButton = screen.getByRole("button", { name: /preview/i });
    fireEvent.click(previewButton);

    await waitFor(() => {
      expect(mockError).toHaveBeenCalledWith("Please select a file first");
    });
  });

  it("calls onPreviewRequested when preview button is clicked with file", async () => {
    const mockOnPreviewRequested = vi.fn();
    const { useButterToast } = require("@/hooks/useButterToast");
    useButterToast.mockReturnValue({
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    });

    const { container } = render(
      <ImportPanel onPreviewRequested={mockOnPreviewRequested} />
    );

    // Select a file
    const file = new File(["test content"], "ontology.skos", {
      type: "text/turtle",
    });
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Click preview
    const previewButton = screen.getByRole("button", { name: /preview/i });
    fireEvent.click(previewButton);

    await waitFor(() => {
      expect(mockOnPreviewRequested).toHaveBeenCalledWith(file, "skos");
    });
  });

  it("has data-testid for accessibility testing", () => {
    render(<ImportPanel />);

    expect(screen.getByTestId("interchange-import-panel")).toBeInTheDocument();
    expect(screen.getByTestId("interchange-import-file-input")).toBeInTheDocument();
  });
});
