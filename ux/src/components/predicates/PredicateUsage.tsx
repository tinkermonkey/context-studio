/**
 * Predicate Usage Component
 *
 * Displays a single example of how a predicate is used in a knowledge graph.
 * Shows subject -> predicate -> object with links to the source.
 */

import React from "react";
import { Badge, Card } from "flowbite-react";
import { ExternalLink, ArrowRight } from "lucide-react";
import { PredicateExample } from "@/api/services/reference";
import { getSourceBadgeColor, getSourceUrl } from "@/utils/sourceUtils";

export interface PredicateUsageProps {
  example: PredicateExample;
}

export const PredicateUsage: React.FC<PredicateUsageProps> = ({ example }) => {
  const subjectUrl = getSourceUrl(
    example.subject.source,
    example.subject.external_id,
  );
  const objectUrl = getSourceUrl(
    example.object.source,
    example.object.external_id,
  );

  return (
    <Card className="mb-3">
      <div className="flex items-center gap-3">
        {/* Subject */}
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex items-center gap-2">
            <Badge
              color={getSourceBadgeColor(example.subject.source)}
              className="w-fit"
            >
              {example.subject.source}
            </Badge>
            {subjectUrl && (
              <a
                href={subjectUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline dark:text-blue-400"
                title="View in source"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <div className="font-medium text-gray-900 dark:text-white">
            {example.subject.title}
          </div>
          <div className="font-mono text-xs break-all text-gray-500 dark:text-gray-400">
            {example.subject.external_id}
          </div>
        </div>

        {/* Arrow */}
        <div className="flex flex-shrink-0 flex-col items-center gap-1">
          <ArrowRight className="h-5 w-5 text-gray-400" />
          <div className="max-w-[120px] text-center text-xs font-medium text-gray-600 dark:text-gray-300">
            {example.predicate.title}
          </div>
        </div>

        {/* Object */}
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex items-center gap-2">
            <Badge
              color={getSourceBadgeColor(example.object.source)}
              className="w-fit"
            >
              {example.object.source}
            </Badge>
            {objectUrl && (
              <a
                href={objectUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline dark:text-blue-400"
                title="View in source"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <div className="font-medium text-gray-900 dark:text-white">
            {example.object.title}
          </div>
          <div className="font-mono text-xs break-all text-gray-500 dark:text-gray-400">
            {example.object.external_id}
          </div>
        </div>
      </div>
    </Card>
  );
};
