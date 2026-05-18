import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ClassForm } from "../ClassForm";

describe("ClassForm", () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  it("renders form with title and description fields", () => {
    render(<ClassForm onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId("class-form")).toBeInTheDocument();
    expect(screen.getByTestId("class-title-input")).toBeInTheDocument();
    expect(screen.getByTestId("class-description-input")).toBeInTheDocument();
    expect(screen.getByTestId("class-submit-button")).toBeInTheDocument();
  });

  it("shows validation error when submitting with empty title", async () => {
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("class-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("clears title error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("class-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("class-title-input");
    await user.type(titleInput, "Test Class");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("submits form with valid data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("class-title-input");
    const descriptionInput = screen.getByTestId("class-description-input");
    const submitButton = screen.getByTestId("class-submit-button");

    await user.type(titleInput, "New Class");
    await user.type(descriptionInput, "A test class");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "New Class",
        description: "A test class",
      });
    });
  });

  it("submits with null description when empty", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("class-title-input");
    const submitButton = screen.getByTestId("class-submit-button");

    await user.type(titleInput, "New Class");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "New Class",
        description: null,
      });
    });
  });

  it("disables submit button when loading", () => {
    render(<ClassForm onSubmit={mockOnSubmit} isLoading={true} />);

    const submitButton = screen.getByTestId("class-submit-button");
    expect(submitButton).toBeDisabled();
  });

  it("does not submit when title is only whitespace", async () => {
    const user = userEvent.setup();
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("class-title-input");
    const submitButton = screen.getByTestId("class-submit-button");

    await user.type(titleInput, "   ");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("renders title field with required indicator", () => {
    render(<ClassForm onSubmit={mockOnSubmit} />);

    expect(screen.getByText("Title")).toBeInTheDocument();
  });

  it("renders description field as optional", () => {
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const descriptionText = screen.getByText(/Description \(optional\)/);
    expect(descriptionText).toBeInTheDocument();
  });

  it("displays field with correct accessibility attributes", () => {
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("class-title-input");
    expect(titleInput).toHaveAttribute("type", "text");
    expect(titleInput).toHaveAttribute("placeholder", "Class name");
  });

  it("displays description textarea with correct attributes", () => {
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const descriptionInput = screen.getByTestId("class-description-input") as HTMLTextAreaElement;
    expect(descriptionInput).toHaveAttribute("placeholder", "Optional description");
    expect(descriptionInput.rows).toBe(4);
  });

  it("clears error immediately on input focus and typing", async () => {
    const user = userEvent.setup();
    render(<ClassForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("class-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("class-title-input");
    await user.click(titleInput);
    await user.type(titleInput, "A");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });
});
