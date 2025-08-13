import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CreateChildButton } from '../create_child_button';

// Mock the form components
jest.mock('@/components/forms/domain_form', () => ({
  DomainForm: ({ onSuccess }: { onSuccess: (domain: any) => void }) => (
    <div data-testid="domain-form">
      <button onClick={() => onSuccess({ id: '1', title: 'Test Domain' })}>
        Submit Domain
      </button>
    </div>
  ),
}));

jest.mock('@/components/forms/term_form', () => ({
  TermForm: ({ onSuccess }: { onSuccess: (term: any) => void }) => (
    <div data-testid="term-form">
      <button onClick={() => onSuccess({ id: '1', title: 'Test Term' })}>
        Submit Term
      </button>
    </div>
  ),
}));

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

describe('CreateChildButton', () => {
  const mockLayer = {
    id: 'layer-1',
    title: 'Test Layer',
    definition: 'Test definition',
    created_at: '2023-01-01T00:00:00Z',
  };

  const mockDomain = {
    id: 'domain-1',
    title: 'Test Domain',
    definition: 'Test definition',
    layer_id: 'layer-1',
    created_at: '2023-01-01T00:00:00Z',
  };

  it('renders create domain button for layer parent', () => {
    const queryClient = createTestQueryClient();
    
    render(
      <QueryClientProvider client={queryClient}>
        <CreateChildButton
          parentType="layer"
          parentId="layer-1"
          parentObject={mockLayer}
          childType="domain"
        />
      </QueryClientProvider>
    );

    expect(screen.getByRole('button', { name: /add/i })).toBeInTheDocument();
  });

  it('opens modal when button is clicked', () => {
    const queryClient = createTestQueryClient();
    
    render(
      <QueryClientProvider client={queryClient}>
        <CreateChildButton
          parentType="layer"
          parentId="layer-1"
          parentObject={mockLayer}
          childType="domain"
        />
      </QueryClientProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /add/i }));
    
    expect(screen.getByText(/Create Domain in Layer: Test Layer/i)).toBeInTheDocument();
    expect(screen.getByTestId('domain-form')).toBeInTheDocument();
  });

  it('renders create term button for domain parent', () => {
    const queryClient = createTestQueryClient();
    
    render(
      <QueryClientProvider client={queryClient}>
        <CreateChildButton
          parentType="domain"
          parentId="domain-1"
          parentObject={mockDomain}
          childType="term"
        />
      </QueryClientProvider>
    );

    expect(screen.getByRole('button', { name: /add/i })).toBeInTheDocument();
  });

  it('calls onSuccess when form is submitted', () => {
    const queryClient = createTestQueryClient();
    const onSuccess = jest.fn();
    
    render(
      <QueryClientProvider client={queryClient}>
        <CreateChildButton
          parentType="layer"
          parentId="layer-1"
          parentObject={mockLayer}
          childType="domain"
          onSuccess={onSuccess}
        />
      </QueryClientProvider>
    );

    // Open modal
    fireEvent.click(screen.getByRole('button', { name: /add/i }));
    
    // Submit form
    fireEvent.click(screen.getByText('Submit Domain'));
    
    expect(onSuccess).toHaveBeenCalledWith({ id: '1', title: 'Test Domain' });
  });
});
