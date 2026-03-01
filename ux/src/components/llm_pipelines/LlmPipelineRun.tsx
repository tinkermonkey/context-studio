import React, { useState, useCallback, ReactNode } from "react";
import { Button, Card, Alert, Spinner, Badge } from "flowbite-react";
import { Play, Zap, CheckCircle, XCircle, Clock } from "lucide-react";
import {
  usePipelineFlavors,
  usePipelineFlavor,
} from "@/api/hooks/pipelineFlavors";
import {
  useSuggestTermDefinitionMutation,
  useSuggestDomainDefinitionMutation,
  useSuggestLayerDefinitionMutation,
} from "@/api/hooks/llm";
import type {
  PipelineType,
  DefinitionSuggestionResponse,
  DomainDefinitionResponse,
  LayerDefinitionResponse,
} from "@/api";

// Types for pipeline execution results
interface PipelineResult {
  flavorId: string;
  flavorTitle: string;
  status: "pending" | "running" | "success" | "error";
  data?:
    | DefinitionSuggestionResponse
    | DomainDefinitionResponse
    | LayerDefinitionResponse;
  error?: string;
  startTime?: number;
  endTime?: number;
}

interface LlmPipelineRunProps {
  /** Pipeline identifier (e.g., 'suggest_term_definition') */
  pipelineType: PipelineType;

  /** JSON blob of context properties for the pipeline */
  context: Record<string, any>;

  /** Optional list of specific flavor IDs to use instead of enabled flavors */
  flavorList?: string[] | null;

  /** Optional custom template to render pipeline results */
  resultTemplate?: (result: PipelineResult) => ReactNode;

  /** Called when pipeline execution is triggered */
  onExecutionStart?: () => void;

  /** Called when all pipelines complete (success or error) */
  onExecutionComplete?: (results: PipelineResult[]) => void;

  /** Called when a single flavor completes */
  onFlavorComplete?: (result: PipelineResult) => void;

  /** Custom className for styling */
  className?: string;

  /** Whether to show execution timing */
  showTiming?: boolean;

  /** Whether to auto-execute on mount (default: false) */
  autoExecute?: boolean;
}

export const LlmPipelineRun: React.FC<LlmPipelineRunProps> = ({
  pipelineType,
  context,
  flavorList = null,
  resultTemplate,
  onExecutionStart,
  onExecutionComplete,
  onFlavorComplete,
  className = "",
  showTiming = false,
  autoExecute = false,
}) => {
  const [results, setResults] = useState<PipelineResult[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionError, setExecutionError] = useState<string | null>(null);

  // Fetch all flavors for pipeline type (always fetch this)
  const {
    data: flavorsResponse,
    isLoading: flavorsLoading,
    error: flavorsError,
  } = usePipelineFlavors({ pipeline: pipelineType });

  // Conditionally fetch specific flavor when we have exactly one in the list
  const specificFlavorId =
    flavorList && flavorList.length === 1 ? flavorList[0] : "";
  const {
    data: specificFlavor,
    isLoading: specificFlavorLoading,
    error: specificFlavorError,
  } = usePipelineFlavor(specificFlavorId);

  // Pipeline mutation hooks
  const termMutation = useSuggestTermDefinitionMutation();
  const domainMutation = useSuggestDomainDefinitionMutation();
  const layerMutation = useSuggestLayerDefinitionMutation();

  // Get enabled flavors or use provided flavorList
  const enabledFlavors = React.useMemo(() => {
    if (flavorList && flavorList.length > 0) {
      if (flavorList.length === 1 && specificFlavor) {
        // Use the specific flavor we fetched directly by ID
        return [specificFlavor];
      } else {
        // Use provided flavorList - filter from all available flavors
        const allFlavors = flavorsResponse?.flavors || [];
        const filtered = allFlavors.filter((flavor) =>
          flavorList.includes(flavor.id),
        );
        return filtered;
      }
    }
    // Fall back to enabled flavors when no flavorList is provided
    const enabledOnly =
      flavorsResponse?.flavors?.filter((flavor) => flavor.enabled) || [];
    return enabledOnly;
  }, [flavorList, flavorsResponse?.flavors, specificFlavor]);

  // Function to execute a specific pipeline for a flavor
  const executePipelineForFlavor = useCallback(
    async (flavorId: string, flavorTitle: string): Promise<PipelineResult> => {
      const startTime = Date.now();

      try {
        let data: any;

        // Construct the new generic pipeline execution request format
        const pipelineRequest = {
          pipeline_type: pipelineType,
          flavor_id: flavorId,
          context_data: context,
        };

        switch (pipelineType) {
          case "suggest_term_definition":
            data = await termMutation.mutateAsync(pipelineRequest as any);
            break;
          case "suggest_domain_definition":
            data = await domainMutation.mutateAsync(pipelineRequest as any);
            break;
          case "suggest_layer_definition":
            data = await layerMutation.mutateAsync(pipelineRequest as any);
            break;
          default:
            throw new Error(`Unsupported pipeline type: ${pipelineType}`);
        }

        const endTime = Date.now();
        return {
          flavorId,
          flavorTitle,
          status: "success",
          data,
          startTime,
          endTime,
        };
      } catch (error) {
        const endTime = Date.now();
        return {
          flavorId,
          flavorTitle,
          status: "error",
          error: error instanceof Error ? error.message : "Unknown error",
          startTime,
          endTime,
        };
      }
    },
    [pipelineType, context, termMutation, domainMutation, layerMutation],
  );

  // Function to execute all enabled flavors in parallel
  const executePipelines = useCallback(async () => {
    if (enabledFlavors.length === 0) {
      const errorMessage =
        flavorList && flavorList.length > 0
          ? "No flavors found matching the provided flavor list for this pipeline type"
          : "No enabled flavors found for this pipeline type";
      setExecutionError(errorMessage);
      return;
    }

    setIsExecuting(true);
    setExecutionError(null);
    onExecutionStart?.();

    // Initialize results with pending status
    const initialResults: PipelineResult[] = enabledFlavors.map((flavor) => ({
      flavorId: flavor.id,
      flavorTitle: flavor.title,
      status: "pending",
    }));
    setResults(initialResults);

    try {
      // Execute all flavors in parallel
      const promises = enabledFlavors.map(async (flavor, index) => {
        // Update status to running
        setResults((prev) =>
          prev.map((result, i) =>
            i === index ? { ...result, status: "running" as const } : result,
          ),
        );

        const result = await executePipelineForFlavor(flavor.id, flavor.title);

        // Update individual result
        setResults((prev) => prev.map((r, i) => (i === index ? result : r)));

        // Call flavor complete callback
        onFlavorComplete?.(result);

        return result;
      });

      const completedResults = await Promise.all(promises);

      // Call execution complete callback
      onExecutionComplete?.(completedResults);
    } catch (error) {
      setExecutionError(
        error instanceof Error ? error.message : "Pipeline execution failed",
      );
    } finally {
      setIsExecuting(false);
    }
  }, [
    enabledFlavors,
    executePipelineForFlavor,
    onExecutionStart,
    onExecutionComplete,
    onFlavorComplete,
    flavorList,
  ]);

  // Auto-execute on mount if requested
  React.useEffect(() => {
    if (
      autoExecute &&
      enabledFlavors.length > 0 &&
      !isExecuting &&
      results.length === 0
    ) {
      executePipelines();
    }
  }, [
    autoExecute,
    enabledFlavors.length,
    isExecuting,
    results.length,
    executePipelines,
  ]);

  // Function to get status icon
  const getStatusIcon = (status: PipelineResult["status"]) => {
    switch (status) {
      case "pending":
        return <Clock className="h-4 w-4 text-gray-400" />;
      case "running":
        return <Spinner size="sm" />;
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />;
    }
  };

  // Function to get status color
  const getStatusColor = (status: PipelineResult["status"]) => {
    switch (status) {
      case "pending":
        return "gray";
      case "running":
        return "yellow";
      case "success":
        return "green";
      case "error":
        return "red";
    }
  };

  // Function to format execution time
  const formatExecutionTime = (result: PipelineResult) => {
    if (!result.startTime || !result.endTime) return null;
    const duration = result.endTime - result.startTime;
    return `${duration}ms`;
  };

  // Default result template
  const defaultResultTemplate = (result: PipelineResult) => {
    if (result.status === "success" && result.data) {
      const data = result.data as any;
      return (
        <div className="space-y-3">
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
            <h5 className="mb-2 font-medium text-gray-900 dark:text-white">
              Definition
            </h5>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {data.definition}
            </p>
          </div>

          {data.reasoning && (
            <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
              <h5 className="mb-2 font-medium text-blue-900 dark:text-blue-200">
                Reasoning
              </h5>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                {data.reasoning}
              </p>
            </div>
          )}

          {data.discrepancies && (
            <div className="rounded-lg bg-yellow-50 p-3 dark:bg-yellow-900/20">
              <h5 className="mb-2 font-medium text-yellow-900 dark:text-yellow-200">
                Discrepancies
              </h5>
              <p className="text-sm text-yellow-700 dark:text-yellow-300">
                {data.discrepancies}
              </p>
            </div>
          )}
        </div>
      );
    }

    if (result.status === "error") {
      return (
        <Alert color="failure">
          <div>
            <h5 className="mb-1 font-medium">Execution Error</h5>
            <p className="text-sm">{result.error}</p>
          </div>
        </Alert>
      );
    }

    return (
      <div className="flex items-center justify-center p-8 text-gray-500 dark:text-gray-400">
        {result.status === "running"
          ? "Executing pipeline..."
          : "Waiting to execute..."}
      </div>
    );
  };

  const isLoading =
    flavorsLoading || (specificFlavorId && specificFlavorLoading);
  const loadingError =
    flavorsError || (specificFlavorId && specificFlavorError);

  if (isLoading) {
    return (
      <div className={"w-full" + className}>
        <div className="flex items-center gap-3 p-4">
          <Spinner size="sm" />
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Loading pipeline flavors...
          </span>
        </div>
      </div>
    );
  }

  if (loadingError) {
    return (
      <div className={"w-full" + className}>
        <Alert color="failure">
          <div>
            <h4 className="mb-2 font-medium">
              Failed to Load Pipeline Flavors
            </h4>
            <p>
              {loadingError instanceof Error
                ? loadingError.message
                : "Unknown error"}
            </p>
          </div>
        </Alert>
      </div>
    );
  }

  if (enabledFlavors.length === 0) {
    const warningMessage =
      flavorList && flavorList.length > 0
        ? `No flavors found matching the provided flavor list for pipeline type: ${pipelineType}`
        : `No enabled flavors found for pipeline type: ${pipelineType}`;

    return (
      <div className={"w-full" + className}>
        <Alert color="warning">
          <div>
            <h4 className="mb-2 font-medium">
              {flavorList && flavorList.length > 0
                ? "No Matching Flavors"
                : "No Enabled Flavors"}
            </h4>
            <p>{warningMessage}</p>
          </div>
        </Alert>
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Execution Controls */}
      <div className={"w-full" + className}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {pipelineType
                .replace(/_/g, " ")
                .replace(/\b\w/g, (l) => l.toUpperCase())}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {enabledFlavors.length}{" "}
              {flavorList && flavorList.length > 0 ? "selected" : "enabled"}{" "}
              flavor
              {enabledFlavors.length !== 1 ? "s" : ""}
            </p>
          </div>

          <Button
            onClick={executePipelines}
            disabled={isExecuting || enabledFlavors.length === 0}
            color="blue"
            size="sm"
          >
            {isExecuting ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            {isExecuting ? "Executing..." : "Execute Pipeline"}
          </Button>
        </div>
      </div>

      {/* Execution Error */}
      {executionError && (
        <Alert color="failure">
          <div>
            <h4 className="mb-2 font-medium">Execution Error</h4>
            <p>{executionError}</p>
          </div>
        </Alert>
      )}

      {/* Results Grid */}
      {results.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {results.map((result) => (
            <div
              key={result.flavorId}
              className="flex flex-col rounded-lg border border-gray-200 bg-white p-2 shadow-md dark:border-gray-700 dark:bg-gray-800"
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getStatusIcon(result.status)}
                  <h4 className="font-medium text-gray-900 dark:text-white">
                    {result.flavorTitle}
                  </h4>
                </div>
                <Badge color={getStatusColor(result.status)} size="sm">
                  {result.status}
                </Badge>
              </div>

              {showTiming && result.startTime && result.endTime && (
                <div className="mb-3 text-xs text-gray-500 dark:text-gray-400">
                  Execution time: {formatExecutionTime(result)}
                </div>
              )}

              {resultTemplate
                ? resultTemplate(result)
                : defaultResultTemplate(result)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
