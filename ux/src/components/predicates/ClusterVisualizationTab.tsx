/**
 * Cluster Visualization Tab Component
 *
 * Visualizes predicate clusters with quality indicators.
 * Supports US-2.2: Cluster Related Predicates
 * Supports US-3.1: Create Global Predicate from Cluster
 */

import React, { useState } from "react";
import { Button,
  Card,
  Spinner,
  Label,
  TextInput,
  Select,
 } from "flowbite-react";
import { GitBranch, Plus } from "lucide-react";
import { useClusterPredicates } from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";

export interface ClusterVisualizationTabProps {
  onCreateGlobalPredicate?: (clusterPredicates: string[]) => void;
}

export const ClusterVisualizationTab: React.FC<
  ClusterVisualizationTabProps
> = ({ onCreateGlobalPredicate }) => {
  const [minSamples, setMinSamples] = useState<number>(2);
  const [eps, setEps] = useState<number>(0.3);
  const [sourceFilter, setSourceFilter] = useState<string>("");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [clusters, setClusters] = useState<any>(null);
  const toast = useButterToast();

  // Cluster predicates mutation
  const clusterMutation = useClusterPredicates({
    onSuccess: (result) => {
      setClusters(result);
      const clusteredCount = result.clusters.reduce(
        (sum, c) => sum + c.size,
        0,
      );
      toast.success(
        `Found ${result.total_clusters} clusters with ${clusteredCount} clustered predicates`,
      );
    },
    onError: (error: Error) => {
      toast.error(`Failed to cluster predicates: ${error.message}`);
    },
  });

  const handleCluster = () => {
    clusterMutation.mutate({
      min_samples: minSamples,
      eps,
      source_filter: sourceFilter || undefined,
    });
  };

  const handleCreateGlobalPredicate = (clusterPredicates: string[]) => {
    if (onCreateGlobalPredicate) {
      onCreateGlobalPredicate(clusterPredicates);
    } else {
      toast.info("Global predicate creation not configured");
    }
  };

  // Calculate cluster quality based on size and cohesion
  const getClusterQuality = (
   
    cluster: any,  // eslint-disable-line @typescript-eslint/no-explicit-any

  ): { color: string; label: string } => {
    const size = cluster.predicate_ids.length;
    const avgSimilarity = cluster.avg_similarity || 0;

    if (size >= 5 && avgSimilarity >= 0.8) {
      return { color: "success", label: "Excellent" };
    } else if (size >= 3 && avgSimilarity >= 0.7) {
      return { color: "info", label: "Good" };
    } else if (size >= 2 && avgSimilarity >= 0.6) {
      return { color: "warning", label: "Fair" };
    }
    return { color: "failure", label: "Poor" };
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Cluster Visualization</h3>
      </div>

      {/* Clustering Parameters */}
      <Card>
        <h4 className="mb-4 text-base font-medium">Clustering Parameters</h4>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <Label htmlFor="eps" className="mb-2 block">
              Distance Threshold (ε): {eps.toFixed(2)}
            </Label>
            <input
              type="range"
              id="eps"
              min="0.1"
              max="1.0"
              step="0.05"
              value={eps}
              onChange={(e) => setEps(Number(e.target.value))}
              className="w-full"
            />
            <p className="mt-1 text-xs text-gray-500">
              Maximum distance between two predicates to be in the same cluster
            </p>
          </div>

          <div>
            <Label htmlFor="min-samples" className="mb-2 block">
              Minimum Samples
            </Label>
            <TextInput
              id="min-samples"
              type="number"
              min="2"
              max="20"
              value={minSamples}
              onChange={(e) => setMinSamples(Number(e.target.value))}
            />
            <p className="mt-1 text-xs text-gray-500">
              Minimum number of predicates to form a cluster
            </p>
          </div>

          <div>
            <Label htmlFor="source-filter-cluster" className="mb-2 block">
              Filter by Source
            </Label>
            <Select
              id="source-filter-cluster"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="">All Sources</option>
              <option value="conceptnet">ConceptNet</option>
              <option value="dbpedia">DBpedia</option>
              <option value="wikidata">Wikidata</option>
            </Select>
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <Button onClick={handleCluster} disabled={clusterMutation.isPending}>
            {clusterMutation.isPending ? (
              <>
                <Spinner size="sm" className="mr-2" />
                Clustering...
              </>
            ) : (
              <>
                <GitBranch className="mr-2 h-4 w-4" />
                Run Clustering
              </>
            )}
          </Button>
        </div>
      </Card>

      {/* Results */}
      {clusterMutation.isPending && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <Spinner size="xl" />
            <p className="mt-4 text-gray-600 dark:text-gray-400">
              Analyzing predicates and forming clusters...
            </p>
          </div>
        </div>
      )}

      {clusters && !clusterMutation.isPending && (
        <>
          {/* Summary */}
          <Card>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {clusters.total_clusters}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Clusters Found
                </div>
              </div>
              <div>
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                  {clusters.clusters.reduce(
   
                    (sum: number, c: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => sum + c.size,
                    0,
                  )}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Clustered Predicates
                </div>
              </div>
              <div>
                <div className="text-3xl font-bold text-gray-600 dark:text-gray-400">
                  {clusters.total_predicates -
                    clusters.clusters.reduce(
   
                      (sum: number, c: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => sum + c.size,
                      0,
                    )}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Outliers
                </div>
              </div>
            </div>
          </Card>

          {/* Clusters */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
            {clusters.clusters.map((cluster: any,  // eslint-disable-line @typescript-eslint/no-explicit-any
 index: number) => {
              const quality = getClusterQuality(cluster);
              return (
                <Card key={index}>
                  <div className="flex items-start justify-between">
                    <div>
                      <h5 className="mb-2 text-lg font-bold text-gray-900 dark:text-white">
                        Cluster {cluster.cluster_id}
                      </h5>
                      <div className="mb-2 flex items-center gap-2">
                        <Badge color="info" size="sm">
                          {cluster.predicate_ids.length} predicates
                        </Badge>
                        <Badge color={quality.color} size="sm">
                          {quality.label}
                        </Badge>
                      </div>
                    </div>
                    <Button
                      size="xs"
                      onClick={() =>
                        handleCreateGlobalPredicate(cluster.predicate_ids)
                      }
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>

                  {cluster.representative_predicate && (
                    <div className="mt-2 rounded-lg bg-gray-50 p-2 dark:bg-gray-700">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {cluster.representative_predicate.title}
                      </p>
                      {cluster.representative_predicate.definition && (
                        <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                          {cluster.representative_predicate.definition}
                        </p>
                      )}
                    </div>
                  )}

                  {cluster.avg_similarity && (
                    <div className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                      Avg. Similarity:{" "}
                      {(cluster.avg_similarity * 100).toFixed(1)}%
                    </div>
                  )}

                  {cluster.sources && cluster.sources.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {cluster.sources.map((source: string) => (
                        <Badge key={source} color="gray" size="xs">
                          {source}
                        </Badge>
                      ))}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>

          {clusters.total_clusters === 0 && (
            <Card>
              <div className="py-8 text-center text-gray-500">
                No clusters found with the current parameters. Try adjusting the
                distance threshold (ε) or minimum samples.
              </div>
            </Card>
          )}
        </>
      )}

      {!clusters && !clusterMutation.isPending && (
        <Card>
          <div className="py-8 text-center text-gray-500">
            Configure clustering parameters and click "Run Clustering" to
            analyze predicates
          </div>
        </Card>
      )}
    </div>
  );
};
