import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { mockAnalysis } from '../../utils/mockNlpData';

// Mock the useNLPAnalysis hook to return our mockAnalysis
vi.mock('@/api/hooks/nlp/useNLPAnalysis', () => ({
  useNLPAnalysis: (text: string) => ({
    data: text ? mockAnalysis : null,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

import { NlpAnalysisPanel } from '@/components/nlp/NlpAnalysisPanel';

describe('NlpAnalysisPanel', () => {
  it('shows tokens and entities when analysis is available', async () => {
    render(<NlpAnalysisPanel text="database" />);

    // Click analyze to trigger (hook returns mock data immediately)
    fireEvent.click(screen.getByText(/Analyze/i));

    expect(await screen.findByText('database')).toBeInTheDocument();
    expect(screen.getByText(/Context Studio/)).toBeInTheDocument();
  });
});
