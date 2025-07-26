import React, { useState } from "react";
import { useLayers } from "@/api/hooks/layers";
import { Spinner, Button } from "flowbite-react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { components } from "@/api/client/types";

type LayerOut = components['schemas']['LayerOut'];

interface CollapsibleLayersListProps {
  showCount?: number;
  onLayerClick?: (layerId: string) => void;
  selectedLayerId?: string;
  useLinks?: boolean;
}

const CollapsibleLayersList: React.FC<CollapsibleLayersListProps> = ({ 
  showCount = 30,
  onLayerClick,
  selectedLayerId,
  useLinks = true,
}) => {
  const { data: layers, isLoading, error } = useLayers();
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (error) {
    console.error('Error loading layers:', error);
    return (
      <div className="text-sm text-red-600 dark:text-red-400 py-2">
        Error loading layers
      </div>
    );
  }

  if (!layers || layers.length === 0) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400 py-2">
        No layers found
      </div>
    );
  }

  // Sort layers alphabetically by title
  const sortedLayers = [...layers].sort((a, b) => a.title.localeCompare(b.title));
  
  const shouldShowExpandButton = sortedLayers.length > showCount;
  const displayedLayers = shouldShowExpandButton && !isExpanded 
    ? sortedLayers.slice(0, showCount)
    : sortedLayers;

  const handleToggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const handleLayerClick = (layerId: string) => {
    if (onLayerClick) {
      onLayerClick(layerId);
    }
  };

  return (
    <div className="space-y-1 mx-1">
      {displayedLayers.map((layer: LayerOut) => {
        const isSelected = selectedLayerId === layer.id;
        const className = `text-sm cursor-pointer px-2 py-1 rounded transition-colors block ${
          isSelected
            ? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 font-medium'
            : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800'
        }`;
        
        if (useLinks) {
          return (
            <Link
              key={layer.id}
              to="/app/domains"
              search={{ layer_id: layer.id }}
              className={className}
              title={layer.definition || layer.title}
            >
              {layer.title}
            </Link>
          );
        } else {
          return (
            <div
              key={layer.id}
              className={className}
              title={layer.definition || layer.title}
              onClick={() => handleLayerClick(layer.id)}
            >
              {layer.title}
            </div>
          );
        }
      })}
      
      {shouldShowExpandButton && (
        <Button
          size="xs"
          color={"light"}
          onClick={handleToggleExpanded}
          className="w-full mt-2 text-xs justify-start border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          <div className="flex items-center justify-center gap-1">
            {isExpanded ? (
              <>
                <ChevronUp size={12} />
                Show Less ({sortedLayers.length - showCount} hidden)
              </>
            ) : (
              <>
                <ChevronDown size={12} />
                Show All ({sortedLayers.length - showCount} more)
              </>
            )}
          </div>
        </Button>
      )}
    </div>
  );
};

export { CollapsibleLayersList };
