import React, { useEffect, useRef } from "react";
import { Badge, Button, Card, Progress, Spinner } from "flowbite-react";
import {
  Activity,
  AlertCircle,
  Calendar,
  ChevronRight,
  Clock,
  Database,
  FileText,
  Hash,
  RefreshCw,
  Settings,
  Square,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useActiveDataset } from "@/api/hooks/datasets/useDatasets";
import { useEmbeddingRegeneration } from "@/api/hooks/embeddings/useEmbeddingRegeneration";

interface CurrentDatasetCardProps {
  className?: string;
}

export const CurrentDatasetCard: React.FC<CurrentDatasetCardProps> = ({
  className = "",
}) => {
  const { data: activeDataset, isLoading, error } = useActiveDataset();
  const {
    status: embeddingStatus,
    progress: embeddingProgress,
    error: embeddingError,
    connect,
    disconnect,
    stopRegeneration,
  } = useEmbeddingRegeneration();

  const previousDatasetId = useRef<string | null>(null);

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleStartRegeneration = (force = false) => {
    connect(force);
  };

  const handleStopRegeneration = async () => {
    await stopRegeneration();
  };

  const isEmbeddingRunning = embeddingStatus === "running";

  // Reset embedding status when dataset actually changes
  useEffect(() => {
    const currentDatasetId = activeDataset?.id;

    // If dataset actually changed (not just initial load)
    if (
      previousDatasetId.current &&
      previousDatasetId.current !== currentDatasetId &&
      embeddingStatus !== "disconnected"
    ) {
      disconnect();
    }

    // Update the ref
    previousDatasetId.current = currentDatasetId || null;
  }, [activeDataset?.id, disconnect, embeddingStatus]);

  if (isLoading) {
    return (
      <Card className={`w-full ${className}`}>
        <div className="flex items-center justify-center py-8">
          <Spinner size="lg" />
          <span className="ml-3 text-sm">Loading current dataset...</span>
        </div>
      </Card>
    );
  }

  if (error || !activeDataset) {
    return (
      <Card className={`w-full ${className}`}>
        <div className="py-8 text-center">
          <Database className="mx-auto mb-4 h-12 w-12 text-gray-400" />
          <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
            No Active Dataset
          </h3>
          <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
            {error
              ? "Failed to load dataset information"
              : "No dataset is currently active"}
          </p>
          <Link to="/app/datasets">
            <Button size="sm">
              Manage Datasets
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <Card className={`w-full ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="flex-shrink-0">
            <Database className="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {activeDataset.title}
            </h3>
            <p className="flex items-center text-sm text-gray-500 dark:text-gray-400">
              <FileText className="mr-1 h-4 w-4" />
              {activeDataset.filename}
            </p>
          </div>
        </div>
        <Badge color="success" size="sm">
          Active
        </Badge>
      </div>

      {/* Metrics Grid */}
      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="rounded-lg bg-gray-50 p-3 text-center dark:bg-gray-700">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {activeDataset.metrics.layers_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Layers
          </div>
        </div>
        <div className="rounded-lg bg-gray-50 p-3 text-center dark:bg-gray-700">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">
            {activeDataset.metrics.domains_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Domains
          </div>
        </div>
        <div className="rounded-lg bg-gray-50 p-3 text-center dark:bg-gray-700">
          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {activeDataset.metrics.terms_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Terms</div>
        </div>
        <div className="rounded-lg bg-gray-50 p-3 text-center dark:bg-gray-700">
          <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
            {activeDataset.metrics.relationships_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Relationships
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="mt-6 space-y-3 border-t border-gray-200 pt-6 dark:border-gray-700">
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Hash className="mr-2 h-4 w-4" />
            Dataset ID
          </span>
          <span className="font-mono text-xs text-gray-900 dark:text-white">
            {activeDataset.id}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Activity className="mr-2 h-4 w-4" />
            Schema Version
          </span>
          <Badge color="gray" size="sm">
            v{activeDataset.schema_version}
          </Badge>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Calendar className="mr-2 h-4 w-4" />
            Created
          </span>
          <span className="text-gray-900 dark:text-white">
            {formatDate(activeDataset.created_at)}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Clock className="mr-2 h-4 w-4" />
            Last Accessed
          </span>
          <span className="text-gray-900 dark:text-white">
            {formatDate(activeDataset.last_accessed)}
          </span>
        </div>
      </div>

      {/* Embedding Regeneration */}
      <div className="mt-6 space-y-3 border-t border-gray-200 pt-6 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white">
            Embedding Regeneration
          </h4>
          <div className="flex items-center space-x-2">
            {isEmbeddingRunning ? (
              <Button
                size="xs"
                color="failure"
                onClick={handleStopRegeneration}
              >
                <Square className="mr-1 h-3 w-3" />
                Stop
              </Button>
            ) : (
              <Button
                size="xs"
                onClick={() => handleStartRegeneration(true)}
                disabled={isEmbeddingRunning}
              >
                <RefreshCw className="mr-1 h-3 w-3" />
                Regenerate Embeddings
              </Button>
            )}
          </div>
        </div>

        {/* Status Display */}
        {isEmbeddingRunning && embeddingProgress && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
              <span>
                {embeddingProgress.completion_percentage.toFixed(1)}% Complete
              </span>
              <span>
                {embeddingProgress.completed_nodes} /{" "}
                {embeddingProgress.total_nodes} nodes
              </span>
            </div>
            <Progress
              progress={embeddingProgress.completion_percentage}
              size="sm"
              color="blue"
            />
            <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>
                {embeddingProgress.current_node_type}:{" "}
                {embeddingProgress.current_node_title}
              </span>
              <span>
                ETA: {Math.round(embeddingProgress.estimated_remaining_seconds)}
                s
              </span>
            </div>
            {embeddingProgress.error_count > 0 && (
              <div className="flex items-center text-xs text-red-600 dark:text-red-400">
                <AlertCircle className="mr-1 h-3 w-3" />
                {embeddingProgress.error_count} errors
              </div>
            )}
          </div>
        )}

        {/* Error Display */}
        {embeddingError && (
          <div className="flex items-center text-xs text-red-600 dark:text-red-400">
            <AlertCircle className="mr-1 h-3 w-3" />
            {embeddingError}
          </div>
        )}

        {/* Status Badge */}
        {embeddingStatus === "completed" && (
          <div className="text-center">
            <Badge color="success" size="sm">
              Embeddings Updated
            </Badge>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="mt-6 flex space-x-3 border-t border-gray-200 pt-6 dark:border-gray-700">
        <Link to="/app/datasets" className="flex-1">
          <Button size="sm" outline className="w-full">
            <Settings className="mr-2 h-4 w-4" />
            Explore Structure
          </Button>
        </Link>
        <Link to="/app" className="flex-1">
          <Button size="sm" className="w-full">
            <ChevronRight className="mr-2 h-4 w-4" />
            Explore Data
          </Button>
        </Link>
      </div>
    </Card>
  );
};

export default CurrentDatasetCard;
