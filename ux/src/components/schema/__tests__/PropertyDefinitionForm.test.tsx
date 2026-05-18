import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PropertyDefinitionForm } from "../PropertyDefinitionForm";
import type { components } from "@/api/types";

describe("PropertyDefinitionForm", () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  it("renders form with identifier, title, and description fields", () => {
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId("property-definition-form")).toBeInTheDocument();
    expect(screen.getByTestId("property-definition-identifier-input")).toBeInTheDocument();
    expect(screen.getByTestId("property-definition-title-input")).toBeInTheDocument();
    expect(screen.getByTestId("property-definition-description-input")).toBeInTheDocument();
  });

  it("shows identifier error when identifier is empty", async () => {
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("property-definition-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Identifier is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("shows identifier error when identifier has invalid format", async () => {
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    await user.type(identifierInput, "Invalid-Identifier");

    const submitButton = screen.getByTestId("property-definition-submit-button");
    fireEvent.click(submitButton);

    expect(
      await screen.findByText("Identifier must be lowercase with underscores only"),
    ).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("shows title error when title is empty", async () => {
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    await user.type(identifierInput, "test_identifier");

    const submitButton = screen.getByTestId("property-definition-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("clears identifier error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("property-definition-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Identifier is required")).toBeInTheDocument();

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    await user.type(identifierInput, "valid_id");

    expect(screen.queryByText("Identifier is required")).not.toBeInTheDocument();
  });

  it("clears title error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    await user.type(identifierInput, "test_id");

    const submitButton = screen.getByTestId("property-definition-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("property-definition-title-input");
    await user.type(titleInput, "Test Title");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("submits create form with valid data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    const titleInput = screen.getByTestId("property-definition-title-input");
    const descriptionInput = screen.getByTestId("property-definition-description-input");
    const submitButton = screen.getByTestId("property-definition-submit-button");

    await user.type(identifierInput, "test_property");
    await user.type(titleInput, "Test Property");
    await user.type(descriptionInput, "A test property");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        identifier: "test_property",
        title: "Test Property",
        description: "A test property",
      });
    });
  });

  it("submits update form with only title and description", async () => {
    const initialData: components["schemas"]["PropertyDefinitionResponse"] = {
      id: "prop-1",
      identifier: "test_property",
      title: "Old Title",
      description: "Old description",
      created_at: "",
      updated_at: "",
    };

    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<PropertyDefinitionForm initialData={initialData} onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("property-definition-title-input");
    const identifierInput = screen.getByTestId("property-definition-identifier-input");

    expect(identifierInput).toBeDisabled();

    await user.clear(titleInput);
    await user.type(titleInput, "New Title");

    const submitButton = screen.getByTestId("property-definition-submit-button");
    expect(submitButton).toHaveTextContent("Update Property");

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "New Title",
        description: "Old description",
      });
    });
  });

  it("disables submit button when loading", () => {
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} isLoading={true} />);

    const submitButton = screen.getByTestId("property-definition-submit-button");
    expect(submitButton).toBeDisabled();
  });

  it("renders form with proper field structure and attributes", () => {
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input") as HTMLInputElement;
    const titleInput = screen.getByTestId("property-definition-title-input") as HTMLInputElement;

    expect(identifierInput.type).toBe("text");
    expect(titleInput.type).toBe("text");
  });

  it("validates identifier format with specific error messages", async () => {
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    const submitButton = screen.getByTestId("property-definition-submit-button");

    await user.type(identifierInput, "Invalid-ID");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Identifier must be lowercase with underscores only")).toBeInTheDocument();
  });

  it("clears identifier error on onChange after failed validation", async () => {
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("property-definition-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Identifier is required")).toBeInTheDocument();

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    await user.type(identifierInput, "valid_id");

    expect(screen.queryByText("Identifier is required")).not.toBeInTheDocument();
  });

  it("clears title error on onChange after failed validation", async () => {
    const user = userEvent.setup();
    render(<PropertyDefinitionForm onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input");
    await user.type(identifierInput, "valid_id");

    const submitButton = screen.getByTestId("property-definition-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("property-definition-title-input");
    await user.type(titleInput, "Title");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("disables identifier field when editing existing property", () => {
    const initialData: components["schemas"]["PropertyDefinitionResponse"] = {
      id: "prop-1",
      identifier: "existing_id",
      title: "Existing",
      description: "",
      created_at: "",
      updated_at: "",
    };

    render(<PropertyDefinitionForm initialData={initialData} onSubmit={mockOnSubmit} />);

    const identifierInput = screen.getByTestId("property-definition-identifier-input") as HTMLInputElement;
    expect(identifierInput.disabled).toBe(true);
  });
});
