/**
 * Import Run Detail Page
 *
 * View details of a past import run
 */

import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { CsMainTitle } from "@/components/layout/cs_main";
import { Card, Button, Badge, Spinner } from "flowbite-react";
import {
  useInterchangeRun,
  useInterchangeRunChangeEvents,
} from "@/api/hooks/interchange";
import { ChangeEvent } from "@/api/types/interchange";
import { ChevronLeft } from "lucide-react";

export const Route = createFileRoute("/app/interchange/runs/$runId")({
  component: ImportRunDetailComponent,
});

function ImportRunDetailComponent() {
  const { runId } = Route.useParams();
  const [eventOffset, setEventOffset] = React.useState(0);
  const eventLimit = 20;

  const { data: run, isLoading: runLoading } = useInterchangeRun(runId);
  const { data: eventsData, isLoading: eventsLoading } =
    useInterchangeRunChangeEvents(runId, {
      offset: eventOffset,
      limit: eventLimit,
    });

  const changeEvents = Array.isArray(eventsData) ? eventsData : [];
  const hasMoreEvents = changeEvents.length === eventLimit;
  const currentPage = Math.floor(eventOffset / eventLimit) + 1;

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
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

  if (runLoading) {
    return <Spinner className="mx-auto my-8" />;
  }

  if (!run) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-950 text-red-900 dark:text-red-100 rounded">
        Import run not found
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center gap-2 mb-6">
        <Link
          to="/app/interchange"
          className="text-blue-500 hover:text-blue-700 flex items-center gap-1"
        >
          <ChevronLeft className="h-4 w-4" />
          Back
        </Link>
      </div>

      <CsMainTitle>Import Run Details</CsMainTitle>

      {/* Metadata section */}
      <Card data-testid="interchange-run-detail-metadata" className="mt-6">
        <h3 className="text-lg font-semibold mb-4">Run Information</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">ID</p>
            <p className="font-mono text-sm">{run.id}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">Format</p>
            <p className="font-semibold">{run.format.toUpperCase()}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Created At
            </p>
            <p className="text-sm">
              {new Date(run.created_at).toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">Status</p>
            <div className="mt-1">{getStatusBadge(run.status)}</div>
          </div>
          {run.created_by && (
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Created By
              </p>
              <p className="text-sm">{run.created_by}</p>
            </div>
          )}
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Scope Type
            </p>
            <p className="text-sm capitalize">{run.scope.scope_type}</p>
          </div>
        </div>
      </Card>

      {/* Affected entities section */}
      <Card
        data-testid="interchange-run-detail-entities"
        className="mt-6"
      >
        <h3 className="text-lg font-semibold mb-4">Affected Entities</h3>
        <div data-testid="interchange-run-affected-entities">
          {run.affected_entity_ids.length === 0 ? (
            <p className="text-gray-600 dark:text-gray-400">
              No entities were affected by this import
            </p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {run.affected_entity_ids.map((entityId: string) => (
                <div
                  key={entityId}
                  className="p-2 bg-gray-50 dark:bg-gray-900 rounded font-mono text-sm"
                >
                  {entityId}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Change events section */}
      <Card data-testid="interchange-run-detail-events" className="mt-6">
        <h3 className="text-lg font-semibold mb-4">Change Events</h3>

        {eventsLoading ? (
          <Spinner />
        ) : changeEvents.length === 0 ? (
          <p className="text-gray-600 dark:text-gray-400">
            No change events recorded
          </p>
        ) : (
          <>
            <div
              data-testid="interchange-run-change-events"
              className="overflow-x-auto"
            >
              <table className="w-full text-sm text-left text-gray-700 dark:text-gray-300">
                <thead className="bg-gray-100 dark:bg-gray-800">
                  <tr>
                    <th className="px-6 py-3 font-semibold">Timestamp</th>
                    <th className="px-6 py-3 font-semibold">Entity Type</th>
                    <th className="px-6 py-3 font-semibold">Change Type</th>
                    <th className="px-6 py-3 font-semibold">Entity ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y border-t border-gray-200 dark:border-gray-700">
                  {changeEvents.map((event: ChangeEvent) => (
                    <tr key={event.id} className="hover:bg-gray-50 dark:hover:bg-gray-900">
                      <td className="px-6 py-4">
                        {new Date(event.timestamp).toLocaleString()}
                      </td>
                      <td className="px-6 py-4">{event.entity_type}</td>
                      <td className="px-6 py-4">
                        <Badge color="blue">{event.change_type}</Badge>
                      </td>
                      <td className="px-6 py-4 font-mono text-sm">
                        {event.entity_id}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {(eventOffset > 0 || hasMoreEvents) && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Page {currentPage}
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={eventOffset === 0}
                    onClick={() =>
                      setEventOffset(Math.max(0, eventOffset - eventLimit))
                    }
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    disabled={!hasMoreEvents}
                    onClick={() => setEventOffset(eventOffset + eventLimit)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {/* Undo button (placeholder) */}
      <div className="mt-6">
        <Button
          data-testid="interchange-run-undo-button"
          disabled
          color="gray"
          outline
        >
          Undo This Run (Not Yet Implemented)
        </Button>
      </div>
    </>
  );
}
