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
  const subjectUrl = getSourceUrl(example.subject.source, example.subject.external_id);
  const objectUrl = getSourceUrl(example.object.source, example.object.external_id);
  
  return (
    <Card className="mb-3">
      <div className="flex items-center gap-3">
        {/* Subject */}
        <div className="flex flex-col gap-1 flex-1">
          <div className="flex items-center gap-2">
            <Badge color={getSourceBadgeColor(example.subject.source)} className="w-fit">
              {example.subject.source}
            </Badge>
            {subjectUrl && (
              <a
                href={subjectUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline dark:text-blue-400 inline-flex items-center gap-1"
                title="View in source"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <div className="font-medium text-gray-900 dark:text-white">
            {example.subject.title}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400 font-mono break-all">
            {example.subject.external_id}
          </div>
        </div>
        
        {/* Arrow */}
        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <ArrowRight className="h-5 w-5 text-gray-400" />
          <div className="text-xs font-medium text-gray-600 dark:text-gray-300 text-center max-w-[120px]">
            {example.predicate.title}
          </div>
        </div>
        
        {/* Object */}
        <div className="flex flex-col gap-1 flex-1">
          <div className="flex items-center gap-2">
            <Badge color={getSourceBadgeColor(example.object.source)} className="w-fit">
              {example.object.source}
            </Badge>
            {objectUrl && (
              <a
                href={objectUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline dark:text-blue-400 inline-flex items-center gap-1"
                title="View in source"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <div className="font-medium text-gray-900 dark:text-white">
            {example.object.title}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400 font-mono break-all">
            {example.object.external_id}
          </div>
        </div>
      </div>
    </Card>
  );
};
