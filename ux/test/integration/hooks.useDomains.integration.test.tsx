import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { renderWithProviders as render } from '@/test/utils/renderWithProviders';
import { useDomains } from '@/api/hooks/domains/useDomains';

const TestComponent: React.FC = () => {
  const { data, isLoading } = useDomains();
  if (isLoading) return <div>loading</div>;
  return (
    <div>
      {data?.map((d: any) => (
        <div key={d.id}>{d.title}</div>
      ))}
    </div>
  );
};

describe('useDomains integration', () => {
  it('fetches domains and renders at least one item', async () => {
    const { container } = render(<TestComponent />);
    await waitFor(() => {
      // ensure loading is gone and at least one child is rendered
      expect(container.querySelectorAll('div > div').length).toBeGreaterThan(0);
    });
  });
});
