/**
 * TestResultsViewer Component
 *
 * Displays pipeline test results in a sortable table with drill-down capabilities
 * and export functionality
 */

import React, { useState, useMemo } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  useReactTable,
  SortingState,
} from "@tanstack/react-table";
import { Button, Badge, Spinner } from "flowbite-react";
import { Download, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from "lucide-react";
import { usePipelineComparison } from "@/api/hooks/ragExperiments";
import { useButterToast } from "@/hooks/useButterToast";
import type { PipelineComparisonResponse } from "@/api/services/ragExperiments";
import type { components } from "@/api/client/types";

type PipelineComparisonItem = components["schemas"]["PipelineComparisonItem"];

export interface TestResultsViewerProps {
  paragraphId: string;
  pipelineNames?: string[];
}

const columnHelper = createColumnHelper<PipelineComparisonItem>();

export const TestResultsViewer: React.FC<TestResultsViewerProps> = ({
  paragraphId,
  pipelineNames,
}) => {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "f1_score", desc: true },
  ]);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const toast = useButterToast();

  const { data, isLoading, error } = usePipelineComparison({
    paragraphId,
    pipelineNames,
  });

  const results = data?.runs || [];
  const summary = data?.summary;

  const columns = useMemo(
    () => [
      columnHelper.accessor("pipeline_name", {
        header: "Pipeline Name",
        cell: (info) => (
          <span className="font-medium text-gray-900">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor("execution_time_ms", {
        header: "Execution Time (ms)",
        cell: (info) => (
          <span className="font-mono text-sm">
            {info.getValue()?.toFixed(2) || "N/A"}
          </span>
        ),
      }),
      columnHelper.accessor("entities_extracted", {
        header: "Entities Extracted",
        cell: (info) => (
          <span className="font-mono text-sm">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor("precision_score", {
        header: "Precision",
        cell: (info) => {
          const value = info.getValue();
          return value !== null && value !== undefined ? (
            <Badge color={value >= 0.8 ? "success" : value >= 0.6 ? "warning" : "failure"}>
              {(value * 100).toFixed(1)}%
            </Badge>
          ) : (
            <span className="text-gray-400">N/A</span>
          );
        },
      }),
      columnHelper.accessor("recall_score", {
        header: "Recall",
        cell: (info) => {
          const value = info.getValue();
          return value !== null && value !== undefined ? (
            <Badge color={value >= 0.8 ? "success" : value >= 0.6 ? "warning" : "failure"}>
              {(value * 100).toFixed(1)}%
            </Badge>
          ) : (
            <span className="text-gray-400">N/A</span>
          );
        },
      }),
      columnHelper.accessor("f1_score", {
        header: "F1 Score",
        cell: (info) => {
          const value = info.getValue();
          return value !== null && value !== undefined ? (
            <Badge color={value >= 0.8 ? "success" : value >= 0.6 ? "warning" : "failure"}>
              {(value * 100).toFixed(1)}%
            </Badge>
          ) : (
            <span className="text-gray-400">N/A</span>
          );
        },
      }),
      columnHelper.accessor("executed_at", {
        header: "Executed At",
        cell: (info) => (
          <span className="text-sm text-gray-600">
            {new Date(info.getValue()).toLocaleString()}
          </span>
        ),
      }),
    ],
    []
  );

  const table = useReactTable({
    data: results,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 10,
      },
    },
  });

  const handleExportCSV = () => {
    try {
      if (!results || results.length === 0) {
        toast.warning("No results to export");
        return;
      }

      // Build CSV content
      const headers = [
        "Pipeline Name",
        "Execution Time (ms)",
        "Entities Extracted",
        "Precision",
        "Recall",
        "F1 Score",
        "Executed At",
      ];
      const rows = results.map((result) => [
        result.pipeline_name,
        result.execution_time_ms?.toFixed(2) || "N/A",
        result.entities_extracted,
        result.precision_score !== null && result.precision_score !== undefined ? (result.precision_score * 100).toFixed(1) + "%" : "N/A",
        result.recall_score !== null && result.recall_score !== undefined ? (result.recall_score * 100).toFixed(1) + "%" : "N/A",
        result.f1_score !== null && result.f1_score !== undefined ? (result.f1_score * 100).toFixed(1) + "%" : "N/A",
        new Date(result.executed_at).toISOString(),
      ]);

      const csvContent = [
        headers.join(","),
        ...rows.map((row) => row.join(",")),
      ].join("\n");

      // Download CSV
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.setAttribute("href", url);
      link.setAttribute(
        "download",
        `rag_test_results_${paragraphId}_${new Date().toISOString()}.csv`
      );
      link.style.visibility = "hidden";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast.success("CSV exported successfully");
    } catch (error) {
      console.error("Failed to export CSV:", error);
      toast.error("Failed to export CSV. Please try again.");
    }
  };

  const handleExportJSON = () => {
    try {
      if (!data) {
        toast.warning("No data to export");
        return;
      }

      const jsonContent = JSON.stringify(data, null, 2);

      // Download JSON
      const blob = new Blob([jsonContent], { type: "application/json" });
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.setAttribute("href", url);
      link.setAttribute(
        "download",
        `rag_test_results_${paragraphId}_${new Date().toISOString()}.json`
      );
      link.style.visibility = "hidden";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast.success("JSON exported successfully");
    } catch (error) {
      console.error("Failed to export JSON:", error);
      toast.error("Failed to export JSON. Please try again.");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-8">
        <Spinner size="md" />
        <span className="text-gray-600">Loading test results...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-red-800">
        <p className="font-medium">Error Loading Results</p>
        <p className="text-sm">{error.message}</p>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center">
        <p className="text-gray-600">
          No test results available for this paragraph.
        </p>
        <p className="mt-2 text-sm text-gray-500">
          Run some pipeline tests to see results here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      {summary && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <h3 className="mb-2 text-lg font-medium text-blue-900">
            Results Summary
          </h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-blue-700">Total Pipelines</p>
              <p className="text-2xl font-bold text-blue-900">
                {summary.total_pipelines}
              </p>
            </div>
            <div>
              <p className="text-blue-700">Best Pipeline</p>
              <p className="font-medium text-blue-900">
                {summary.best_pipeline || "N/A"}
              </p>
            </div>
            <div>
              <p className="text-blue-700">Best F1 Score</p>
              <p className="text-2xl font-bold text-blue-900">
                {summary.best_f1_score !== null && summary.best_f1_score !== undefined
                  ? (summary.best_f1_score * 100).toFixed(1) + "%"
                  : "N/A"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Export Buttons */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Test Results</h3>
        <div className="flex gap-2">
          <Button size="sm" color="gray" onClick={handleExportCSV}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button size="sm" color="gray" onClick={handleExportJSON}>
            <Download className="mr-2 h-4 w-4" />
            Export JSON
          </Button>
        </div>
      </div>

      {/* Results Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className="cursor-pointer select-none px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-700 hover:bg-gray-100"
                  >
                    <div className="flex items-center gap-2">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {header.column.getIsSorted() ? (
                        header.column.getIsSorted() === "asc" ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )
                      ) : null}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="hover:bg-gray-50"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="whitespace-nowrap px-6 py-4">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {results.length > 10 && (
        <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-700">
              Page {table.getState().pagination.pageIndex + 1} of{" "}
              {table.getPageCount()}
            </span>
            <span className="text-sm text-gray-500">
              ({results.length} total results)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              color="gray"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              size="sm"
              color="gray"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              Next
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
