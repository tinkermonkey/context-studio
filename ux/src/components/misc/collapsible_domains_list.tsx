import React, { useState } from "react";
import { useDomains } from "@/api/hooks/domains";
import { Spinner, Button } from "flowbite-react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { components } from "@/api/client/types";

type DomainOut = components['schemas']['DomainOut'];

interface CollapsibleDomainsListProps {
  layerId: string;
  showCount?: number;
  onDomainClick?: (domainId: string) => void;
  selectedDomainId?: string;
  useLinks?: boolean;
}

const CollapsibleDomainsList: React.FC<CollapsibleDomainsListProps> = ({ 
  layerId,
  showCount = 20,
  onDomainClick,
  selectedDomainId,
  useLinks = true,
}) => {
  const { data: domains, isLoading, error } = useDomains({ layer_id: layerId });
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (error) {
    console.error('Error loading domains:', error);
    return (
      <div className="text-sm text-red-600 dark:text-red-400 py-2">
        Error loading domains
      </div>
    );
  }

  if (!domains || domains.length === 0) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400 py-2">
        No domains found
      </div>
    );
  }

  // Sort domains alphabetically by title
  const sortedDomains = [...domains].sort((a, b) => a.title.localeCompare(b.title));
  
  const shouldShowExpandButton = sortedDomains.length > showCount;
  const displayedDomains = shouldShowExpandButton && !isExpanded 
    ? sortedDomains.slice(0, showCount)
    : sortedDomains;

  const handleToggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const handleDomainClick = (domainId: string) => {
    if (onDomainClick) {
      onDomainClick(domainId);
    }
  };

  return (
    <div className="space-y-1 mx-1 mb-8">
      {displayedDomains.map((domain: DomainOut) => {
        const isSelected = selectedDomainId === domain.id;
        const className = `text-sm cursor-pointer px-2 py-1 rounded transition-colors block ${
          isSelected
            ? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 font-medium'
            : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800'
        }`;
        
        if (useLinks) {
          return (
            <Link
              key={domain.id}
              to="/app/terms"
              search={{ domain_id: domain.id }}
              className={className}
              title={domain.definition || domain.title}
            >
              {domain.title}
            </Link>
          );
        } else {
          return (
            <div
              key={domain.id}
              className={className}
              title={domain.definition || domain.title}
              onClick={() => handleDomainClick(domain.id)}
            >
              {domain.title}
            </div>
          );
        }
      })}
      
      {shouldShowExpandButton && (
        <Button
          size="xs"
          color={"light"}
          onClick={handleToggleExpanded}
          className="w-full mt-2 justify-start text-xs border-none text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          <div className="flex items-center justify-center gap-1">
            {isExpanded ? (
              <>
                <ChevronUp size={12} />
                Show Less ({sortedDomains.length - showCount} hidden)
              </>
            ) : (
              <>
                <ChevronDown size={12} />
                Show All ({sortedDomains.length - showCount} more)
              </>
            )}
          </div>
        </Button>
      )}
    </div>
  );
};

export { CollapsibleDomainsList };
