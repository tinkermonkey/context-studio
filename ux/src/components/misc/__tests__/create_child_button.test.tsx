import React from "react";
import { vi } from "vitest";
import {
  renderWithProviders as render,
  screen,
  fireEvent,
} from "@/test/utils/renderWithProviders";
import { CreateChildButton } from "../create_child_button";

// Mock the form components
vi.mock("@/components/forms/domain_form", () => ({
  DomainForm: ({ onSuccess }: { onSuccess: (domain: any) => void }) => (
    <div data-testid="domain-form">
      <button onClick={() => onSuccess({ id: "1", title: "Test Domain" })}>
        Submit Domain
      </button>
    </div>
  ),
}));

vi.mock("@/components/forms/term_form", () => ({
  TermForm: ({ onSuccess }: { onSuccess: (term: any) => void }) => (
    <div data-testid="term-form">
      <button onClick={() => onSuccess({ id: "1", title: "Test Term" })}>
        Submit Term
      </button>
    </div>
  ),
}));

// test/utils/renderWithProviders handles creating a test QueryClient

describe("CreateChildButton", () => {
  const mockLayer = {
    id: "layer-1",
    title: "Test Layer",
    definition: "Test definition",
    created_at: "2023-01-01T00:00:00Z",
  };

  const mockDomain = {
    id: "domain-1",
    title: "Test Domain",
    definition: "Test definition",
    layer_id: "layer-1",
    created_at: "2023-01-01T00:00:00Z",
  };

  it("renders create domain button for layer parent", () => {
    render(
      <CreateChildButton
        parentType="layer"
        parentId="layer-1"
        parentObject={mockLayer}
        childType="domain"
      />,
    );

    expect(screen.getByRole("button", { name: /add/i })).toBeInTheDocument();
  });

  it("opens modal when button is clicked", () => {
    render(
      <CreateChildButton
        parentType="layer"
        parentId="layer-1"
        parentObject={mockLayer}
        childType="domain"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(
      screen.getByText(/Create Domain in Layer: Test Layer/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("domain-form")).toBeInTheDocument();
  });

  it("renders create term button for domain parent", () => {
    render(
      <CreateChildButton
        parentType="domain"
        parentId="domain-1"
        parentObject={mockDomain}
        childType="term"
      />,
    );

    expect(screen.getByRole("button", { name: /add/i })).toBeInTheDocument();
  });

  it("calls onSuccess when form is submitted", () => {
    const onSuccess = vi.fn();

    render(
      <CreateChildButton
        parentType="layer"
        parentId="layer-1"
        parentObject={mockLayer}
        childType="domain"
        onSuccess={onSuccess}
      />,
    );

    // Open modal
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    // Submit form
    fireEvent.click(screen.getByText("Submit Domain"));

    expect(onSuccess).toHaveBeenCalledWith({ id: "1", title: "Test Domain" });
  });
});
