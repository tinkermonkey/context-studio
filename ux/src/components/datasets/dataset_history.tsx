/**
 * Dataset History Component
 *
 * Displays recent dataset activity log entries in the sidebar
 */

import React, { useState, useEffect } from "react";
import { useDatasetActionLog, type ActionLogEntry } from "@/api";
import {
  Clock,
  Database,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface DatasetHistoryProps {
  className?: string;
  maxEntries?: number;
  days?: number;
}

export function DatasetHistory({
  className = "",
  maxEntries = 10,
  days = 7,
}: DatasetHistoryProps) {
  const { data: actionLog, isLoading, error } = useDatasetActionLog(days);
  const [showAll, setShowAll] = useState(false);

  // State to trigger re-render every minute
  const [, setTick] = useState(0);
  React.useEffect(() => {
    const interval = setInterval(() => {
      setTick((t) => t + 1);
    }, 60000); // 1 minute
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center p-4 ${className}`}>
        <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
        <span className="ml-2 text-sm text-gray-500">Loading history...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="flex items-center text-red-500">
          <AlertCircle className="h-4 w-4" />
          <span className="ml-2 text-sm">Failed to load history</span>
        </div>
      </div>
    );
  }

  if (!actionLog?.entries?.length) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="flex items-center text-gray-500">
          <Database className="h-4 w-4" />
          <span className="ml-2 text-sm">No recent activity</span>
        </div>
      </div>
    );
  }

  // Get the entries to display based on showAll state
  const entriesToShow = showAll
    ? actionLog.entries
    : actionLog.entries.slice(0, maxEntries);
  const hasMoreEntries = actionLog.entries.length > maxEntries;

  return (
    <div className={`space-y-3 ${className}`}>
      {entriesToShow.map((entry, index) => (
        <DatasetHistoryEntry
          key={`${entry.dataset_id}-${entry.timestamp}-${index}`}
          entry={entry}
        />
      ))}

      {hasMoreEntries && (
        <div className="pt-2">
          <button
            onClick={() => setShowAll(!showAll)}
            className="flex w-full items-center justify-center space-x-1 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
          >
            {showAll ? (
              <>
                <ChevronUp className="h-3 w-3" />
                <span>Show less</span>
              </>
            ) : (
              <>
                <ChevronDown className="h-3 w-3" />
                <span>Show {actionLog.entries.length - maxEntries} more</span>
              </>
            )}
          </button>
          {!showAll && (
            <div className="mt-1 text-center">
              <span className="text-xs text-gray-500">
                Showing {maxEntries} of {actionLog.total_count} entries
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface DatasetHistoryEntryProps {
  entry: ActionLogEntry;
}

function DatasetHistoryEntry({ entry }: DatasetHistoryEntryProps) {
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor(
      (now.getTime() - date.getTime()) / (1000 * 60),
    );

    if (diffInMinutes < 1) return "Just now";
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
  };

  const getActionColor = (action: string) => {
    switch (action.toLowerCase()) {
      case "created":
      case "create":
        return "text-green-600 dark:text-green-400";
      case "activated":
      case "activate":
        return "text-blue-600 dark:text-blue-400";
      case "deleted":
      case "delete":
        return "text-red-600 dark:text-red-400";
      case "updated":
      case "update":
        return "text-orange-600 dark:text-orange-400";
      default:
        return "text-gray-600 dark:text-gray-400";
    }
  };

  const getActionIcon = (action: string) => {
    switch (action.toLowerCase()) {
      case "created":
      case "create":
        return <Database className="h-3 w-3" />;
      case "activated":
      case "activate":
        return <Clock className="h-3 w-3" />;
      case "deleted":
      case "delete":
        return <AlertCircle className="h-3 w-3" />;
      default:
        return <Database className="h-3 w-3" />;
    }
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-start space-x-2">
        <div className={`mt-0.5 ${getActionColor(entry.action)}`}>
          {getActionIcon(entry.action)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between">
            <span
              className={`text-sm font-medium capitalize ${getActionColor(entry.action)}`}
            >
              {entry.action}
            </span>
            <span className="text-xs text-gray-500">
              {formatTimestamp(entry.timestamp)}
            </span>
          </div>
          <div className="mt-1">
            <p className="truncate text-sm text-gray-900 dark:text-white">
              {entry.dataset_title || entry.dataset_id}
            </p>
          </div>
          {entry.details && Object.keys(entry.details).length > 0 && (
            <div className="mt-1">
              <span className="text-xs text-gray-500">
                {Object.keys(entry.details).join(", ")}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DatasetHistory;
