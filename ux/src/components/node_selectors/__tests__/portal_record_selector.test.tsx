import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { renderWithProviders as render } from '@/test/utils/renderWithProviders';
import PortalRecordSelector from '@/components/node_selectors/portal_record_selector';

type Rec = { id: string; name: string; definition?: string };

const records: Rec[] = [
  { id: '1', name: 'Alpha', definition: 'First' },
  { id: '2', name: 'Beta', definition: 'Second' },
  { id: '3', name: 'Gamma', definition: 'Third' },
];

describe('PortalRecordSelector', () => {
  it('renders placeholder and opens portal showing items', () => {
    render(
      <PortalRecordSelector
        records={records}
        fieldMap={{ value: 'id', title: 'name', definition: 'definition' }}
        placeholder="Choose..."
      />,
    );

    // placeholder present
    expect(screen.getByText('Choose...')).toBeTruthy();

    // open menu
    fireEvent.click(screen.getByRole('button'));

    // items should appear in the document (portal)
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.getByText('Gamma')).toBeTruthy();
  });

  it('filters items using search input', () => {
    render(
      <PortalRecordSelector
        records={records}
        fieldMap={{ value: 'id', title: 'name', definition: 'definition' }}
      />,
    );

    fireEvent.click(screen.getByRole('button'));

    const input = screen.getByPlaceholderText('Search...') as HTMLInputElement;
    expect(input).toBeTruthy();

    // search for 'Beta'
    fireEvent.change(input, { target: { value: 'Beta' } });
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.queryByText('Alpha')).toBeNull();
  });

  it('calls onSelect when an item is clicked (single select)', () => {
    const onSelect = vi.fn();
    render(
      <PortalRecordSelector
        records={records}
        fieldMap={{ value: 'id', title: 'name', definition: 'definition' }}
        onSelect={onSelect}
      />,
    );

    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByText('Beta'));

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: '2' }));
  });

  it('supports multi-select and onSelectionChange', () => {
    const onSelectionChange = vi.fn();
    render(
      <PortalRecordSelector
        records={records}
        fieldMap={{ value: 'id', title: 'name', definition: 'definition' }}
        multi
        value={[]}
        onSelectionChange={onSelectionChange}
      />,
    );

    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByText('Alpha'));

    expect(onSelectionChange).toHaveBeenCalled();
    // first call should include the selected id
    expect(onSelectionChange.mock.calls[0][0]).toContain('1');
  });

  it('supports keyboard navigation and exposes ARIA attributes', async () => {
    const onSelect = vi.fn();
    render(
      <PortalRecordSelector
        records={records}
        fieldMap={{ value: 'id', title: 'name', definition: 'definition' }}
        onSelect={onSelect}
      />,
    );

  const trigger = screen.getByRole('button');
  // open menu
  trigger.focus();
  await userEvent.click(trigger);

  // The listbox should be present and have aria-expanded on the trigger
  await waitFor(() => expect(trigger).toHaveAttribute('aria-expanded', 'true'));
  const listbox = screen.getByRole('listbox');
  expect(listbox).toBeTruthy();

  // Move highlight down to Gamma using keyboard
  await userEvent.keyboard('{ArrowDown}{ArrowDown}{ArrowDown}');

  // Press Enter to select the highlighted item
  await userEvent.keyboard('{Enter}');

    expect(onSelect).toHaveBeenCalledTimes(1);
    // ensure selected item was Gamma
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: '3' }));

  // Re-open and press Escape to close
  await userEvent.click(trigger);
  await waitFor(() => expect(trigger).toHaveAttribute('aria-expanded', 'true'));
  await userEvent.keyboard('{Escape}');
  await waitFor(() => expect(trigger).toHaveAttribute('aria-expanded', 'false'));
  });
});
