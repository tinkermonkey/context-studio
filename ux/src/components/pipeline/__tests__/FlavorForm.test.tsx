import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FlavorForm } from "../FlavorForm";

describe("FlavorForm", () => {
  const mockOnSubmit = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
    mockOnCancel.mockClear();
  });

  it("renders form with name and description fields", () => {
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId("flavor-form")).toBeInTheDocument();
    expect(screen.getByTestId("flavor-name-input")).toBeInTheDocument();
    expect(screen.getByTestId("flavor-description-input")).toBeInTheDocument();
    expect(screen.getByTestId("flavor-submit-button")).toBeInTheDocument();
  });

  it("shows name error when submitting with empty name", async () => {
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const descriptionInput = screen.getByTestId("flavor-description-input");
    await userEvent.type(descriptionInput, "Description");

    const submitButton = screen.getByTestId("flavor-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Name is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("shows description error when submitting with empty description", async () => {
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByTestId("flavor-name-input");
    await userEvent.type(nameInput, "Flavor Name");

    const submitButton = screen.getByTestId("flavor-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Description is required")).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("clears name error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId("flavor-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Name is required")).toBeInTheDocument();

    const nameInput = screen.getByTestId("flavor-name-input");
    await user.type(nameInput, "Test Flavor");

    expect(screen.queryByText("Name is required")).not.toBeInTheDocument();
  });

  it("clears description error on onChange after failed submission", async () => {
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByTestId("flavor-name-input");
    await user.type(nameInput, "Flavor Name");

    const submitButton = screen.getByTestId("flavor-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Description is required")).toBeInTheDocument();

    const descriptionInput = screen.getByTestId("flavor-description-input");
    await user.type(descriptionInput, "Test Description");

    expect(screen.queryByText("Description is required")).not.toBeInTheDocument();
  });

  it("submits form with valid data", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByTestId("flavor-name-input");
    const descriptionInput = screen.getByTestId("flavor-description-input");
    const submitButton = screen.getByTestId("flavor-submit-button");

    await user.type(nameInput, "New Flavor");
    await user.type(descriptionInput, "A test flavor");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        name: "New Flavor",
        description: "A test flavor",
        steps: [],
      });
    });
  });

  it("clears form after successful submission", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByTestId("flavor-name-input") as HTMLInputElement;
    const descriptionInput = screen.getByTestId("flavor-description-input") as HTMLInputElement;
    const submitButton = screen.getByTestId("flavor-submit-button");

    await user.type(nameInput, "New Flavor");
    await user.type(descriptionInput, "A test flavor");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(nameInput.value).toBe("");
      expect(descriptionInput.value).toBe("");
    });
  });

  it("shows form error when submission fails", async () => {
    const error = new Error("Failed to create flavor");
    mockOnSubmit.mockRejectedValue(error);
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByTestId("flavor-name-input");
    const descriptionInput = screen.getByTestId("flavor-description-input");
    const submitButton = screen.getByTestId("flavor-submit-button");

    await user.type(nameInput, "New Flavor");
    await user.type(descriptionInput, "A test flavor");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByTestId("flavor-form-error")).toBeInTheDocument();
      expect(screen.getByText("Failed to create flavor")).toBeInTheDocument();
    });
  });

  it("disables submit button when loading", () => {
    render(<FlavorForm onSubmit={mockOnSubmit} isLoading={true} />);

    const submitButton = screen.getByTestId("flavor-submit-button");
    expect(submitButton).toBeDisabled();
    expect(submitButton).toHaveTextContent("Saving...");
  });

  it("calls onCancel when cancel button is clicked", async () => {
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} onCancel={mockOnCancel} />);

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    await user.click(cancelButton);

    expect(mockOnCancel).toHaveBeenCalled();
  });

  it("renders input fields with correct attributes and types", () => {
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByTestId("flavor-name-input") as HTMLInputElement;
    const descriptionInput = screen.getByTestId("flavor-description-input") as HTMLInputElement;

    expect(nameInput.type).toBe("text");
    expect(descriptionInput.type).toBe("text");
  });

  it("shows field labels and required indicators", () => {
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
  });

  it("clears name error immediately when user starts typing", async () => {
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const descriptionInput = screen.getByTestId("flavor-description-input");
    await user.type(descriptionInput, "Description");

    const submitButton = screen.getByTestId("flavor-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Name is required")).toBeInTheDocument();

    const nameInput = screen.getByTestId("flavor-name-input");
    await user.type(nameInput, "X");

    expect(screen.queryByText("Name is required")).not.toBeInTheDocument();
  });

  it("clears description error immediately when user starts typing", async () => {
    const user = userEvent.setup();
    render(<FlavorForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByTestId("flavor-name-input");
    await user.type(nameInput, "Name");

    const submitButton = screen.getByTestId("flavor-submit-button");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Description is required")).toBeInTheDocument();

    const descriptionInput = screen.getByTestId("flavor-description-input");
    await user.type(descriptionInput, "X");

    expect(screen.queryByText("Description is required")).not.toBeInTheDocument();
  });
});
