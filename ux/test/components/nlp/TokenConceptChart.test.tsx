import React from 'react';
import { render, screen } from '@testing-library/react';
import TokenConceptChart from '@/components/nlp/TokenConceptChart';
import { mockTokenData } from '../../utils/mockNlpData';

describe('TokenConceptChart', () => {
  it('renders concept map with central term', () => {
    render(<TokenConceptChart concepcyData={mockTokenData.concepcy} centralTerm={mockTokenData.text} />);

    expect(screen.getByLabelText(/Concept map for/i)).toBeInTheDocument();
    expect(screen.getByText(/database/)).toBeInTheDocument();
  });
});
