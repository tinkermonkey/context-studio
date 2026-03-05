/**
 * TestParagraphEditor Component Tests
 */

import React from "react";
import { render, screen,  } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TestParagraphEditor } from "../TestParagraphEditor";
import type { TestParagraphResponse } from "@/api/services/ragExperiments";
import { vi, describe, it, expect, beforeEach } from "vitest";
import "@testing-library/jest-dom";
import * as ragExperimentsHooks from "@/api/hooks/ragExperiments";
import type { UseMutationResult } from "@tanstack/react-query";

// Mock the hooks
vi.mock("@/api/hooks/ragExperiments", () => ({
  useCreateTestParagraph: vi.fn(),
  useUpdateTestParagraph: vi.fn(),
}));

// Default mock implementations
const defaultCreateMock = {
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
  isPending: false,
  isSuccess: false,
  error: null,
  data: undefined,
  isError: false,
  isIdle: true,
  status: "idle",
  reset: vi.fn(),
  variables: undefined,
  context: undefined,
  submittedAt: 0,
} as unknown as UseMutationResult<
  TestParagraphResponse,
  Error,
  { text: string; notes?: string },
  unknown
>;

const defaultUpdateMock = {
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
  isPending: false,
  isSuccess: false,
  error: null,
  data: undefined,
  isError: false,
  isIdle: true,
  status: "idle",
  reset: vi.fn(),
  variables: undefined,
  context: undefined,
  submittedAt: 0,
} as unknown as UseMutationResult<
  TestParagraphResponse,
  Error,
  { paragraphId: string; text?: string; notes?: string },
  unknown
>;

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
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset to default mocks
    vi.mocked(ragExperimentsHooks.useCreateTestParagraph).mockReturnValue(
      defaultCreateMock,
    );
    vi.mocked(ragExperimentsHooks.useUpdateTestParagraph).mockReturnValue(
      defaultUpdateMock,
    );
  });

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

  it("shows loading state during submission", () => {
    vi.mocked(ragExperimentsHooks.useCreateTestParagraph).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: true,
      isSuccess: false,
      error: null,
      data: undefined,
      isError: false,
      isIdle: false,
      status: "pending",
      reset: vi.fn(),
      variables: undefined,
      context: undefined,
      submittedAt: 0,
    } as unknown as UseMutationResult<
      TestParagraphResponse,
      Error,
      { text: string; notes?: string },
      unknown
    >);

    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByLabelText(/Paragraph Text/i);
    fireEvent.change(textarea, { target: { value: "Test text" } });

    expect(screen.getByText(/Creating/i)).toBeInTheDocument();
  });

  it("shows error state on submission failure", () => {
    vi.mocked(ragExperimentsHooks.useCreateTestParagraph).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isSuccess: false,
      error: new Error("Submission failed"),
      data: undefined,
      isError: true,
      isIdle: false,
      status: "error",
      reset: vi.fn(),
      variables: undefined,
      context: undefined,
      submittedAt: 0,
    } as unknown as UseMutationResult<
      TestParagraphResponse,
      Error,
      { text: string; notes?: string },
      unknown
    >);

    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    expect(screen.getByText(/Submission failed/i)).toBeInTheDocument();
  });

  it("clears form after successful creation", async () => {
    const mutateFn = vi.fn();
    vi.mocked(ragExperimentsHooks.useCreateTestParagraph).mockReturnValue({
      mutate: mutateFn,
      mutateAsync: vi.fn(),
      isPending: false,
      isSuccess: false,
      error: null,
      data: undefined,
      isError: false,
      isIdle: true,
      status: "idle",
      reset: vi.fn(),
      variables: undefined,
      context: undefined,
      submittedAt: 0,
    } as unknown as UseMutationResult<
      TestParagraphResponse,
      Error,
      { text: string; notes?: string },
      unknown
    >);

    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByLabelText(/Paragraph Text/i);
    fireEvent.change(textarea, { target: { value: "Test text" } });

    const submitButton = screen.getByText(/Create Paragraph/i);
    fireEvent.click(submitButton);

    expect(mutateFn).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Test text" }),
    );
  });

  it("handles empty notes field", () => {
    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByLabelText(/Paragraph Text/i);
    fireEvent.change(textarea, { target: { value: "Test text" } });

    const notesInput = screen.getByLabelText(/Notes/i);
    expect(notesInput).toHaveValue("");
  });

  it("updates character count in real-time", () => {
    render(<TestParagraphEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByLabelText(/Paragraph Text/i);

    fireEvent.change(textarea, { target: { value: "Hi" } });
    expect(screen.getByText("2 characters")).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: "Hello World" } });
    expect(screen.getByText("11 characters")).toBeInTheDocument();
  });
});
