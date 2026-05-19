import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SchemeForm } from "../SchemeForm";

describe("SchemeForm", () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  it("renders form with title and description fields", () => {
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId("scheme-form")).toBeInTheDocument();
    expect(screen.getByTestId("scheme-title-input")).toBeInTheDocument();
    expect(screen.getByTestId("scheme-description-input")).toBeInTheDocument();
  });

  it("shows validation error when submitting with empty title", async () => {
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("scheme-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("clears title error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("scheme-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("scheme-title-input");
    await user.type(titleInput, "Test Scheme");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("submits form with valid data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("scheme-title-input");
    const descriptionInput = screen.getByTestId("scheme-description-input");
    const submitButton = screen.getByTestId("scheme-submit-button");

    await user.type(titleInput, "New Scheme");
    await user.type(descriptionInput, "A test scheme");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "New Scheme",
        description: "A test scheme",
      });
    });
  });

  it("submits with null description when empty", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("scheme-title-input");
    const submitButton = screen.getByTestId("scheme-submit-button");

    await user.type(titleInput, "New Scheme");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "New Scheme",
        description: null,
      });
    });
  });

  it("disables submit button when loading", () => {
    render(<SchemeForm onSubmit={mockOnSubmit} isLoading={true} />);

    const submitButton = screen.getByTestId("scheme-submit-button");
    expect(submitButton).toBeDisabled();
  });

  it("renders form with proper field attributes", () => {
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("scheme-title-input") as HTMLInputElement;
    expect(titleInput.type).toBe("text");
    expect(titleInput.placeholder).toBe("Scheme name");
  });

  it("shows required indicator on title field", () => {
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    expect(screen.getByText("Title")).toBeInTheDocument();
  });

  it("clears error state during continued form interaction", async () => {
    const user = userEvent.setup();
    render(<SchemeForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("scheme-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("scheme-title-input");
    await user.type(titleInput, "Test");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();

    const descriptionInput = screen.getByTestId("scheme-description-input");
    await user.type(descriptionInput, "Description");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });
});
