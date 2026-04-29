/**
 * ExecutionHistory Component
 *
 * Displays detailed execution timeline and audit trails for LLM operations
 * Shows token usage, performance data, and selection history for auditing
 */

import React, { useState, useMemo } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionPanel,
  AccordionTitle,
  Alert,
  Badge,
  Button,
  Card,
  Modal,
  Select,
  Spinner,
  TextInput,
} from "flowbite-react";
import {
  useExecutionHistory,
  useExecutionHistories,
  useFlavorExecutionHistory,
} from "@/api/hooks/llm/useLLMTraceability";
import type {
  ExecutionHistoryResponse,
  ExecutionDetails,
  SelectionRecord,
  ExecutionHistoryConfig,
  ExecutionHistoryFilters,
} from "@/api/types/traceability";

export interface ExecutionHistoryProps {
  /**
   * Specific execution ID to show details for (single execution mode)
   */
  executionId?: string;

  /**
   * Optional flavor ID for flavor-specific execution history
   */
  flavorId?: string;

  /**
   * Configuration options
   */
  config?: ExecutionHistoryConfig;

  /**
   * Custom CSS class name
   */
  className?: string;

  /**
   * Callback when execution is selected
   */
  onExecutionSelected?: (execution: ExecutionDetails) => void;

  /**
   * Whether to show filters in multi-execution mode
   * @default true
   */
  showFilters?: boolean;
}

/**
 * Status badge component for execution status
 */
const StatusBadge: React.FC<{ status: ExecutionDetails["status"] }> = ({
  status,
}) => {
  const color =
    status === "completed"
      ? "success"
      : status === "failed"
        ? "failure"
        : "warning";

  return (
    <Badge color={color} size="sm">
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
};

/**
 * Execution detail modal component
 */
const ExecutionDetailModal: React.FC<{
  execution: ExecutionDetails;
  selections: SelectionRecord[];
  isOpen: boolean;
  onClose: () => void;
}> = ({ execution, selections, isOpen, onClose }) => {
  return (
    <Modal show={isOpen} onClose={onClose} size="6xl">
      <div className="flex items-center justify-between rounded-t border-b p-4 md:p-5 dark:border-gray-600">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
          Execution Details: {execution.execution_id}
        </h3>
        <button
          type="button"
          className="ms-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-sm text-gray-400 hover:bg-gray-200 hover:text-gray-900 dark:hover:bg-gray-600 dark:hover:text-white"
          onClick={onClose}
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 14 14">
            <path
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"
            />
          </svg>
        </button>
      </div>
      <div className="max-h-[80vh] space-y-4 overflow-y-auto p-4 md:p-5">
        <div className="space-y-6">
          {/* Execution Overview */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <h4 className="text-sm font-medium text-gray-500">Status</h4>
              <StatusBadge status={execution.status} />
            </Card>
            <Card>
              <h4 className="text-sm font-medium text-gray-500">
                Execution Time
              </h4>
              <p className="text-lg font-semibold">
                {execution.execution_time}ms
              </p>
            </Card>
            <Card>
              <h4 className="text-sm font-medium text-gray-500">Tokens Used</h4>
              <p className="text-lg font-semibold">
                {execution.tokens_used.toLocaleString()}
              </p>
            </Card>
            <Card>
              <h4 className="text-sm font-medium text-gray-500">Pipeline</h4>
              <p className="text-lg font-semibold">{execution.pipeline_type}</p>
            </Card>
          </div>

          {/* Error Details - moved above accordion */}
          {execution.error_details && (
            <Alert color="failure">
              <div>
                <h4 className="mb-2 text-lg font-medium text-red-800 dark:text-red-400">
                  Error Details
                </h4>
                <pre className="text-sm whitespace-pre-wrap">
                  {execution.error_details}
                </pre>
              </div>
            </Alert>
          )}

          <Accordion>
            <AccordionPanel>
              <AccordionTitle>User Prompt</AccordionTitle>
              <AccordionContent>
                <div className="max-h-64 overflow-auto rounded bg-gray-100 p-4 font-mono text-sm dark:bg-gray-700">
                  <pre className="whitespace-pre-wrap text-gray-800 dark:text-gray-200">
                    {execution.user_prompt || "No user prompt available"}
                  </pre>
                </div>
              </AccordionContent>
            </AccordionPanel>

            <AccordionPanel>
              <AccordionTitle>LLM Response</AccordionTitle>
              <AccordionContent>
                <div className="max-h-64 overflow-auto rounded bg-gray-100 p-4 font-mono text-sm dark:bg-gray-700">
                  <pre className="whitespace-pre-wrap text-gray-800 dark:text-gray-200">
                    {execution.response_message ||
                      "No response message available"}
                  </pre>
                </div>
              </AccordionContent>
            </AccordionPanel>

            <AccordionPanel>
              <AccordionTitle>Input Data</AccordionTitle>
              <AccordionContent>
                <div className="max-h-64 overflow-auto rounded bg-gray-100 p-4 font-mono text-sm dark:bg-gray-700">
                  <pre className="text-gray-800 dark:text-gray-200">
                    {JSON.stringify(execution.input_data, null, 2)}
                  </pre>
                </div>
              </AccordionContent>
            </AccordionPanel>

            <AccordionPanel>
              <AccordionTitle>Output Data</AccordionTitle>
              <AccordionContent>
                <div className="max-h-64 overflow-auto rounded bg-gray-100 p-4 font-mono text-sm dark:bg-gray-700">
                  <pre className="text-gray-800 dark:text-gray-200">
                    {JSON.stringify(execution.output_data, null, 2)}
                  </pre>
                </div>
              </AccordionContent>
            </AccordionPanel>

            <AccordionPanel>
              <AccordionTitle>
                Selection History ({selections.length})
              </AccordionTitle>
              <AccordionContent>
                {selections.length > 0 ? (
                  <div className="relative overflow-x-auto">
                    <table className="w-full text-left text-sm text-gray-500 rtl:text-right dark:text-gray-400">
                      <thead className="bg-gray-50 text-xs text-gray-700 uppercase dark:bg-gray-700 dark:text-gray-400">
                        <tr>
                          <th scope="col" className="px-6 py-3">
                            Selection ID
                          </th>
                          <th scope="col" className="px-6 py-3">
                            Record ID
                          </th>
                          <th scope="col" className="px-6 py-3">
                            Field
                          </th>
                          <th scope="col" className="px-6 py-3">
                            Content Preview
                          </th>
                          <th scope="col" className="px-6 py-3">
                            Timestamp
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {selections.map((selection) => (
                          <tr
                            key={selection.selection_id}
                            className="border-b bg-white dark:border-gray-700 dark:bg-gray-800"
                          >
                            <td className="px-6 py-4 font-mono text-xs">
                              {selection.selection_id.substring(0, 8)}...
                            </td>
                            <td className="px-6 py-4 font-mono text-xs">
                              {selection.record_id}
                            </td>
                            <td className="px-6 py-4">
                              <Badge color="info" size="sm">
                                {selection.suggestion_field}
                              </Badge>
                            </td>
                            <td className="max-w-xs px-6 py-4">
                              <div
                                className="truncate"
                                title={selection.selected_content}
                              >
                                {selection.selected_content}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-500">
                              {new Date(selection.timestamp).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-gray-600 dark:text-gray-400">
                    No selection history available for this execution.
                  </p>
                )}
              </AccordionContent>
            </AccordionPanel>
          </Accordion>
        </div>
      </div>
      <div className="flex items-center rounded-b border-t border-gray-200 p-4 md:p-5 dark:border-gray-600">
        <Button color="gray" onClick={onClose}>
          Close
        </Button>
      </div>
    </Modal>
  );
};

/**
 * Main execution history component
 */
export const ExecutionHistory: React.FC<ExecutionHistoryProps> = ({
  executionId,
  flavorId,
  config = {},
  className = "",
  onExecutionSelected,
  showFilters = true,
}) => {
  const { maxEntries = 50, showFilters: configShowFilters = true } = config;

  // State for multi-execution mode
  const [filters, setFilters] = useState<ExecutionHistoryFilters>({
    limit: Math.min(maxEntries, 100),
  });
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedExecution, setSelectedExecution] =
    useState<ExecutionHistoryResponse | null>(null);

  // Single execution mode
  const {
    data: singleExecutionData,
    isLoading: singleExecutionLoading,
    error: singleExecutionError,
  } = useExecutionHistory(executionId || null);

  // Flavor-specific execution history
  const flavorHistoryFilters =
    flavorId && !executionId
      ? { flavor_id: flavorId, limit: filters.limit }
      : null;
  const {
    data: flavorExecutionData,
    isLoading: flavorExecutionLoading,
    error: flavorExecutionError,
    refetch: refetchFlavorExecutions,
  } = useFlavorExecutionHistory(flavorHistoryFilters);

  // Multi-execution mode (general) - disabled since API requires flavor_id
  const {
    data: multiExecutionData,
    isLoading: multiExecutionLoading,
    error: multiExecutionError,
    refetch: refetchGeneralExecutions,
  } = useExecutionHistories(null); // Always null - general execution history not supported by current API

  // Convert flavor execution data to match expected format
  const flavorExecutions = useMemo(() => {
    if (!flavorExecutionData?.executions) return [];

    // Convert flavor execution data to ExecutionHistoryResponse format
    // Map database fields to what the UI component expects
    return flavorExecutionData.executions.map((exec: any) => ({
      success: true,
      data: {
        execution: {
          execution_id: exec.id, // Database uses 'id', UI expects 'execution_id'
          pipeline_type: exec.pipeline_type,
          status: exec.status as "completed" | "failed" | "in_progress",
          execution_time: exec.execution_time_ms || 0,
          tokens_used: exec.total_tokens || 0,
          timestamp: exec.started_at,
          input_data: (() => {
            try {
              return exec.request_context
                ? JSON.parse(exec.request_context)
                : {};
            } catch {
              return { raw: exec.request_context };
            }
          })(),
          output_data: exec.response_message
            ? { message: exec.response_message }
            : {},
          error_details: exec.error_message || undefined,
          user_prompt: exec.user_prompt || undefined,
          response_message: exec.response_message || undefined,
        },
        selections: [], // Will be populated separately if needed
      },
    })) as ExecutionHistoryResponse[];
  }, [flavorExecutionData]);

  // Computed values
  const isLoading = executionId
    ? singleExecutionLoading
    : flavorId
      ? flavorExecutionLoading
      : multiExecutionLoading;

  const error = executionId
    ? singleExecutionError
    : flavorId
      ? flavorExecutionError
      : multiExecutionError;

  const executions = executionId
    ? singleExecutionData
      ? [singleExecutionData]
      : []
    : flavorId
      ? flavorExecutions
      : multiExecutionData || [];

  const refetchExecutions = flavorId
    ? refetchFlavorExecutions
    : refetchGeneralExecutions;

  // Filtered executions for search
  const filteredExecutions = useMemo(() => {
    if (!searchTerm) return executions;

    return executions.filter(
      (exec) =>
        exec.data.execution.execution_id
          .toLowerCase()
          .includes(searchTerm.toLowerCase()) ||
        exec.data.execution.pipeline_type
          .toLowerCase()
          .includes(searchTerm.toLowerCase()),
    );
  }, [executions, searchTerm]);

  // Handle execution row click
  const handleExecutionClick = (execution: ExecutionHistoryResponse) => {
    setSelectedExecution(execution);
    onExecutionSelected?.(execution.data.execution);
  };

  // Handle filter changes
  const handleStatusFilterChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    const status = event.target.value as ExecutionDetails["status"] | "";
    setFilters((prev) => ({
      ...prev,
      status: status || undefined,
    }));
  };

  const handlePipelineFilterChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    const pipelineType = event.target.value;
    setFilters((prev) => ({
      ...prev,
      pipeline_type: pipelineType || undefined,
    }));
  };

  // Get unique pipeline types for filter
  const uniquePipelineTypes = useMemo(() => {
    const types = executions.map((exec) => exec.data.execution.pipeline_type);
    return [...new Set(types)].sort();
  }, [executions]);

  return (
    <div className={`execution-history ${className}`.trim()}>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            {executionId
              ? "Execution Details"
              : flavorId
                ? "Flavor Execution History"
                : "Execution History"}
          </h2>
          <p className="mt-1 text-gray-600 dark:text-gray-400">
            {executionId
              ? `Detailed audit trail for execution ${executionId.substring(0, 8)}...`
              : flavorId
                ? `Execution history for flavor ${flavorId.substring(0, 8)}...`
                : "Detailed audit trails for LLM executions"}
          </p>
        </div>

        {!executionId && (
          <Button
            onClick={() => refetchExecutions()}
            disabled={isLoading}
            size="sm"
            color="gray"
          >
            {isLoading ? <Spinner size="sm" /> : "Refresh"}
          </Button>
        )}
      </div>

      {/* Filters (multi-execution mode only) */}
      {!executionId && showFilters && configShowFilters && (
        <Card className="mb-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <TextInput
              placeholder="Search by execution ID or pipeline..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />

            <Select
              value={filters.status || ""}
              onChange={handleStatusFilterChange}
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="in_progress">In Progress</option>
            </Select>

            <Select
              value={filters.pipeline_type || ""}
              onChange={handlePipelineFilterChange}
            >
              <option value="">All Pipelines</option>
              {uniquePipelineTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Select>

            <div className="flex items-center text-sm text-gray-500">
              {filteredExecutions.length} of {executions.length} executions
            </div>
          </div>
        </Card>
      )}

      {/* Error State */}
      {error && (
        <Alert color="failure" className="mb-6">
          <span className="font-medium">Failed to load execution history:</span>{" "}
          {error.message}
        </Alert>
      )}

      {/* Missing Flavor ID Alert */}
      {!executionId && !flavorId && (
        <Alert color="warning" className="mb-6">
          <span className="font-medium">Flavor ID Required:</span> Please
          provide a flavor ID to view execution history. General execution
          history is not currently supported by the API.
        </Alert>
      )}

      {/* Loading State */}
      {isLoading && executions.length === 0 && (
        <div className="flex justify-center py-12">
          <div className="text-center">
            <Spinner size="xl" />
            <p className="mt-4 text-gray-600 dark:text-gray-400">
              Loading execution history...
            </p>
          </div>
        </div>
      )}

      {/* Executions Table */}
      {filteredExecutions.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <div className="relative overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-500 rtl:text-right dark:text-gray-400">
                <thead className="bg-gray-50 text-xs text-gray-700 uppercase dark:bg-gray-700 dark:text-gray-400">
                  <tr>
                    <th scope="col" className="px-6 py-3">
                      Execution ID
                    </th>
                    <th scope="col" className="px-6 py-3">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3">
                      Pipeline
                    </th>
                    <th scope="col" className="px-6 py-3">
                      Execution Time
                    </th>
                    <th scope="col" className="px-6 py-3">
                      Tokens
                    </th>
                    <th scope="col" className="px-6 py-3">
                      Selections
                    </th>
                    <th scope="col" className="px-6 py-3">
                      Timestamp
                    </th>
                    <th scope="col" className="px-6 py-3">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredExecutions.map((executionResponse) => {
                    const execution = executionResponse.data.execution;
                    const selections = executionResponse.data.selections;

                    return (
                      <tr
                        key={execution.execution_id}
                        className="cursor-pointer border-b bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-800"
                        onClick={() => handleExecutionClick(executionResponse)}
                      >
                        <td className="px-6 py-4 font-mono text-sm">
                          {execution.execution_id.substring(0, 12)}...
                        </td>
                        <td className="px-6 py-4">
                          <StatusBadge status={execution.status} />
                        </td>
                        <td className="px-6 py-4">
                          <Badge color="info" size="sm">
                            {execution.pipeline_type}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 font-mono">
                          {execution.execution_time}ms
                        </td>
                        <td className="px-6 py-4 font-mono">
                          {execution.tokens_used.toLocaleString()}
                        </td>
                        <td className="px-6 py-4">
                          <Badge color="purple" size="sm">
                            {selections.length}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500">
                          {new Date(execution.timestamp).toLocaleString()}
                        </td>
                        <td className="px-6 py-4">
                          <Button
                            size="xs"
                            color="light"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExecutionClick(executionResponse);
                            }}
                          >
                            View Details
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </Card>
      )}

      {/* No Data State */}
      {!isLoading &&
        filteredExecutions.length === 0 &&
        executions.length === 0 && (
          <div className="py-12 text-center">
            <div className="mb-4 text-gray-400 dark:text-gray-600">
              <span className="text-6xl">📋</span>
            </div>
            <h3 className="mb-2 text-lg font-medium text-gray-900 dark:text-white">
              No Execution History
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {executionId
                ? "No execution found with the specified ID."
                : flavorId
                  ? "No LLM executions found for this flavor."
                  : "A flavor ID is required to view execution history."}
            </p>
          </div>
        )}

      {/* No Results State (with filters) */}
      {!isLoading &&
        filteredExecutions.length === 0 &&
        executions.length > 0 && (
          <div className="py-12 text-center">
            <div className="mb-4 text-gray-400 dark:text-gray-600">
              <span className="text-6xl">🔍</span>
            </div>
            <h3 className="mb-2 text-lg font-medium text-gray-900 dark:text-white">
              No Results Found
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              No executions match your current filters. Try adjusting your
              search criteria.
            </p>
          </div>
        )}

      {/* Execution Detail Modal */}
      {selectedExecution && (
        <ExecutionDetailModal
          execution={selectedExecution.data.execution}
          selections={selectedExecution.data.selections}
          isOpen={!!selectedExecution}
          onClose={() => setSelectedExecution(null)}
        />
      )}
    </div>
  );
};

export default ExecutionHistory;
