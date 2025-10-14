/**
 * Similarity Search Tab Component
 *
 * Provides similarity search interface with ranked results and scores.
 * Supports US-2.1: Find Similar Predicates Across Sources
 * Supports US-2.2: Cluster Related Predicates (visualization)
 */

import React, { useState, useEffect } from "react";
import { Table, TableHead, TableHeadCell, TableBody, TableRow, TableCell, Button, Spinner, Badge, Label, Select } from "flowbite-react";
import { Search, X } from "lucide-react";
import { useSimilarPredicates } from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";
import { getSourceBadgeColor } from "@/utils/sourceUtils";
import { PredicateSelector } from "@/components/node_selectors/predicate_selector";
import { PredicateOut } from "@/api/services/predicates";

export interface SimilaritySearchTabProps {
  onClusterSelect?: (predicateIds: string[]) => void;
}

export const SimilaritySearchTab: React.FC<SimilaritySearchTabProps> = ({
  onClusterSelect,
}) => {
  const [selectedPredicate, setSelectedPredicate] = useState<PredicateOut | undefined>();
  const [debouncedPredicateId, setDebouncedPredicateId] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [thresholdFilter, setThresholdFilter] = useState<number>(0.7);
  const [topK, setTopK] = useState<number>(20);
  const toast = useButterToast();

  // Debounce the predicate ID to avoid searching immediately on selection
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedPredicateId(selectedPredicate?.id || "");
    }, 500);

    return () => {
      clearTimeout(timer);
    };
  }, [selectedPredicate?.id]);

  // Query similar predicates using the debounced predicate ID
  const {
    data,
    isLoading,
    error,
    isFetching,
  } = useSimilarPredicates(debouncedPredicateId, {
    limit: topK,
    source: sourceFilter || undefined,
    threshold: thresholdFilter,
  });

  // Handle error display
  React.useEffect(() => {
    if (error) {
      toast.error(`Failed to find similar predicates: ${error.message}`);
    }
  }, [error, toast]);

  const handleClear = () => {
    setSelectedPredicate(undefined);
    setDebouncedPredicateId("");
    setSourceFilter("");
    setThresholdFilter(0.7);
  };

  // Get unique sources from results
  const availableSources = React.useMemo(() => {
    if (!data?.results) return [];
    const sources = new Set(
      data.results.map((item) => item.source),
    );
    return Array.from(sources).sort();
  }, [data?.results]);

  // Filter results by threshold
  const filteredResults = React.useMemo(() => {
    if (!data?.results) return [];
    return data.results.filter(
      (item) => item.similarity_score >= thresholdFilter,
    );
  }, [data?.results, thresholdFilter]);

  // Calculate quality indicator
  const getQualityColor = (score: number): string => {
    if (score >= 0.9) return "success";
    if (score >= 0.8) return "info";
    if (score >= 0.7) return "warning";
    return "failure";
  };

  const getQualityLabel = (score: number): string => {
    if (score >= 0.9) return "Excellent";
    if (score >= 0.8) return "Good";
    if (score >= 0.7) return "Fair";
    return "Poor";
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Similarity Search</h3>
        {data && (
          <Button size="xs" color="light" onClick={handleClear}>
            <X className="mr-2 h-4 w-4" />
            Clear
          </Button>
        )}
      </div>

      {/* Search Form */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <Label htmlFor="predicate-search" className="mb-2 block">
            Select Predicate
          </Label>
          <PredicateSelector
            value={selectedPredicate?.id}
            onSelect={(predicate) => setSelectedPredicate(predicate)}
            placeholder="Search and select a predicate..."
            disabled={isLoading}
          />
          {selectedPredicate && (
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              Selected: <span className="font-medium">{selectedPredicate.title}</span>
            </p>
          )}
        </div>

        <div>
          <Label htmlFor="top-k" className="mb-2 block">
            Number of Results
          </Label>
          <Select
            id="top-k"
            value={topK.toString()}
            onChange={(e) => setTopK(Number(e.target.value))}
          >
            <option value="10">10 results</option>
            <option value="20">20 results</option>
            <option value="50">50 results</option>
            <option value="100">100 results</option>
          </Select>
        </div>
      </div>

      {/* Filters */}
      {data && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="source-filter" className="mb-2 block">
              Filter by Source
            </Label>
            <Select
              id="source-filter"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="">All Sources</option>
              {availableSources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label htmlFor="threshold-filter" className="mb-2 block">
              Minimum Similarity: {thresholdFilter.toFixed(2)}
            </Label>
            <input
              type="range"
              id="threshold-filter"
              min="0"
              max="1"
              step="0.05"
              value={thresholdFilter}
              onChange={(e) => setThresholdFilter(Number(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      )}

      {/* Results */}
      {isFetching && (
        <div className="flex items-center justify-center py-8">
          <Spinner size="lg" />
        </div>
      )}

      {!isFetching && data && (
        <>
          <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <span className="font-semibold">Searching for predicates similar to:</span>{" "}
              {data.predicate_title}
            </p>
          </div>

          <div className="text-sm text-gray-600 dark:text-gray-400">
            Found {filteredResults.length} similar predicates
            {sourceFilter && ` from ${sourceFilter}`}
            {filteredResults.length > 0 && onClusterSelect && (
              <Button
                size="xs"
                color="light"
                className="ml-4"
                onClick={() =>
                  onClusterSelect(filteredResults.map((item) => item.predicate_id))
                }
              >
                Create Cluster from Results
              </Button>
            )}
          </div>

          <div className="overflow-x-auto">
            {filteredResults.length === 0 ? (
              <div className="py-8 text-center text-gray-500">
                No similar predicates found with similarity ≥ {thresholdFilter.toFixed(2)}
              </div>
            ) : (
              <Table hoverable>
                <TableHead>
                  <TableRow>
                    <TableHeadCell>Similarity</TableHeadCell>
                    <TableHeadCell>Quality</TableHeadCell>
                    <TableHeadCell>Source</TableHeadCell>
                    <TableHeadCell>External ID</TableHeadCell>
                    <TableHeadCell>Title</TableHeadCell>
                    <TableHeadCell>Definition</TableHeadCell>
                  </TableRow>
                </TableHead>
                <TableBody className="divide-y">{filteredResults.map((item, index) => (
                    <TableRow
                      key={`${item.predicate_id}-${index}`}
                      className="bg-white dark:border-gray-700 dark:bg-gray-800"
                    >
                      <TableCell>
                        <Badge color={getQualityColor(item.similarity_score)} size="sm">
                          {(item.similarity_score * 100).toFixed(1)}%
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge color={getQualityColor(item.similarity_score)} size="sm">
                          {getQualityLabel(item.similarity_score)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge color={getSourceBadgeColor(item.source)}>{item.source}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {item.source_id}
                      </TableCell>
                      <TableCell className="font-medium text-gray-900 dark:text-white">
                        {item.title}
                      </TableCell>
                      <TableCell className="max-w-md truncate">
                        {item.definition || (
                          <span className="text-gray-400">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </>
      )}

      {!isFetching && !data && (
        <div className="py-12 text-center">
          <Search className="mx-auto h-12 w-12 text-gray-400" />
          <p className="mt-4 text-gray-500 dark:text-gray-400">
            Select a predicate above to find similar external predicates
          </p>
          <p className="mt-2 text-sm text-gray-400 dark:text-gray-500">
            Search across ConceptNet, DBpedia, Wikidata, and Schema.org
          </p>
        </div>
      )}
    </div>
  );
};
