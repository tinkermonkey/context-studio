import React from 'react';
import { render, screen } from '@testing-library/react';
import TokenSelectionList from '@/components/nlp/TokenSelectionList';
import { mockAnalysis } from '../../utils/mockNlpData';

describe('TokenSelectionList', () => {
  it('renders non-stop tokens and hides stop words', () => {
    render(<TokenSelectionList tokens={mockAnalysis.tokens} selectedToken={null} onTokenSelect={() => {}} />);

    // 'database' should be present
    expect(screen.getByText('database')).toBeInTheDocument();

    // 'the' is a stop word in mock and should not be displayed
    expect(screen.queryByText('the')).toBeNull();
  });
});
