/**
 * LayerTable Component
 *
 * A specialized table component for viewing and editing layers
 */

import React, { useState } from 'react';
import { EditableTable } from '../common/EditableTable';
import { useLayers, useLayerSearch, useUpdateLayer, useDeleteLayer } from '../../api/hooks/layers';
import { handleApiError } from '../../api/errors/errorHandlers';
import type { components } from '../../api/client/types';

type LayerUpdate = components['schemas']['LayerUpdate'];

interface LayerTableProps {
  showActions?: boolean;
  enableInlineEdit?: boolean;
  enableSearch?: boolean;
  enablePagination?: boolean;
  pageSize?: number;
}

export const LayerTable: React.FC<LayerTableProps> = ({
  showActions = true,
  enableInlineEdit = true,
  enableSearch = true,
  enablePagination = true,
  pageSize = 20,
}) => {
  const [pagination, setPagination] = useState({ skip: 0, limit: pageSize });
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearching, setIsSearching] = useState(false);

  // Use search if there's a query, otherwise use regular list
  const listQuery = useLayers(
    enablePagination ? pagination : undefined
  );

  const searchQuery_ = useLayerSearch(
    { 
      query: searchQuery, 
      limit: enablePagination ? pagination.limit : undefined 
    }
  );

  const updateLayer = useUpdateLayer();
  const deleteLayer = useDeleteLayer();

  // Use search results if searching, otherwise use list results
  const data = isSearching ? (searchQuery_.data || []) : (listQuery.data || []);
  const isLoading = isSearching ? searchQuery_.isLoading : listQuery.isLoading;
  const error = isSearching ? searchQuery_.error : listQuery.error;

  const handleUpdate = async (id: string, updateData: LayerUpdate) => {
    try {
      await updateLayer.mutateAsync({ id, data: updateData });
    } catch (error) {
      handleApiError(error);
      throw error;
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteLayer.mutateAsync(id);
    } catch (error) {
      handleApiError(error);
      throw error;
    }
  };

  const handleSearch = (query: string, field: 'title' | 'definition') => {
    setSearchQuery(query);
    setIsSearching(!!query);
  };

  const handleRefresh = () => {
    if (isSearching) {
      searchQuery_.refetch();
    } else {
      listQuery.refetch();
    }
  };

  const handlePageChange = (skip: number, limit: number) => {
    setPagination({ skip, limit });
  };

  return (
    <EditableTable
      nodeType="layer"
      data={data}
      isLoading={isLoading}
      error={error}
      onUpdate={handleUpdate}
      onDelete={showActions ? handleDelete : undefined}
      onRefresh={handleRefresh}
      onSearch={enableSearch ? handleSearch : undefined}
      pagination={enablePagination ? {
        ...pagination,
        onPageChange: handlePageChange,
      } : undefined}
      showActions={showActions}
      enableInlineEdit={enableInlineEdit}
      enableSearch={enableSearch}
      enablePagination={enablePagination}
    />
  );
};
