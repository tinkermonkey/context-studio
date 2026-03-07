/**
 * Mapping Configuration Tab Component
 *
 * Displays filtering statistics and configuration options.
 * Supports US-4.2: Toggle Predicate Filtering
 * Supports US-4.3: View Filtered Relationship Statistics
 */

import React from "react";
import { Badge, Button, Card, Spinner, ToggleSwitch } from "flowbite-react";
import { RefreshCw, Filter, CheckCircle, XCircle } from "lucide-react";
import { useFilterStatistics } from "@/api/hooks/reference/useReference";
import { useButterToast } from "@/hooks/useButterToast";

const STORAGE_KEY = "predicate_filter_enabled";

export interface MappingConfigurationTabProps {
  onFilterToggle?: (enabled: boolean) => void;
}

export const MappingConfigurationTab: React.FC<
  MappingConfigurationTabProps
> = ({ onFilterToggle }) => {
  // Session storage for filter toggle state
  const [filterEnabled, setFilterEnabled] = React.useState<boolean>(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return stored !== null ? JSON.parse(stored) : true;
  });

  const toast = useButterToast();

  // Query filter statistics
  const { data, isLoading, error, refetch, isFetching } = useFilterStatistics();

  // Handle error display
  React.useEffect(() => {
    if (error) {
      toast.error(`Failed to load filter statistics: ${error.message}`);
    }
  }, [error, toast]);

  // Handle filter toggle
  const handleFilterToggle = (enabled: boolean) => {
    setFilterEnabled(enabled);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(enabled));
    if (onFilterToggle) {
      onFilterToggle(enabled);
    }
    toast.success(
      enabled ? "Predicate filtering enabled" : "Predicate filtering disabled",
    );
  };

  // Format large numbers
  const formatNumber = (num: number | undefined): string => {
    if (num === undefined || num === null) return "0";
    return num.toLocaleString();
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Configuration & Statistics</h3>
        <Button
          size="sm"
          color="light"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          {isFetching ? (
            <Spinner size="sm" className="mr-2" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      {/* Filter Toggle */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Filter className="h-5 w-5 text-gray-600 dark:text-gray-400" />
            <div>
              <h4 className="font-medium text-gray-900 dark:text-white">
                Relevance Filtering
              </h4>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Filter relationships based on predicate relevance ratings
              </p>
            </div>
          </div>
          <ToggleSwitch
            checked={filterEnabled}
            onChange={handleFilterToggle}
            label=""
          />
        </div>
      </Card>

      {/* Statistics */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Spinner size="xl" />
        </div>
      )}

      {!isLoading && data && (
        <>
          {/* Overall Status */}
          <Card>
            <div className="mb-4 flex items-center gap-2">
              {data.filtering_ready ? (
                <>
                  <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                  <span className="font-medium text-green-600 dark:text-green-400">
                    Filtering Ready
                  </span>
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-orange-600 dark:text-orange-400" />
                  <span className="font-medium text-orange-600 dark:text-orange-400">
                    Filtering Not Ready
                  </span>
                </>
              )}
            </div>
            {!data.filtering_ready && (
              <p className="text-sm text-gray-600 dark:text-gray-400">
                No predicates have been marked as relevant yet. Visit the
                "Relevance Selection" tab to mark predicates.
              </p>
            )}
          </Card>

          {/* Predicate Statistics */}
          <Card>
            <h4 className="mb-4 text-base font-medium">Predicate Statistics</h4>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                  {formatNumber(data.relevant_predicates_count)}
                </div>
                <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  Relevant
                </div>
              </div>

              <div className="text-center">
                <div className="text-3xl font-bold text-red-600 dark:text-red-400">
                  {formatNumber(data.irrelevant_predicates_count)}
                </div>
                <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  Irrelevant
                </div>
              </div>

              <div className="text-center">
                <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {formatNumber(data.external_predicate_count)}
                </div>
                <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  Total External
                </div>
              </div>

              <div className="text-center">
                <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">
                  {formatNumber(data.total_mappings)}
                </div>
                <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  Total Mappings
                </div>
              </div>
            </div>
          </Card>

          {/* External Predicates by Source */}
          {data.external_predicates_by_source &&
            Object.keys(data.external_predicates_by_source).length > 0 && (
              <Card>
                <h4 className="mb-4 text-base font-medium">
                  External Predicates by Source
                </h4>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(data.external_predicates_by_source)
                    .sort(([, a], [, b]) => b - a) // Sort by count descending
                    .map(([source, count]) => (
                      <div
                        key={source}
                        className="flex items-center justify-between rounded-lg bg-gray-50 p-3 dark:bg-gray-700"
                      >
                        <div className="flex items-center gap-2">
                          <Badge color="info" size="sm">
                            {source}
                          </Badge>
                        </div>
                        <div className="text-lg font-bold text-gray-900 dark:text-white">
                          {formatNumber(count)}
                        </div>
                      </div>
                    ))}
                </div>
              </Card>
            )}

          {/* Filtering Impact (if enabled) */}
          {filterEnabled && data.filtering_ready && (
            <Card>
              <h4 className="mb-4 text-base font-medium">Filtering Impact</h4>
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Predicates in Use
                  </span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {formatNumber(data.relevant_predicates_count)} /{" "}
                    {formatNumber(data.external_predicate_count)}
                  </span>
                </div>

                <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Filter Coverage
                  </span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {data.external_predicate_count > 0
                      ? (
                          ((data.relevant_predicates_count +
                            data.irrelevant_predicates_count) /
                            data.external_predicate_count) *
                          100
                        ).toFixed(1)
                      : 0}
                    %
                  </span>
                </div>

                <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Unrated Predicates
                  </span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {formatNumber(
                      data.external_predicate_count -
                        data.relevant_predicates_count -
                        data.irrelevant_predicates_count,
                    )}
                  </span>
                </div>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
};
