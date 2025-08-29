import React from 'react';
import { render, screen } from '@testing-library/react';
import TokenSenseList from '@/components/nlp/TokenSenseList';
import { mockTokenData } from '../../utils/mockNlpData';

describe('TokenSenseList', () => {
  it('renders word senses and definition', () => {
    render(<TokenSenseList senses={mockTokenData.wordnet.synsets} onSenseSelect={() => {}} />);

    expect(screen.getByText('database.n.01')).toBeInTheDocument();
    expect(screen.getByText(/an organized body of related information/)).toBeInTheDocument();
  });
});
