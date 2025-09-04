import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PipelineFlavorEditor } from '@/components/llm_pipelines/flavors/PipelineFlavorEditor';

// Mock the pipeline flavors hooks
const mockExistingFlavor = {
  id: 'existing-flavor-1',
  pipeline: 'suggest_term_definition' as const,
  title: 'Default Term Flavor',
  llm_provider: 'openai',
  llm_model: 'gpt-4o',
  system_prompt: 'You are an expert at creating precise, informative definitions for technical terms.',
  user_prompt: 'Create a definition for the term "{title}" in the context of {domain_context}.',
  llm_config: {
    temperature: 0.5,
    max_tokens: 500,
    top_p: 0.9,
    frequency_penalty: 0.1,
    presence_penalty: 0.2
  },
  enabled: true,
  version: 1,
  last_updated: '2025-09-02T10:00:00Z',
  date_created: '2025-09-01T10:00:00Z'
};

vi.mock('@/api/hooks/pipelineFlavors', () => ({
  usePipelineFlavors: vi.fn(() => ({
    data: {
      flavors: [mockExistingFlavor],
      total_count: 1
    },
    isLoading: false,
    error: null
  })),
  useCreatePipelineFlavor: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false
  })),
  useUpdatePipelineFlavor: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false
  }))
}));

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
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
};

describe('PipelineFlavorEditor - Default Population', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('populates default values from existing flavor when creating new', async () => {
    const mockOnClose = vi.fn();
    
    renderWithQueryClient(
      <PipelineFlavorEditor
        pipeline="suggest_term_definition"
        flavor={null} // Creating new flavor
        onClose={mockOnClose}
      />
    );

    // Should show the "Defaults populated" alert
    await waitFor(() => {
      expect(screen.getByText(/Defaults populated/)).toBeInTheDocument();
    });

    // Check that the form is populated with the default values
    await waitFor(() => {
      const systemPromptTextarea = screen.getByDisplayValue(/You are an expert at creating precise/);
      expect(systemPromptTextarea).toBeInTheDocument();
      
      const userPromptTextarea = screen.getByDisplayValue(/Create a definition for the term/);
      expect(userPromptTextarea).toBeInTheDocument();
    });
  });

  it('does not fetch defaults when editing existing flavor', () => {
    const mockOnClose = vi.fn();
    
    renderWithQueryClient(
      <PipelineFlavorEditor
        pipeline="suggest_term_definition"
        flavor={mockExistingFlavor} // Editing existing flavor
        onClose={mockOnClose}
      />
    );

    // Should not show the "Defaults populated" alert
    expect(screen.queryByText(/Defaults populated/)).not.toBeInTheDocument();
  });

  it('shows loading state when fetching defaults', () => {
    const mockUsePipelineFlavors = vi.fn(() => ({
      data: null,
      isLoading: true,
      error: null
    }));
    
    vi.mocked(require('@/api/hooks/pipelineFlavors').usePipelineFlavors).mockImplementation(mockUsePipelineFlavors);

    const mockOnClose = vi.fn();
    
    renderWithQueryClient(
      <PipelineFlavorEditor
        pipeline="suggest_term_definition"
        flavor={null} // Creating new flavor
        onClose={mockOnClose}
      />
    );

    // Should show loading message
    expect(screen.getByText(/Loading default values/)).toBeInTheDocument();
  });

  it('handles case when no existing flavors exist', async () => {
    const mockUsePipelineFlavors = vi.fn(() => ({
      data: {
        flavors: [],
        total_count: 0
      },
      isLoading: false,
      error: null
    }));
    
    vi.mocked(require('@/api/hooks/pipelineFlavors').usePipelineFlavors).mockImplementation(mockUsePipelineFlavors);

    const mockOnClose = vi.fn();
    
    renderWithQueryClient(
      <PipelineFlavorEditor
        pipeline="suggest_term_definition"
        flavor={null} // Creating new flavor
        onClose={mockOnClose}
      />
    );

    // Should not show defaults populated alert
    expect(screen.queryByText(/Defaults populated/)).not.toBeInTheDocument();
    
    // Should show empty form
    const systemPromptTextarea = screen.getByPlaceholderText(/Define the role and context/) as HTMLTextAreaElement;
    expect(systemPromptTextarea.value).toBe('');
  });
});
