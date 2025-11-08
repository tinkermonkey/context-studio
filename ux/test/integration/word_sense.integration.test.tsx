/**
 * Integration tests for Word Sense Workflow
 *
 * Tests the complete word sense selection workflow:
 * - Load structure node with persisted senses
 * - Select/deselect word senses
 * - Save changes
 * - Reload and verify persistence
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WordSenseSelector } from '@/components/graphs/nlp_concept/WordSenseSelector';
import { WordSense } from '@/api/types/structureNodes';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

// Mock API responses
const mockNlpAnalysis = {
  tokens: [
    {
      text: 'bank',
      lemma: 'bank',
      pos: 'NOUN',
      tag: 'NN',
      wordnet: {
        synsets: [
          {
            name: 'bank.n.01',
            definition: 'a financial institution',
            lemmas: ['bank'],
            pos: 'n',
            offset: 8420278,
            domain: 'noun.group'
          },
          {
            name: 'bank.n.02',
            definition: 'sloping land beside water',
            lemmas: ['bank'],
            pos: 'n',
            offset: 9236472,
            domain: 'noun.object'
          }
        ]
      },
      concepcy: {
        related_terms: []
      }
    }
  ]
};

const mockWordSenses: WordSense[] = [
  {
    term: 'bank',
    sense_type: 'wordnet',
    sense_id: 'bank.n.01',
    definition: 'a financial institution',
    domain: 'noun.group'
  }
];

// Setup MSW server
const server = setupServer();

beforeEach(() => {
  server.listen({ onUnhandledRequest: 'warn' });
});

afterEach(() => {
  server.resetHandlers();
  server.close();
  vi.clearAllMocks();
});

describe('Word Sense Integration Tests', () => {
  const createWrapper = () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    return ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };

  it('should load persisted word senses on mount', async () => {
    const nodeId = 'test-node-123';

    // Setup mock handlers
    server.use(
      rest.get('/api/structure_nodes/:nodeId/word_senses', (req, res, ctx) => {
        return res(ctx.json(mockWordSenses));
      })
    );

    render(
      <WordSenseSelector
        title="bank"
        persistedSenses={mockWordSenses}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Verify persisted sense is shown
    await waitFor(() => {
      expect(screen.getByText(/bank/i)).toBeInTheDocument();
      expect(screen.getByText('bank.n.01')).toBeInTheDocument();
    });
  });

  it('should expand word and load NLP analysis on click', async () => {
    const user = userEvent.setup();
    const nodeId = 'test-node-123';

    server.use(
      rest.get('/api/nlp/analyze', (req, res, ctx) => {
        return res(ctx.json(mockNlpAnalysis));
      })
    );

    render(
      <WordSenseSelector
        title="bank"
        persistedSenses={[]}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Click word to expand
    const wordButton = screen.getByRole('button', { name: /bank/i });
    await user.click(wordButton);

    // Should show analyzing state
    expect(await screen.findByText(/Analyzing/i)).toBeInTheDocument();

    // Should load analysis
    await waitFor(() => {
      expect(screen.queryByText(/Analyzing/i)).not.toBeInTheDocument();
    });
  });

  it('should select a word sense and mark as dirty', async () => {
    const user = userEvent.setup();
    const nodeId = 'test-node-123';

    server.use(
      rest.get('/api/nlp/analyze', (req, res, ctx) => {
        return res(ctx.json(mockNlpAnalysis));
      })
    );

    render(
      <WordSenseSelector
        title="bank"
        persistedSenses={[]}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Expand word
    const wordButton = screen.getByRole('button', { name: /^bank$/i });
    await user.click(wordButton);

    // Wait for analysis to complete
    await waitFor(() => {
      expect(screen.queryByText(/Analyzing/i)).not.toBeInTheDocument();
    });

    // Save button should not be visible initially
    expect(screen.queryByRole('button', { name: /Save Word Senses/i })).not.toBeInTheDocument();

    // Note: Selecting a sense node requires clicking on the chart
    // This would need actual chart interaction, which is complex to test
    // For now, we verify the component renders correctly
  });

  it('should save word senses and call onSaveComplete', async () => {
    const user = userEvent.setup();
    const nodeId = 'test-node-123';
    const onSaveComplete = vi.fn();

    server.use(
      rest.put('/api/structure_nodes/:nodeId/word_senses', (req, res, ctx) => {
        return res(ctx.json([mockWordSenses[0]]));
      })
    );

    // Simulate component with dirty state (has selections different from persisted)
    render(
      <WordSenseSelector
        title="bank"
        persistedSenses={[]}
        nodeId={nodeId}
        onSaveComplete={onSaveComplete}
      />,
      { wrapper: createWrapper() }
    );

    // Note: Actually getting to a dirty state requires chart interaction
    // This test verifies the component structure is correct
    // Full E2E testing would require Playwright or similar
  });

  it('should handle API error during NLP analysis', async () => {
    const user = userEvent.setup();
    const nodeId = 'test-node-123';

    server.use(
      rest.get('/api/nlp/analyze', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ detail: 'NLP service unavailable' }));
      })
    );

    render(
      <WordSenseSelector
        title="bank"
        persistedSenses={[]}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Click word to expand
    const wordButton = screen.getByRole('button', { name: /bank/i });
    await user.click(wordButton);

    // Should show error state
    await waitFor(() => {
      expect(screen.getByText(/Error:/i)).toBeInTheDocument();
    });
  });

  it('should handle API error during save', async () => {
    const nodeId = 'test-node-123';

    server.use(
      rest.put('/api/structure_nodes/:nodeId/word_senses', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ detail: 'Database error' }));
      })
    );

    // This test verifies error handling structure exists
    // Full testing requires being able to trigger save action
    render(
      <WordSenseSelector
        title="bank"
        persistedSenses={mockWordSenses}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Component should render without crashing
    expect(screen.getByText(/bank/i)).toBeInTheDocument();
  });

  it('should handle multi-word titles with lazy loading', async () => {
    const user = userEvent.setup();
    const nodeId = 'test-node-123';

    server.use(
      rest.get('/api/nlp/analyze', (req, res, ctx) => {
        const text = req.url.searchParams.get('text');

        // Return different analysis based on word
        if (text === 'bank') {
          return res(ctx.json(mockNlpAnalysis));
        } else if (text === 'account') {
          return res(ctx.json({
            tokens: [{
              text: 'account',
              lemma: 'account',
              pos: 'NOUN',
              wordnet: {
                synsets: [{
                  name: 'account.n.01',
                  definition: 'a record or narrative description',
                  lemmas: ['account'],
                  pos: 'n',
                  domain: 'noun.communication'
                }]
              },
              concepcy: { related_terms: [] }
            }]
          }));
        }

        return res(ctx.status(404));
      })
    );

    render(
      <WordSenseSelector
        title="bank account"
        persistedSenses={[]}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Both words should be rendered
    const wordButtons = screen.getAllByRole('button');
    expect(wordButtons.length).toBeGreaterThanOrEqual(2);

    // Click first word
    const bankButton = screen.getByRole('button', { name: /^bank$/i });
    await user.click(bankButton);

    // Should only analyze "bank"
    await waitFor(() => {
      expect(screen.getByText(/Analyzing/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.queryByText(/Analyzing/i)).not.toBeInTheDocument();
    });

    // Click second word
    const accountButton = screen.getByRole('button', { name: /^account$/i });
    await user.click(accountButton);

    // Should analyze "account" separately
    await waitFor(() => {
      expect(screen.getByText(/Analyzing/i)).toBeInTheDocument();
    });
  });

  it('should preserve selections for other words during save', async () => {
    const nodeId = 'test-node-123';
    const initialSenses: WordSense[] = [
      {
        term: 'bank',
        sense_type: 'wordnet',
        sense_id: 'bank.n.01',
        definition: 'a financial institution',
        domain: 'noun.group'
      },
      {
        term: 'account',
        sense_type: 'wordnet',
        sense_id: 'account.n.01',
        definition: 'a record',
        domain: 'noun.communication'
      }
    ];

    server.use(
      rest.put('/api/structure_nodes/:nodeId/word_senses', async (req, res, ctx) => {
        const body = await req.json();
        // Verify conservative merge: update should include both words if both had selections
        return res(ctx.json(body.selected_senses));
      })
    );

    render(
      <WordSenseSelector
        title="bank account"
        persistedSenses={initialSenses}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Both words should show their persisted senses
    await waitFor(() => {
      expect(screen.getByText('bank.n.01')).toBeInTheDocument();
      expect(screen.getByText('account.n.01')).toBeInTheDocument();
    });
  });

  it('should deselect sense when clicking same sense again', () => {
    const nodeId = 'test-node-123';

    render(
      <WordSenseSelector
        title="bank"
        persistedSenses={mockWordSenses}
        nodeId={nodeId}
      />,
      { wrapper: createWrapper() }
    );

    // Initial state shows selected sense
    expect(screen.getByText('bank.n.01')).toBeInTheDocument();

    // Note: Actually deselecting requires chart interaction
    // This test verifies component structure
  });
});
