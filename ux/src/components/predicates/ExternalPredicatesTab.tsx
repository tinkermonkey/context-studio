/**
 * External Predicates Tab Component
 *
 * Displays external predicates with pagination and filtering by source.
 * Supports US-2.1: Find Similar Predicates Across Sources
 */

import React, { useState, lazy, Suspense } from "react";
import {
  Badge,
  Button,
  Dropdown,
  DropdownDivider,
  DropdownItem,
  Modal,
  ModalBody,
  ModalHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
  TextInput,
} from "flowbite-react";
import { Search, RefreshCw, X, ChevronDown, Info } from "lucide-react";
import {
  useExternalPredicates,
  useDiscoverPredicates,
  useSearchExternalPredicates,
} from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";
import { getSourceBadgeColor } from "@/utils/sourceUtils";

// Lazy load the ExamplePredicateUses component to avoid circular dependency issues
const ExamplePredicateUses = lazy(() =>
  import("./ExamplePredicateUses").then((module) => ({
    default: module.ExamplePredicateUses,
  })),
);

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
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [searchThreshold] = useState<number>(0.3);
  const [selectedPredicate, setSelectedPredicate] = useState<{
    source: string;
    externalId: string;
  } | null>(null);
  const toast = useButterToast();

  // Debounce search input (500ms delay)
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 500);

    return () => clearTimeout(timer);
  }, [search]);

  // Determine if we should use search or list
  const useSearch = debouncedSearch.trim().length > 0;

  // Query external predicates (list mode)
  const listQuery = useExternalPredicates(
    {
      skip: (page - 1) * pageSize,
      limit: pageSize,
      source: source || undefined,
    },
    {
      enabled: !useSearch,
    } as any,
  );

  const {
    data: listData,
    isLoading: isListLoading,
    refetch: refetchList,
  } = listQuery;

  // Search external predicates (search mode)
  const { data: searchData, isLoading: isSearchLoading } =
    useSearchExternalPredicates(
      useSearch
        ? {
            query: debouncedSearch,
            source: source || undefined,
            limit: 100, // Get more results for search
            threshold: searchThreshold,
          }
        : undefined,
    );

  // Use search data if searching, otherwise use list data
  const data = useSearch ? searchData : listData;
  const isLoading = useSearch ? isSearchLoading : isListLoading;

  // Discover predicates mutation
  const discoverMutation = useDiscoverPredicates({
    onSuccess: (result: unknown) => {
      toast.success(
        `Predicate discovery started. Task ID: ${(result as Record<string, unknown>)?.task_id}. This may take a few minutes.`,
      );
      // Refetch after a delay to show new predicates
      setTimeout(() => refetchList(), 5000);
    },
    onError: (error: Error) => {
      toast.error(`Failed to start discovery: ${error.message}`);
    },
  });

  const handleDiscoverClick = (sources?: string[]) => {
    discoverMutation.mutate(sources ? { sources } : undefined);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  // Handle search clear
  const handleClearSearch = () => {
    setSearch("");
    setPage(1);
  };

  // In search mode, data is already filtered by vector search
  // In list mode, we show all data as paginated
  const displayData = data?.data || [];
  const totalCount = useSearch ? data?.total || 0 : data?.total || 0;
  const totalPages = useSearch ? 1 : Math.ceil(totalCount / pageSize); // Search doesn't use pagination

  // Available sources for predicate discovery and filtering
  // These are the sources supported by the backend discovery endpoint
  const availableSources = [
    {
      id: "conceptnet",
      label: "ConceptNet",
      color: getSourceBadgeColor("conceptnet"),
    },
    { id: "dbpedia", label: "DBpedia", color: getSourceBadgeColor("dbpedia") },
    {
      id: "wikidata",
      label: "Wikidata",
      color: getSourceBadgeColor("wikidata"),
    },
    {
      id: "schema_org",
      label: "Schema.org",
      color: getSourceBadgeColor("schema_org"),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* Header with Discovery Button */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">External Predicates</h3>
        <Dropdown
          label=""
          dismissOnClick={true}
          renderTrigger={() => (
            <Button size="sm" disabled={discoverMutation.isPending}>
              {discoverMutation.isPending ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Discovering...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Discover Predicates
                  <ChevronDown className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          )}
        >
          <DropdownItem onClick={() => handleDiscoverClick()}>
            All Sources
          </DropdownItem>
          <DropdownDivider />
          {availableSources.map((s) => (
            <DropdownItem
              key={s.id}
              onClick={() => handleDiscoverClick([s.id])}
            >
              <Badge color={s.color} className="mr-2 w-fit">
                {s.id}
              </Badge>
              {s.label}
            </DropdownItem>
          ))}
        </Dropdown>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <TextInput
            placeholder="Search predicates using vector similarity..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1); // Reset to first page when searching
            }}
            icon={Search}
          />
          {search && (
            <button
              type="button"
              onClick={handleClearSearch}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <Dropdown
          label=""
          dismissOnClick={true}
          renderTrigger={() => (
            <Button color="light" size="sm" className="whitespace-nowrap">
              {source ? (
                <>
                  <Badge
                    color={getSourceBadgeColor(source)}
                    className="mr-2 w-fit"
                  >
                    {source}
                  </Badge>
                  Filter: {source}
                </>
              ) : (
                "All Sources"
              )}
              <ChevronDown className="ml-2 h-4 w-4" />
            </Button>
          )}
        >
          <DropdownItem
            onClick={() => {
              setSource("");
              setPage(1);
            }}
          >
            All Sources
          </DropdownItem>
          <DropdownDivider />
          {availableSources.map((s) => (
            <DropdownItem
              key={s.id}
              onClick={() => {
                setSource(s.id);
                setPage(1);
              }}
            >
              <Badge color={s.color} className="mr-2 w-fit">
                {s.id}
              </Badge>
              {s.label}
            </DropdownItem>
          ))}
        </Dropdown>
        {!useSearch && (
          <Select
            sizing="sm"
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
        )}
      </div>

      {/* Results Count */}
      {data && (
        <div className="text-sm text-gray-600 dark:text-gray-400">
          {useSearch ? (
            <>
              Found {displayData.length} matching predicate
              {displayData.length !== 1 ? "s" : ""} using vector search
              {source && ` (filtered by ${source})`} with similarity ≥{" "}
              {(searchThreshold * 100).toFixed(0)}%
            </>
          ) : (
            <>
              {totalCount} total predicate{totalCount !== 1 ? "s" : ""}
              {source && ` from ${source}`}
            </>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spinner size="lg" />
          </div>
        ) : displayData.length === 0 ? (
          <div className="py-8 text-center text-gray-500">
            {useSearch
              ? "No predicates match your search. Try adjusting your query or lowering the similarity threshold."
              : "No external predicates found. Click 'Discover Predicates' to fetch them."}
          </div>
        ) : (
          <Table hoverable>
            <TableHead>
              <TableRow>
                <TableHeadCell>Source</TableHeadCell>
                <TableHeadCell>External ID</TableHeadCell>
                <TableHeadCell>Title</TableHeadCell>
                <TableHeadCell>Definition</TableHeadCell>
                {useSearch && <TableHeadCell>Similarity</TableHeadCell>}
                <TableHeadCell></TableHeadCell>
                <TableHeadCell>
                  <span className="sr-only">Actions</span>
                </TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody className="divide-y">
              {displayData.map((predicate: any) => (
                <TableRow
                  key={predicate.id}
                  className="bg-white dark:border-gray-700 dark:bg-gray-800"
                >
                  <TableCell className="w-fit whitespace-nowrap">
                    <Badge
                      color={getSourceBadgeColor(predicate.source)}
                      className="w-fit"
                    >
                      {predicate.source}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs break-all">
                    {predicate.external_id}
                  </TableCell>
                  <TableCell className="font-medium text-gray-900 dark:text-white">
                    {predicate.title}
                  </TableCell>
                  <TableCell className="break-words">
                    {predicate.definition || (
                      <span className="text-gray-400">—</span>
                    )}
                  </TableCell>
                  {useSearch && (
                    <TableCell className="">
                      <Badge
                        color={
                          predicate.similarity_score >= 0.8
                            ? "success"
                            : predicate.similarity_score >= 0.7
                              ? "warning"
                              : "gray"
                        }
                      >
                        {(predicate.similarity_score * 100).toFixed(0)}%
                      </Badge>
                    </TableCell>
                  )}
                  <TableCell className="">
                    <Button
                      size="xs"
                      color="light"
                      onClick={() =>
                        setSelectedPredicate({
                          source: predicate.source,
                          externalId: predicate.external_id,
                        })
                      }
                      title="View example uses"
                    >
                      <Info className="h-4 w-4" />
                    </Button>
                  </TableCell>
                  <TableCell className="w-1">
                    {onPredicateSelect && (
                      <Button
                        size="xs"
                        onClick={() => onPredicateSelect(predicate.id)}
                      >
                        Select
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Pagination */}
      {!useSearch && data && totalCount > 0 && (
        <div className="mt-4 flex w-full items-center justify-between px-4">
          {totalPages > 1 ? (
            <>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2">
                  <Select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setPage(1);
                    }}
                    className="w-20"
                  >
                    <option value="10">10</option>
                    <option value="20">20</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                  </Select>
                  <span className="text-sm text-gray-600">per page,</span>
                </div>
                <div className="text-sm font-normal text-gray-700">
                  showing{" "}
                  <Badge className="inline" color="gray">
                    predicates
                  </Badge>{" "}
                  <span className="font-bold">{(page - 1) * pageSize + 1}</span>
                  -
                  <span className="font-bold">
                    {Math.min(page * pageSize, totalCount)}
                  </span>
                  &nbsp;of&nbsp;<span className="font-bold">{totalCount}</span>
                </div>
              </div>
              <div>
                <Pagination
                  layout="pagination"
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={(newPage) => handlePageChange(newPage)}
                  showIcons
                  nextLabel=""
                  previousLabel=""
                />
              </div>
            </>
          ) : (
            <div className="text-sm font-normal text-gray-700">
              Showing{" "}
              <Badge className="inline" color="gray">
                predicates
              </Badge>{" "}
              <span className="font-bold">{(page - 1) * pageSize + 1}</span>-
              <span className="font-bold">
                {Math.min(page * pageSize, totalCount)}
              </span>
              &nbsp;of&nbsp;<span className="font-bold">{totalCount}</span>
            </div>
          )}
        </div>
      )}

      {/* Example Uses Modal */}
      <Modal
        show={!!selectedPredicate}
        onClose={() => setSelectedPredicate(null)}
        size="4xl"
      >
        <ModalHeader>Example Uses of Predicate</ModalHeader>
        <ModalBody>
          {selectedPredicate && (
            <Suspense
              fallback={
                <div className="flex items-center justify-center py-8">
                  <Spinner size="lg" />
                </div>
              }
            >
              <ExamplePredicateUses
                source={selectedPredicate.source}
                externalId={selectedPredicate.externalId}
                limit={10}
              />
            </Suspense>
          )}
        </ModalBody>
      </Modal>
    </div>
  );
};
