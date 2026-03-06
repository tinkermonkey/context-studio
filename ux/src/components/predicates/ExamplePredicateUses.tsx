/**
 * Example Predicate Uses Component
 *
 * Displays example uses of a predicate from the reference database.
 * Shows how the predicate is used to connect subjects and objects
 * in the knowledge graph.
 */

import React from "react";
import { Alert, Badge, Spinner  } from "flowbite-react";;
import { AlertCircle, BookOpen } from "lucide-react";
import { usePredicateExamples } from "@/api/hooks/reference/useReference";
import { PredicateUsage } from "./PredicateUsage";
import { getSourceBadgeColor } from "@/utils/sourceUtils";

export interface ExamplePredicateUsesProps {
  source: string;
  externalId: string;
  limit?: number;
}

export const ExamplePredicateUses: React.FC<ExamplePredicateUsesProps> = ({
  source,
  externalId,
  limit = 10,
}) => {
  const { data, isLoading, error } = usePredicateExamples(
    source,
    externalId,
    limit,
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner size="lg" />
        <span className="ml-3">Loading examples...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Alert color="failure" icon={AlertCircle}>
        <span className="font-medium">Error loading examples:</span>{" "}
        {error.message}
      </Alert>
    );
  }

  if (!data || data.total_examples === 0) {
    return (
      <Alert color="info" icon={BookOpen}>
        <span className="font-medium">No examples found</span>
        <p className="mt-2 text-sm">
          This predicate doesn't have any recorded uses in the reference
          database yet.
        </p>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Predicate Info Header */}
      <div className="border-b pb-4 dark:border-gray-700">
        <div className="mb-2 flex items-center gap-2">
          <Badge
            color={getSourceBadgeColor(data.predicate.source)}
            className="w-fit"
          >
            {data.predicate.source}
          </Badge>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {data.predicate.title}
          </h3>
        </div>
        {data.predicate.definition && (
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {data.predicate.definition}
          </p>
        )}
        <p className="mt-2 font-mono text-xs text-gray-500 dark:text-gray-500">
          {data.predicate.external_id}
        </p>
      </div>

      {/* Examples Count */}
      <div className="text-sm text-gray-600 dark:text-gray-400">
        Showing {data.examples.length} example
        {data.examples.length !== 1 ? "s" : ""} of how this predicate is used:
      </div>

      {/* Examples List */}
      <div className="space-y-2">
        {data.examples.map((example) => (
          <PredicateUsage key={example.link_id} example={example} />
        ))}
      </div>

      {/* Footer note if there might be more */}
      {data.examples.length >= limit && (
        <p className="pt-2 text-center text-xs text-gray-500 dark:text-gray-500">
          Showing first {limit} examples. There may be more uses in the
          database.
        </p>
      )}
    </div>
  );
};
