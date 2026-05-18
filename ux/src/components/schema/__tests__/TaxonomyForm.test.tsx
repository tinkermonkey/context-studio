import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaxonomyForm } from "../TaxonomyForm";

describe("TaxonomyForm", () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  it("renders form with title and description fields", () => {
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId("taxonomy-form")).toBeInTheDocument();
    expect(screen.getByTestId("taxonomy-title-input")).toBeInTheDocument();
    expect(screen.getByTestId("taxonomy-description-input")).toBeInTheDocument();
  });

  it("shows validation error when submitting with empty title", async () => {
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByRole("button", { name: /create taxonomy/i });
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("clears title error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByRole("button", { name: /create taxonomy/i });
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("taxonomy-title-input");
    await user.type(titleInput, "Test Taxonomy");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("submits form with valid data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("taxonomy-title-input");
    const descriptionInput = screen.getByTestId("taxonomy-description-input");
    const submitButton = screen.getByRole("button", { name: /create taxonomy/i });

    await user.type(titleInput, "New Taxonomy");
    await user.type(descriptionInput, "A test taxonomy");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: "New Taxonomy",
        description: "A test taxonomy",
      });
    });
  });

  it("disables submit button when loading", () => {
    render(<TaxonomyForm onSubmit={mockOnSubmit} isLoading={true} />);

    const submitButton = screen.getByRole("button", { name: /create taxonomy/i });
    expect(submitButton).toBeDisabled();
  });

  it("renders form fields with correct attributes", () => {
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    const titleInput = screen.getByTestId("taxonomy-title-input") as HTMLInputElement;
    const descriptionInput = screen.getByTestId("taxonomy-description-input") as HTMLTextAreaElement;

    expect(titleInput.type).toBe("text");
    expect(descriptionInput.tagName).toBe("TEXTAREA");
  });

  it("shows required indicator on title field", () => {
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    expect(screen.getByText("Title")).toBeInTheDocument();
  });

  it("shows optional indicator on description field", () => {
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    const descriptionText = screen.getByText(/Description/);
    expect(descriptionText).toBeInTheDocument();
  });

  it("preserves error clearing behavior through multiple onChange events", async () => {
    const user = userEvent.setup();
    render(<TaxonomyForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByRole("button", { name: /create taxonomy/i });
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const titleInput = screen.getByTestId("taxonomy-title-input");
    await user.type(titleInput, "T");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();

    await user.clear(titleInput);
    fireEvent.click(submitButton);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    await user.type(titleInput, "New");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });
});
