/**
 * EditableTable Tests
 *
 * Basic tests for the EditableTable component
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { EditableTable } from '../../components/common/EditableTable';

// Mock data
const mockLayerData = [
  {
    id: '1',
    title: 'Test Layer',
    definition: 'Test definition',
    created_at: '2023-01-01T00:00:00Z',
    last_modified: '2023-01-01T00:00:00Z',
  },
];

// Mock functions
const mockOnUpdate = jest.fn();
const mockOnDelete = jest.fn();
const mockOnRefresh = jest.fn();

describe('EditableTable', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders table with data', () => {
    render(
      <EditableTable
        nodeType="layer"
        data={mockLayerData}
        isLoading={false}
        error={null}
        onUpdate={mockOnUpdate}
        onDelete={mockOnDelete}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Test Layer')).toBeTruthy();
    expect(screen.getByText('Test definition')).toBeTruthy();
  });

  it('shows loading state', () => {
    render(
      <EditableTable
        nodeType="layer"
        data={[]}
        isLoading={true}
        error={null}
        onUpdate={mockOnUpdate}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Loading layers...')).toBeTruthy();
  });

  it('shows error state', () => {
    const mockError = new Error('Test error');
    
    render(
      <EditableTable
        nodeType="layer"
        data={[]}
        isLoading={false}
        error={mockError}
        onUpdate={mockOnUpdate}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Error loading layers')).toBeTruthy();
    expect(screen.getByText('Retry')).toBeTruthy();
  });

  it('shows empty state when no data', () => {
    render(
      <EditableTable
        nodeType="layer"
        data={[]}
        isLoading={false}
        error={null}
        onUpdate={mockOnUpdate}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('No layers found')).toBeTruthy();
  });

  it('handles refresh button click', () => {
    const mockError = new Error('Test error');
    
    render(
      <EditableTable
        nodeType="layer"
        data={[]}
        isLoading={false}
        error={mockError}
        onUpdate={mockOnUpdate}
        onRefresh={mockOnRefresh}
      />
    );

    fireEvent.press(screen.getByText('Retry'));
    expect(mockOnRefresh).toHaveBeenCalledTimes(1);
  });
});
