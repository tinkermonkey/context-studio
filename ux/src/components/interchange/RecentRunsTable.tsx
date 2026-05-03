/**
 * Recent Runs Table
 *
 * Table displaying recent import runs with pagination
 */

import React from "react";
import { Button, Badge, Spinner } from "flowbite-react";
import { Link } from "@tanstack/react-router";
import { useInterchangeRuns } from "@/api/hooks/interchange";
import { ImportRunStatus, ImportRun } from "@/api/types/interchange";
import { Eye } from "lucide-react";

export function RecentRunsTable() {
  const [offset, setOffset] = React.useState(0);
  const limit = 10;

  const {
    data: runs = [],
    isLoading,
    error,
  } = useInterchangeRuns({
    offset,
    limit,
  });

  // Determine if there are more pages by checking if we got a full page of results
  const hasMorePages = runs.length === limit;
  const currentPage = Math.floor(offset / limit) + 1;

  const getStatusBadge = (status: ImportRunStatus) => {
    const colors: Record<ImportRunStatus, string> = {
      pending: "yellow",
      committed: "green",
      failed: "red",
      rolled_back: "gray",
    };
    return (
      <Badge color={colors[status] || "gray"}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  if (error) {
    return (
      <div className="rounded bg-red-50 p-4 text-red-900 dark:bg-red-950 dark:text-red-100">
        Error loading runs:{" "}
        {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="rounded bg-gray-50 p-4 text-gray-600 dark:bg-gray-900 dark:text-gray-400">
        No import runs yet. Start by importing a file.
      </div>
    );
  }

  return (
    <div data-testid="interchange-recent-runs-table" className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-gray-700 dark:text-gray-300">
          <thead className="bg-gray-100 dark:bg-gray-800">
            <tr>
              <th className="px-6 py-3 font-semibold">Format</th>
              <th className="px-6 py-3 font-semibold">Source</th>
              <th className="px-6 py-3 font-semibold">Date</th>
              <th className="px-6 py-3 font-semibold">Status</th>
              <th className="px-6 py-3 font-semibold">Entities Affected</th>
              <th className="px-6 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y border-t border-gray-200 dark:border-gray-700">
            {runs.map((run: ImportRun) => (
              <tr
                key={run.id}
                data-testid={`interchange-runs-table-row-${run.id}`}
                className="hover:bg-gray-50 dark:hover:bg-gray-900"
              >
                <td className="px-6 py-4 font-medium">
                  {run.format.toUpperCase()}
                </td>
                <td className="px-6 py-4">
                  {run.source_uri
                    ? (() => {
                        try {
                          return (
                            new URL(run.source_uri).pathname.split("/").pop() ||
                            run.source_uri
                          );
                        } catch {
                          // If source_uri is not a valid URL, extract filename using string methods
                          return (
                            run.source_uri.split("/").pop() || run.source_uri
                          );
                        }
                      })()
                    : "File"}
                </td>
                <td className="px-6 py-4">
                  {new Date(run.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4">{getStatusBadge(run.status)}</td>
                <td className="px-6 py-4">{run.affected_entity_ids.length}</td>
                <td className="px-6 py-4">
                  <Link
                    to="/app/interchange/runs/$runId"
                    params={{ runId: run.id }}
                    className="inline-block"
                  >
                    <Eye className="h-4 w-4 cursor-pointer text-blue-500 hover:text-blue-700" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {(offset > 0 || hasMorePages) && (
        <div className="mt-4 flex items-center justify-between">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Page {currentPage}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              disabled={!hasMorePages}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
