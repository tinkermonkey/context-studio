import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GroundingWorkflowForm } from "../GroundingWorkflowForm";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", () => ({
  useReferenceStatus: vi.fn(),
  useClasses: vi.fn(),
}));

describe("GroundingWorkflowForm", () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
    vi.mocked(hooks.useReferenceStatus).mockReturnValue({
      data: {
        sources: [
          { name: "source-1", status: "ready" },
          { name: "source-2", status: "ready" },
        ],
      },
    } as any);
    vi.mocked(hooks.useClasses).mockReturnValue({
      data: {
        items: [
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
        ],
      },
    } as any);
  });

  it("renders form with title, source, and scope fields", () => {
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId("grounding-workflow-form")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-title-input")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-source-select")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-scope-input")).toBeInTheDocument();
  });

  it("shows title error when submitting with empty title", async () => {
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("workflow-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("shows source error when submitting without selecting source", async () => {
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("workflow-title-input");
    await user.type(titleInput, "Test Workflow");

    const submitButton = screen.getByTestId("workflow-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Source is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("shows scope error when submitting without selecting classes", async () => {
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("workflow-title-input");
    const sourceSelect = screen.getByTestId("workflow-source-select");

    await user.type(titleInput, "Test Workflow");
    await user.selectOptions(sourceSelect, "source-1");

    const submitButton = screen.getByTestId("workflow-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("At least one class scope is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("clears title error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("workflow-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("workflow-title-input");
    await user.type(titleInput, "Test Workflow");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("clears source error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("workflow-title-input");
    await user.type(titleInput, "Test Workflow");

    const submitButton = screen.getByTestId("workflow-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Source is required")).toBeInTheDocument();

    const sourceSelect = screen.getByTestId("workflow-source-select");
    await user.selectOptions(sourceSelect, "source-1");

    expect(screen.queryByText("Source is required")).not.toBeInTheDocument();
  });

  it("clears scope error when adding a class", async () => {
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("workflow-title-input");
    const sourceSelect = screen.getByTestId("workflow-source-select");

    await user.type(titleInput, "Test Workflow");
    await user.selectOptions(sourceSelect, "source-1");

    const submitButton = screen.getByTestId("workflow-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("At least one class scope is required")).toBeInTheDocument();

    const scopeInput = screen.getByTestId("workflow-scope-input");
    await user.click(scopeInput);
    await user.type(scopeInput, "Class");

    const classOption = await screen.findByTestId("workflow-scope-option-class-1");
    await user.click(classOption);

    expect(screen.queryByText("At least one class scope is required")).not.toBeInTheDocument();
  });

  it("submits form with valid data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("workflow-title-input");
    const sourceSelect = screen.getByTestId("workflow-source-select");
    const scopeInput = screen.getByTestId("workflow-scope-input");
    const submitButton = screen.getByTestId("workflow-submit-button");

    await user.type(titleInput, "Test Workflow");
    await user.selectOptions(sourceSelect, "source-1");
    await user.click(scopeInput);
    await user.type(scopeInput, "Class");

    const classOption = await screen.findByTestId("workflow-scope-option-class-1");
    await user.click(classOption);

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "Test Workflow",
        source: "source-1",
        class_scope: ["class-1"],
      });
    });
  });

  it("can select multiple classes", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("workflow-title-input");
    const sourceSelect = screen.getByTestId("workflow-source-select");
    const scopeInput = screen.getByTestId("workflow-scope-input");

    await user.type(titleInput, "Test Workflow");
    await user.selectOptions(sourceSelect, "source-1");

    await user.click(scopeInput);
    await user.type(scopeInput, "Class");

    const classOption1 = await screen.findByTestId("workflow-scope-option-class-1");
    await user.click(classOption1);

    await user.click(scopeInput);
    await user.clear(scopeInput);
    await user.type(scopeInput, "Class");

    const classOption2 = await screen.findByTestId("workflow-scope-option-class-2");
    await user.click(classOption2);

    const submitButton = screen.getByTestId("workflow-submit-button");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "Test Workflow",
        source: "source-1",
        class_scope: ["class-1", "class-2"],
      });
    });
  });

  it("removes a selected class when remove button is clicked", async () => {
    const user = userEvent.setup();
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("workflow-title-input");
    const scopeInput = screen.getByTestId("workflow-scope-input");

    await user.type(titleInput, "Test Workflow");
    await user.click(scopeInput);
    await user.type(scopeInput, "Class");

    const classOption = await screen.findByTestId("workflow-scope-option-class-1");
    await user.click(classOption);

    expect(screen.getByTestId("workflow-class-chip-class-1")).toBeInTheDocument();

    const removeButton = screen.getByTestId("workflow-class-remove-class-1");
    await user.click(removeButton);

    expect(screen.queryByTestId("workflow-class-chip-class-1")).not.toBeInTheDocument();
  });

  it("disables submit button when loading", () => {
    render(<GroundingWorkflowForm onSubmit={mockOnSubmit} isLoading={true} />);

    const submitButton = screen.getByTestId("workflow-submit-button");
    expect(submitButton).toBeDisabled();
  });
});
