/**
 * External Predicates Tab Component
 *
 * Displays external predicates with pagination and filtering by source.
 * Supports US-2.1: Find Similar Predicates Across Sources
 */

import React, { useState } from "react";
import { Table, Button, Select, Spinner, Badge, TextInput } from "flowbite-react";
import { Search, RefreshCw } from "lucide-react";
import { useExternalPredicates, useDiscoverPredicates } from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";

export interface ExternalPredicatesTabProps {
  onPredicateSelect?: (predicateId: string) => void;
}

export const ExternalPredicatesTab: React.FC<ExternalPredicatesTabProps> = ({
  onPredicateSelect,
}) => {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [source, setSource] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const toast = useButterToast();

  // Query external predicates
  const {
    data,
    isLoading,
    error,
    refetch,
  } = useExternalPredicates({
    page,
    page_size: pageSize,
    source: source || undefined,
  });

  // Discover predicates mutation
  const discoverMutation = useDiscoverPredicates({
    onSuccess: (result) => {
      toast.success(
        `Predicate discovery started. Task ID: ${result.task_id}. This may take a few minutes.`,
      );
      // Refetch after a delay to show new predicates
      setTimeout(() => refetch(), 5000);
    },
    onError: (error: Error) => {
      toast.error(`Failed to start discovery: ${error.message}`);
    },
  });

  // Handle error display
  React.useEffect(() => {
    if (error) {
      toast.error(`Failed to load external predicates: ${error.message}`);
    }
  }, [error, toast]);

  const handleDiscoverClick = () => {
    discoverMutation.mutate();
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  // Filter predicates by search term
  const filteredPredicates = React.useMemo(() => {
    if (!data?.items || !search.trim()) return data?.items || [];
    const searchLower = search.toLowerCase();
    return data.items.filter(
      (p) =>
        p.title.toLowerCase().includes(searchLower) ||
        p.external_id.toLowerCase().includes(searchLower) ||
        p.definition?.toLowerCase().includes(searchLower),
    );
  }, [data?.items, search]);

  const totalPages = data?.total ? Math.ceil(data.total / pageSize) : 0;

  // Get unique sources for filter dropdown
  const availableSources = React.useMemo(() => {
    if (!data?.items) return [];
    const sources = new Set(data.items.map((p) => p.source));
    return Array.from(sources).sort();
  }, [data?.items]);

  return (
    <div className="flex flex-col gap-4">
      {/* Header with Discovery Button */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">External Predicates</h3>
        <Button
          size="sm"
          onClick={handleDiscoverClick}
          disabled={discoverMutation.isPending}
        >
          {discoverMutation.isPending ? (
            <>
              <Spinner size="sm" className="mr-2" />
              Discovering...
            </>
          ) : (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Discover Predicates
            </>
          )}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <div className="flex-1">
          <TextInput
            placeholder="Search predicates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={Search}
          />
        </div>
        <Select
          value={source}
          onChange={(e) => {
            setSource(e.target.value);
            setPage(1); // Reset to first page when changing filter
          }}
          className="w-48"
        >
          <option value="">All Sources</option>
          {availableSources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Select
          value={pageSize.toString()}
          onChange={(e) => {
            setPageSize(Number(e.target.value));
            setPage(1); // Reset to first page when changing page size
          }}
          className="w-32"
        >
          <option value="10">10 per page</option>
          <option value="20">20 per page</option>
          <option value="50">50 per page</option>
          <option value="100">100 per page</option>
        </Select>
      </div>

      {/* Results Count */}
      {data && (
        <div className="text-sm text-gray-600 dark:text-gray-400">
          Showing {filteredPredicates.length} of {data.total} external predicates
          {source && ` from ${source}`}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spinner size="lg" />
          </div>
        ) : filteredPredicates.length === 0 ? (
          <div className="py-8 text-center text-gray-500">
            {search.trim()
              ? "No predicates match your search"
              : "No external predicates found. Click 'Discover Predicates' to fetch them."}
          </div>
        ) : (
          <Table hoverable>
            <Table.Head>
              <Table.HeadCell>Source</Table.HeadCell>
              <Table.HeadCell>External ID</Table.HeadCell>
              <Table.HeadCell>Title</Table.HeadCell>
              <Table.HeadCell>Definition</Table.HeadCell>
              <Table.HeadCell>
                <span className="sr-only">Actions</span>
              </Table.HeadCell>
            </Table.Head>
            <Table.Body className="divide-y">
              {filteredPredicates.map((predicate) => (
                <Table.Row
                  key={predicate.id}
                  className="bg-white dark:border-gray-700 dark:bg-gray-800"
                >
                  <Table.Cell>
                    <Badge color="info">{predicate.source}</Badge>
                  </Table.Cell>
                  <Table.Cell className="font-mono text-sm">
                    {predicate.external_id}
                  </Table.Cell>
                  <Table.Cell className="font-medium text-gray-900 dark:text-white">
                    {predicate.title}
                  </Table.Cell>
                  <Table.Cell className="max-w-md truncate">
                    {predicate.definition || <span className="text-gray-400">—</span>}
                  </Table.Cell>
                  <Table.Cell>
                    {onPredicateSelect && (
                      <Button
                        size="xs"
                        onClick={() => onPredicateSelect(predicate.id)}
                      >
                        Select
                      </Button>
                    )}
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Page {page} of {totalPages}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={page === 1}
              onClick={() => handlePageChange(page - 1)}
            >
              Previous
            </Button>
            <Button
              size="sm"
              disabled={page === totalPages}
              onClick={() => handlePageChange(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
