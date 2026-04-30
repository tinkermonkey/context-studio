import React, { useState } from "react";
import { useTaxonomies } from "@/api/hooks/taxonomies";
import { Spinner, Button } from "flowbite-react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { Taxonomy } from "@/api/types/ontology";

interface CollapsibleTaxonomiesListProps {
  showCount?: number;
  onTaxonomyClick?: (taxonomyId: string) => void;
  selectedTaxonomyId?: string;
  useLinks?: boolean;
}

const CollapsibleTaxonomiesList: React.FC<CollapsibleTaxonomiesListProps> = ({
  showCount = 30,
  onTaxonomyClick,
  selectedTaxonomyId,
  useLinks = true,
}) => {
  const { data: taxonomies, isLoading, error } = useTaxonomies();
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (error) {
    console.error("Error loading taxonomies:", error);
    return (
      <div className="py-2 text-sm text-red-600 dark:text-red-400">
        Error loading taxonomies
      </div>
    );
  }

  if (!taxonomies || taxonomies.length === 0) {
    return (
      <div className="py-2 text-sm text-gray-500 dark:text-gray-400">
        No taxonomies found
      </div>
    );
  }

  const sortedTaxonomies = [...taxonomies].sort((a, b) =>
    a.title.localeCompare(b.title),
  );

  const shouldShowExpandButton = sortedTaxonomies.length > showCount;
  const displayedTaxonomies =
    shouldShowExpandButton && !isExpanded
      ? sortedTaxonomies.slice(0, showCount)
      : sortedTaxonomies;

  const handleToggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const handleTaxonomyClick = (taxonomyId: string) => {
    if (onTaxonomyClick) {
      onTaxonomyClick(taxonomyId);
    }
  };

  return (
    <div className="mx-1 space-y-1">
      {displayedTaxonomies.map((taxonomy: Taxonomy) => {
        const isSelected = selectedTaxonomyId === taxonomy.id;
        const className = `${
          isSelected
            ? "bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 font-medium"
            : "text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800"
        }`;

        if (useLinks) {
          return (
            <Link
              key={taxonomy.id}
              to="/app/concept-schemes"
              search={{ taxonomy_id: taxonomy.id }}
              className={className}
              title={taxonomy.description || taxonomy.title}
            >
              {taxonomy.title}
            </Link>
          );
        } else {
          return (
            <div
              key={taxonomy.id}
              className={className}
              title={taxonomy.description || taxonomy.title}
              onClick={() => handleTaxonomyClick(taxonomy.id)}
            >
              {taxonomy.title}
            </div>
          );
        }
      })}

      {shouldShowExpandButton && (
        <Button
          size="xs"
          color={"light"}
          onClick={handleToggleExpanded}
          className="mt-2 w-full justify-start border-gray-300 text-xs text-gray-600 hover:text-gray-800 dark:border-gray-600 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <div className="flex items-center justify-center gap-1">
            {isExpanded ? (
              <>
                <ChevronUp size={12} />
                Show Less ({sortedTaxonomies.length - showCount} hidden)
              </>
            ) : (
              <>
                <ChevronDown size={12} />
                Show All ({sortedTaxonomies.length - showCount} more)
              </>
            )}
          </div>
        </Button>
      )}
    </div>
  );
};

export { CollapsibleTaxonomiesList };
