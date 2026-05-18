import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RelationshipForm } from "../RelationshipForm";
import type { components } from "@/api/types";

describe("RelationshipForm", () => {
  const mockOnSubmit = vi.fn();
  const mockClasses: components["schemas"]["ClassResponse"][] = [
    {
      id: "class-1",
      title: "Class 1",
      concept_scheme_id: "scheme-1",
      taxonomy_id: "tax-1",
      version: 1,
      status: "draft",
    },
    {
      id: "class-2",
      title: "Class 2",
      concept_scheme_id: "scheme-1",
      taxonomy_id: "tax-1",
      version: 1,
      status: "draft",
    },
  ];
  const mockProperties: components["schemas"]["PropertyDefinitionResponse"][] = [
    { id: "prop-1", identifier: "prop_1", title: "Property 1", version: 1, status: "draft" },
    { id: "prop-2", identifier: "prop_2", title: "Property 2", version: 1, status: "draft" },
  ];

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  it("renders form with source, target, and type selects", () => {
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    expect(screen.getByTestId("relationship-form")).toBeInTheDocument();
    expect(screen.getByTestId("relationship-source-select")).toBeInTheDocument();
    expect(screen.getByTestId("relationship-target-select")).toBeInTheDocument();
    expect(screen.getByTestId("relationship-type-select")).toBeInTheDocument();
  });

  it("shows validation errors when submitting with empty fields", async () => {
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const submitButton = screen.getByTestId("relationship-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Source class is required")).toBeInTheDocument();
    expect(await screen.findByText("Target class is required")).toBeInTheDocument();
    expect(await screen.findByText("Relationship type is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("clears source error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const submitButton = screen.getByTestId("relationship-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Source class is required")).toBeInTheDocument();

    const sourceSelect = screen.getByTestId("relationship-source-select");
    await user.selectOptions(sourceSelect, "class-1");

    expect(screen.queryByText("Source class is required")).not.toBeInTheDocument();
  });

  it("clears target error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const submitButton = screen.getByTestId("relationship-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Target class is required")).toBeInTheDocument();

    const targetSelect = screen.getByTestId("relationship-target-select");
    await user.selectOptions(targetSelect, "class-1");

    expect(screen.queryByText("Target class is required")).not.toBeInTheDocument();
  });

  it("clears type error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const submitButton = screen.getByTestId("relationship-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Relationship type is required")).toBeInTheDocument();

    const typeSelect = screen.getByTestId("relationship-type-select");
    await user.selectOptions(typeSelect, "prop_1");

    expect(screen.queryByText("Relationship type is required")).not.toBeInTheDocument();
  });

  it("submits form with valid data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const sourceSelect = screen.getByTestId("relationship-source-select");
    const targetSelect = screen.getByTestId("relationship-target-select");
    const typeSelect = screen.getByTestId("relationship-type-select");
    const submitButton = screen.getByTestId("relationship-submit-button");

    await user.selectOptions(sourceSelect, "class-1");
    await user.selectOptions(targetSelect, "class-2");
    await user.selectOptions(typeSelect, "prop_1");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        source_id: "class-1",
        target_id: "class-2",
        relationship_type: "prop_1",
      });
    });
  });

  it("disables submit button when loading", () => {
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
        isLoading={true}
      />,
    );

    const submitButton = screen.getByTestId("relationship-submit-button");
    expect(submitButton).toBeDisabled();
  });

  it("renders select fields with correct structure", () => {
    const { container } = render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const selects = container.querySelectorAll("select");
    expect(selects.length).toBeGreaterThanOrEqual(3);
  });

  it("clears source error on onChange after validation failure", async () => {
    const user = userEvent.setup();
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const submitButton = screen.getByTestId("relationship-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Source class is required")).toBeInTheDocument();

    const sourceSelect = screen.getByTestId("relationship-source-select");
    await user.selectOptions(sourceSelect, "class-1");

    expect(screen.queryByText("Source class is required")).not.toBeInTheDocument();
  });

  it("preserves other field errors when one field is corrected", async () => {
    const user = userEvent.setup();
    render(
      <RelationshipForm
        onSubmit={mockOnSubmit}
        classes={mockClasses}
        properties={mockProperties}
      />,
    );

    const submitButton = screen.getByTestId("relationship-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Source class is required")).toBeInTheDocument();

    const sourceSelect = screen.getByTestId("relationship-source-select");
    await user.selectOptions(sourceSelect, "class-1");

    expect(await screen.findByText("Target class is required")).toBeInTheDocument();
  });
});
