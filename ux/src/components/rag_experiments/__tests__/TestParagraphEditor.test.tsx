/**
 * TestParagraphEditor Component Tests
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TestParagraphEditor } from "../TestParagraphEditor";
import type { TestParagraphResponse } from "@/api/services/ragExperiments";

// Mock the hooks
jest.mock("@/api/hooks/ragExperiments", () => ({
  useCreateTestParagraph: () => ({
    mutate: jest.fn(),
    isPending: false,
    isSuccess: false,
    error: null,
    data: null,
  }),
  useUpdateTestParagraph: () => ({
    mutate: jest.fn(),
    isPending: false,
    isSuccess: false,
    error: null,
    data: null,
  }),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("TestParagraphEditor", () => {
  it("renders create form when no paragraph provided", () => {
    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    expect(screen.getByLabelText(/Paragraph Text/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Notes/i)).toBeInTheDocument();
    expect(screen.getByText(/Create Paragraph/i)).toBeInTheDocument();
  });

  it("renders edit form when paragraph provided", () => {
    const paragraph: TestParagraphResponse = {
      id: "test-id",
      text: "Test paragraph text",
      notes: "Test notes",
      created_at: new Date().toISOString(),
      annotations: [],
    };

    render(<TestParagraphEditor paragraph={paragraph} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByDisplayValue("Test paragraph text")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Test notes")).toBeInTheDocument();
    expect(screen.getByText(/Update Paragraph/i)).toBeInTheDocument();
  });

  it("shows character count", () => {
    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByLabelText(/Paragraph Text/i);
    fireEvent.change(textarea, { target: { value: "Hello" } });

    expect(screen.getByText("5 characters")).toBeInTheDocument();
  });

  it("disables submit button when text is empty", () => {
    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    const submitButton = screen.getByText(/Create Paragraph/i);
    expect(submitButton).toBeDisabled();
  });

  it("enables submit button when text is provided", () => {
    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByLabelText(/Paragraph Text/i);
    fireEvent.change(textarea, { target: { value: "Test text" } });

    const submitButton = screen.getByText(/Create Paragraph/i);
    expect(submitButton).not.toBeDisabled();
  });
});
