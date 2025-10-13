/**
 * Similarity Search Tab Component
 *
 * Provides similarity search interface with ranked results and scores.
 * Supports US-2.1: Find Similar Predicates Across Sources
 * Supports US-2.2: Cluster Related Predicates (visualization)
 */

import React, { useState } from "react";
import { Table, Button, TextInput, Spinner, Badge, Label, Select } from "flowbite-react";
import { Search, X } from "lucide-react";
import { useSimilarPredicates } from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";

export interface SimilaritySearchTabProps {
  onClusterSelect?: (predicateIds: string[]) => void;
}

export const SimilaritySearchTab: React.FC<SimilaritySearchTabProps> = ({
  onClusterSelect,
}) => {
  const [predicateId, setPredicateId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [thresholdFilter, setThresholdFilter] = useState<number>(0.7);
  const [topK, setTopK] = useState<number>(20);
  const toast = useButterToast();

  // Query similar predicates
  const {
    data,
    isLoading,
    error,
    isFetching,
  } = useSimilarPredicates(
    {
      predicate_id: searchQuery || predicateId,
      top_k: topK,
      source_filter: sourceFilter || undefined,
      similarity_threshold: thresholdFilter,
    },
    {
      enabled: !!(searchQuery || predicateId),
    },
  );

  // Handle error display
  React.useEffect(() => {
    if (error) {
      toast.error(`Failed to find similar predicates: ${error.message}`);
    }
  }, [error, toast]);

  const handleSearch = () => {
    if (!searchQuery.trim()) {
      toast.warning("Please enter a predicate ID to search");
      return;
    }
    setPredicateId(searchQuery);
  };

  const handleClear = () => {
    setSearchQuery("");
    setPredicateId("");
    setSourceFilter("");
    setThresholdFilter(0.7);
  };

  // Get unique sources from results
  const availableSources = React.useMemo(() => {
    if (!data?.similar_predicates) return [];
    const sources = new Set(
      data.similar_predicates.map((item) => item.predicate.source),
    );
    return Array.from(sources).sort();
  }, [data?.similar_predicates]);

  // Filter results by threshold
  const filteredResults = React.useMemo(() => {
    if (!data?.similar_predicates) return [];
    return data.similar_predicates.filter(
      (item) => item.similarity_score >= thresholdFilter,
    );
  }, [data?.similar_predicates, thresholdFilter]);

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
            Predicate ID
          </Label>
          <div className="flex gap-2">
            <TextInput
              id="predicate-search"
              placeholder="Enter predicate ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={isLoading || !searchQuery.trim()}>
              {isLoading ? (
                <Spinner size="sm" />
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Search
                </>
              )}
            </Button>
          </div>
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
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Found {filteredResults.length} similar predicates
            {sourceFilter && ` from ${sourceFilter}`}
            {filteredResults.length > 0 && onClusterSelect && (
              <Button
                size="xs"
                color="light"
                className="ml-4"
                onClick={() =>
                  onClusterSelect(filteredResults.map((item) => item.predicate.id))
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
                <Table.Head>
                  <Table.HeadCell>Similarity</Table.HeadCell>
                  <Table.HeadCell>Quality</Table.HeadCell>
                  <Table.HeadCell>Source</Table.HeadCell>
                  <Table.HeadCell>External ID</Table.HeadCell>
                  <Table.HeadCell>Title</Table.HeadCell>
                  <Table.HeadCell>Definition</Table.HeadCell>
                </Table.Head>
                <Table.Body className="divide-y">
                  {filteredResults.map((item, index) => (
                    <Table.Row
                      key={`${item.predicate.id}-${index}`}
                      className="bg-white dark:border-gray-700 dark:bg-gray-800"
                    >
                      <Table.Cell>
                        <Badge color={getQualityColor(item.similarity_score)} size="sm">
                          {(item.similarity_score * 100).toFixed(1)}%
                        </Badge>
                      </Table.Cell>
                      <Table.Cell>
                        <Badge color={getQualityColor(item.similarity_score)} size="sm">
                          {getQualityLabel(item.similarity_score)}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell>
                        <Badge color="info">{item.predicate.source}</Badge>
                      </Table.Cell>
                      <Table.Cell className="font-mono text-sm">
                        {item.predicate.external_id}
                      </Table.Cell>
                      <Table.Cell className="font-medium text-gray-900 dark:text-white">
                        {item.predicate.title}
                      </Table.Cell>
                      <Table.Cell className="max-w-md truncate">
                        {item.predicate.definition || (
                          <span className="text-gray-400">—</span>
                        )}
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table>
            )}
          </div>
        </>
      )}

      {!isFetching && !data && (
        <div className="py-8 text-center text-gray-500">
          Enter a predicate ID to search for similar predicates
        </div>
      )}
    </div>
  );
};
