/**
 * EditableTable Component
 *
 * A reusable table component for viewing and editing nodes (layers, domains, terms)
 * with in-place editing capabilities, pagination, and search functionality.
 */

import React, { useState, useEffect } from 'react';
import { VStack } from '@/components/ui/vstack';
import { HStack } from '@/components/ui/hstack';
import { Box } from '@/components/ui/box';
import { Text } from '@/components/ui/text';
import { Input, InputField } from '@/components/ui/input';
import { Button, ButtonText } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { Table, TableBody, TableData, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pressable } from 'react-native';
import { useDebounce } from '@/hooks/useDebounce';
import { handleApiError } from '@/api/errors/errorHandlers';
import type { components } from '@/api/client/types';

// Type definitions
type LayerOut = components['schemas']['LayerOut'];
type DomainOut = components['schemas']['DomainOut'];
type TermOut = components['schemas']['TermOut'];
type LayerUpdate = components['schemas']['LayerUpdate'];
type DomainUpdate = components['schemas']['DomainUpdate'];
type TermUpdate = components['schemas']['TermUpdate'];

export type NodeType = 'layer' | 'domain' | 'term';
export type NodeData = LayerOut | DomainOut | TermOut;
export type UpdateData = LayerUpdate | DomainUpdate | TermUpdate;

interface EditingCell {
  id: string;
  field: 'title' | 'definition';
  value: string;
}

interface EditableTableProps {
  nodeType: NodeType;
  data: NodeData[];
  isLoading: boolean;
  error: Error | null;
  onUpdate: (id: string, updateData: UpdateData) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  onRefresh: () => void;
  onSearch?: (query: string, searchField: 'title' | 'definition') => void;
  pagination?: {
    skip: number;
    limit: number;
    total?: number;
    onPageChange: (skip: number, limit: number) => void;
  };
  showActions?: boolean;
  enableInlineEdit?: boolean;
  enableSearch?: boolean;
  enablePagination?: boolean;
}

export const EditableTable: React.FC<EditableTableProps> = ({
  nodeType,
  data,
  isLoading,
  error,
  onUpdate,
  onDelete,
  onRefresh,
  onSearch,
  pagination,
  showActions = true,
  enableInlineEdit = true,
  enableSearch = true,
  enablePagination = true,
}) => {
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchField, setSearchField] = useState<'title' | 'definition'>('title');
  const [updating, setUpdating] = useState<string | null>(null);
  
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  // Handle search when debounced query changes
  useEffect(() => {
    if (onSearch && debouncedSearchQuery) {
      onSearch(debouncedSearchQuery, searchField);
    }
  }, [debouncedSearchQuery, searchField, onSearch]);

  // Helper function to get the relationship column name and value
  const getRelationshipInfo = (item: NodeData) => {
    if (nodeType === 'domain' && 'layer_id' in item) {
      return { label: 'Layer ID', value: item.layer_id };
    }
    if (nodeType === 'term' && 'domain_id' in item) {
      return { label: 'Domain ID', value: item.domain_id };
    }
    return null;
  };

  // Handle cell editing
  const handleCellEdit = (id: string, field: 'title' | 'definition', currentValue: string) => {
    if (!enableInlineEdit) return;
    setEditingCell({ id, field, value: currentValue });
  };

  const handleCellSave = async () => {
    if (!editingCell) return;

    setUpdating(editingCell.id);
    try {
      const updateData = {
        [editingCell.field]: editingCell.value,
      } as UpdateData;

      await onUpdate(editingCell.id, updateData);
      setEditingCell(null);
    } catch (error) {
      handleApiError(error);
    } finally {
      setUpdating(null);
    }
  };

  const handleCellCancel = () => {
    setEditingCell(null);
  };

  // Handle delete
  const handleDelete = async (id: string) => {
    if (!onDelete) return;

    setUpdating(id);
    try {
      await onDelete(id);
    } catch (error) {
      handleApiError(error);
    } finally {
      setUpdating(null);
    }
  };

  // Format date for display
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  // Render editable cell
  const renderEditableCell = (item: NodeData, field: 'title' | 'definition') => {
    const value = item[field] || '';
    const isEditing = editingCell?.id === item.id && editingCell.field === field;

    if (isEditing) {
      return (
        <HStack space="sm" className="items-center">
          <Input className="flex-1" size="sm">
            <InputField
              value={editingCell.value}
              onChangeText={(text) => setEditingCell({ ...editingCell, value: text })}
              autoFocus
              onSubmitEditing={handleCellSave}
              onBlur={handleCellCancel}
            />
          </Input>
          <Button size="sm" onPress={handleCellSave}>
            <ButtonText>Save</ButtonText>
          </Button>
          <Button size="sm" variant="outline" onPress={handleCellCancel}>
            <ButtonText>Cancel</ButtonText>
          </Button>
        </HStack>
      );
    }

    return (
      <Pressable onPress={() => handleCellEdit(item.id, field, value)}>
        <Text className={enableInlineEdit ? 'hover:bg-gray-100 p-1 rounded' : ''}>
          {value || '-'}
        </Text>
      </Pressable>
    );
  };

  // Pagination controls
  const renderPagination = () => {
    if (!enablePagination || !pagination) return null;

    const { skip, limit, total, onPageChange } = pagination;
    const currentPage = Math.floor(skip / limit) + 1;
    const totalPages = total ? Math.ceil(total / limit) : 1;

    return (
      <HStack className="justify-between items-center mt-4">
        <Text className="text-sm text-gray-600">
          Showing {skip + 1} to {Math.min(skip + limit, total || skip + data.length)} 
          {total && ` of ${total}`} results
        </Text>
        <HStack space="sm">
          <Button
            size="sm"
            variant="outline"
            onPress={() => onPageChange(Math.max(0, skip - limit), limit)}
            disabled={skip === 0}
          >
            <ButtonText>Previous</ButtonText>
          </Button>
          <Text className="text-sm px-3 py-1">
            Page {currentPage} {total && `of ${totalPages}`}
          </Text>
          <Button
            size="sm"
            variant="outline"
            onPress={() => onPageChange(skip + limit, limit)}
            disabled={total ? skip + limit >= total : data.length < limit}
          >
            <ButtonText>Next</ButtonText>
          </Button>
        </HStack>
      </HStack>
    );
  };

  // Loading state
  if (isLoading) {
    return (
      <VStack className="flex-1 justify-center items-center">
        <Spinner size="large" />
        <Text className="mt-4">Loading {nodeType}s...</Text>
      </VStack>
    );
  }

  // Error state
  if (error) {
    return (
      <VStack className="flex-1 justify-center items-center">
        <Text className="text-red-500 mb-4">Error loading {nodeType}s</Text>
        <Button onPress={onRefresh}>
          <ButtonText>Retry</ButtonText>
        </Button>
      </VStack>
    );
  }

  return (
    <VStack className="flex-1">
      {/* Search Controls */}
      {enableSearch && onSearch && (
        <HStack className="p-4 border-b border-gray-200" space="md">
          <Input className="flex-1">
            <InputField
              placeholder={`Search ${nodeType}s...`}
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
          </Input>
          <Button
            variant="outline"
            size="sm"
            onPress={() => setSearchField(searchField === 'title' ? 'definition' : 'title')}
          >
            <ButtonText>
              Search by: {searchField === 'title' ? 'Title' : 'Definition'}
            </ButtonText>
          </Button>
        </HStack>
      )}

      {/* Table */}
      <Box className="flex-1">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Text className="font-semibold">ID</Text>
              </TableHead>
              <TableHead>
                <Text className="font-semibold">Title</Text>
              </TableHead>
              <TableHead>
                <Text className="font-semibold">Definition</Text>
              </TableHead>
              {nodeType !== 'layer' && (
                <TableHead>
                  <Text className="font-semibold">
                    {nodeType === 'domain' ? 'Layer ID' : 'Domain ID'}
                  </Text>
                </TableHead>
              )}
              <TableHead>
                <Text className="font-semibold">Created</Text>
              </TableHead>
              <TableHead>
                <Text className="font-semibold">Last Modified</Text>
              </TableHead>
              {showActions && (
                <TableHead>
                  <Text className="font-semibold">Actions</Text>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((item) => {
              const relationshipInfo = getRelationshipInfo(item);
              const isUpdating = updating === item.id;

              return (
                <TableRow key={item.id}>
                  <TableData>
                    <Text className="text-xs font-mono">{item.id}</Text>
                  </TableData>
                  <TableData>
                    {renderEditableCell(item, 'title')}
                  </TableData>
                  <TableData>
                    {renderEditableCell(item, 'definition')}
                  </TableData>
                  {relationshipInfo && (
                    <TableData>
                      <Text className="text-xs font-mono">{relationshipInfo.value}</Text>
                    </TableData>
                  )}
                  <TableData>
                    <Text className="text-xs">
                      {formatDate(item.created_at)}
                    </Text>
                  </TableData>
                  <TableData>
                    <Text className="text-xs">
                      {'last_modified' in item && item.last_modified ? formatDate(item.last_modified) : '-'}
                    </Text>
                  </TableData>
                  {showActions && (
                    <TableData>
                      <HStack space="sm">
                        {isUpdating && <Spinner size="small" />}
                        {onDelete && (
                          <Button
                            size="sm"
                            variant="outline"
                            onPress={() => handleDelete(item.id)}
                            disabled={isUpdating}
                          >
                            <ButtonText>Delete</ButtonText>
                          </Button>
                        )}
                      </HStack>
                    </TableData>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>

        {/* Empty state */}
        {data.length === 0 && (
          <VStack className="flex-1 justify-center items-center py-8">
            <Text className="text-gray-500">No {nodeType}s found</Text>
          </VStack>
        )}
      </Box>

      {/* Pagination */}
      {renderPagination()}
    </VStack>
  );
};
