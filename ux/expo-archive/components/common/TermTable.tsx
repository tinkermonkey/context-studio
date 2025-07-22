/**
 * TermTable Component
 *
 * A specialized table component for viewing and editing terms
 */

import React, { useState } from 'react';
import { EditableTable } from '../common/EditableTable';
import { useTerms, useTermsSearch, useUpdateTerm, useDeleteTerm } from '../../api/hooks/terms';
import { handleApiError } from '../../api/errors/errorHandlers';
import type { components } from '../../api/client/types';

type TermUpdate = components['schemas']['TermUpdate'];

interface TermTableProps {
  domainId?: string;
  layerId?: string;
  showActions?: boolean;
  enableInlineEdit?: boolean;
  enableSearch?: boolean;
  enablePagination?: boolean;
  pageSize?: number;
}

export const TermTable: React.FC<TermTableProps> = ({
  domainId,
  layerId,
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
  const listQuery = useTerms(
    { 
      ...(enablePagination ? pagination : {}),
      ...(domainId ? { domain_id: domainId } : {}),
      ...(layerId ? { layer_id: layerId } : {})
    }
  );

  const searchQuery_ = useTermsSearch(
    searchQuery
  );

  const updateTerm = useUpdateTerm();
  const deleteTerm = useDeleteTerm();

  // Use search results if searching, otherwise use list results
  const data = isSearching ? (searchQuery_.data || []) : (listQuery.data || []);
  const isLoading = isSearching ? searchQuery_.isLoading : listQuery.isLoading;
  const error = isSearching ? searchQuery_.error : listQuery.error;

  const handleUpdate = async (id: string, updateData: TermUpdate) => {
    try {
      await updateTerm.mutateAsync({ id, data: updateData });
    } catch (error) {
      handleApiError(error);
      throw error;
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTerm.mutateAsync(id);
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
      nodeType="term"
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
