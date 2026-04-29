import React from "react";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { mockAnalysis } from "../../utils/mockNlpData";

// Mock the useNLPAnalysis hook to return our mockAnalysis
vi.mock("@/api/hooks/nlp/useNLPAnalysis", () => ({
  useNLPAnalysis: (text: string, options: any) => ({
    data: options?.enabled === false ? null : text ? mockAnalysis : null,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

// Mock the API hooks used by LlmPipelineRun
vi.mock("@/api/hooks/pipelines/usePipelineFlavors", () => ({
  usePipelineFlavors: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
}));

vi.mock("@/api/hooks/llm/useLlmMutations", () => ({
  useLlmMutation: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/api/hooks/terms/useTermMutations", () => ({
  useUpdateTerm: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";

const renderWithQueryClient = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
  );
};

describe("NlpAnalysisPanel", () => {
  it("shows message prompting to analyze when no analysis is available", () => {
    renderWithQueryClient(
      <NlpAnalysisPanel text="database" textTitle="Term" />,
    );

    // Should show message since no analysis has been triggered yet (enabled: false in hook)
    expect(
      screen.getByText(/Click "Analyze Term" to view token analysis/i),
    ).toBeInTheDocument();
  });
});
