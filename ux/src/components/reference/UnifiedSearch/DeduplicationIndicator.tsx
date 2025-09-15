/**
 * DeduplicationIndicator Component
 *
 * Shows when a result has been merged from multiple sources due to deduplication
 */

import React, { useState } from 'react';
import { Badge, Tooltip } from 'flowbite-react';
import { Layers, Info } from 'lucide-react';
import { SOURCE_METADATA } from '@/api/types/unified';

interface DeduplicationIndicatorProps {
  mergedSources: string[];
  similarityScore: number;
  primarySource: string;
  showDetails?: boolean;
  size?: 'xs' | 'sm' | 'md';
}

export const DeduplicationIndicator: React.FC<DeduplicationIndicatorProps> = ({
  mergedSources,
  similarityScore,
  primarySource,
  showDetails = false,
  size = 'sm',
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  if (!mergedSources || mergedSources.length === 0) {
    return null;
  }

  const totalSources = mergedSources.length + 1; // +1 for primary source
  const confidencePercent = Math.round(similarityScore * 100);

  const getSourceLabel = (sourceName: string) => {
    return SOURCE_METADATA[sourceName]?.label || sourceName;
  };

  const tooltipContent = (
    <div className="max-w-sm space-y-2">
      <div className="font-semibold text-sm">Merged Result</div>
      <div className="text-xs space-y-1">
        <div>
          <span className="font-medium">Primary:</span> {getSourceLabel(primarySource)}
        </div>
        <div>
          <span className="font-medium">Also found in:</span>
        </div>
        <ul className="list-disc list-inside ml-2 space-y-0.5">
          {mergedSources.map(source => (
            <li key={source} className="text-xs">
              {getSourceLabel(source)}
            </li>
          ))}
        </ul>
        <div className="pt-1 border-t border-gray-200">
          <span className="font-medium">Similarity:</span> {confidencePercent}%
        </div>
      </div>
    </div>
  );

  if (showDetails) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-md p-2 space-y-2">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-blue-600" />
          <span className="text-sm font-medium text-blue-800">
            Merged from {totalSources} sources
          </span>
        </div>

        <div className="text-xs text-blue-700 space-y-1">
          <div>
            <span className="font-medium">Primary source:</span> {getSourceLabel(primarySource)}
          </div>
          <div>
            <span className="font-medium">Also found in:</span>
          </div>
          <div className="ml-2">
            {mergedSources.map((source, index) => (
              <span key={source}>
                {getSourceLabel(source)}
                {index < mergedSources.length - 1 && ', '}
              </span>
            ))}
          </div>
          <div className="pt-1">
            <span className="font-medium">Similarity confidence:</span> {confidencePercent}%
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <Tooltip
        content={tooltipContent}
        placement="top"
        style="light"
        arrow={false}
      >
        <Badge
          color="blue"
          size={size}
          className="cursor-help"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <div className="flex items-center gap-1">
            <Layers className="w-3 h-3" />
            <span>{totalSources} sources</span>
            {confidencePercent < 90 && (
              <Info className="w-3 h-3" />
            )}
          </div>
        </Badge>
      </Tooltip>
    </div>
  );
};

export default DeduplicationIndicator;