/**
 * Recent Runs Table
 *
 * Table displaying recent import runs with pagination
 */

import React from "react";
import { Button, Badge, Spinner } from "flowbite-react";
import { Link } from "@tanstack/react-router";
import { useInterchangeRuns } from "@/api/hooks/interchange";
import { ImportRunStatus } from "@/api/types/interchange";
import { Eye } from "lucide-react";

export function RecentRunsTable() {
  const [offset, setOffset] = React.useState(0);
  const limit = 10;

  const { data: runs = [], isLoading, error } = useInterchangeRuns({
    offset,
    limit,
  });

  const totalPages = runs.length > 0 ? Math.ceil((runs[0] as any).total / limit) : 1;
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
      <div className="p-4 bg-red-50 dark:bg-red-950 text-red-900 dark:text-red-100 rounded">
        Error loading runs: {error instanceof Error ? error.message : "Unknown error"}
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
      <div className="p-4 bg-gray-50 dark:bg-gray-900 text-gray-600 dark:text-gray-400 rounded">
        No import runs yet. Start by importing a file.
      </div>
    );
  }

  return (
    <div data-testid="interchange-recent-runs-table" className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left text-gray-700 dark:text-gray-300">
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
            {runs.map((run: any) => (
              <tr
                key={run.id}
                data-testid={`interchange-runs-table-row-${run.id}`}
                className="hover:bg-gray-50 dark:hover:bg-gray-900"
              >
                <td className="px-6 py-4 font-medium">{run.format.toUpperCase()}</td>
                <td className="px-6 py-4">
                  {run.source_uri
                    ? new URL(run.source_uri).pathname.split("/").pop() || run.source_uri
                    : "File"}
                </td>
                <td className="px-6 py-4">
                  {new Date(run.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4">{getStatusBadge(run.status)}</td>
                <td className="px-6 py-4">{run.affected_entity_ids.length}</td>
                <td className="px-6 py-4">
                  <a href={`/app/interchange/runs/${run.id}`} className="inline-block">
                    <Eye className="h-4 w-4 text-blue-500 hover:text-blue-700 cursor-pointer" />
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Page {currentPage} of {totalPages}
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
              disabled={offset + limit >= (runs[0] as any)?.total}
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
