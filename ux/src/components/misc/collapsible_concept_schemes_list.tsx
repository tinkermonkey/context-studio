import React, { useState } from "react";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes";
import { Spinner, Button } from "flowbite-react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { StructureNode } from "@/api/types/structureNodes";

interface CollapsibleConceptSchemesListProps {
  taxonomyId: string;
  showCount?: number;
  onConceptSchemeClick?: (conceptSchemeId: string) => void;
  selectedConceptSchemeId?: string;
  useLinks?: boolean;
}

const CollapsibleConceptSchemesList: React.FC<CollapsibleConceptSchemesListProps> = ({
  taxonomyId,
  showCount = 20,
  onConceptSchemeClick,
  selectedConceptSchemeId,
  useLinks = true,
}) => {
  const { data: conceptSchemes, isLoading, error } = useConceptSchemes(taxonomyId);
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (error) {
    console.error("Error loading concept schemes:", error);
    return (
      <div className="py-2 text-sm text-red-600 dark:text-red-400">
        Error loading concept schemes
      </div>
    );
  }

  if (!conceptSchemes || conceptSchemes.length === 0) {
    return (
      <div className="py-2 text-sm text-gray-500 dark:text-gray-400">
        No concept schemes found
      </div>
    );
  }

  const sortedConceptSchemes = [...conceptSchemes].sort((a, b) =>
    a.title.localeCompare(b.title),
  );

  const shouldShowExpandButton = sortedConceptSchemes.length > showCount;
  const displayedConceptSchemes =
    shouldShowExpandButton && !isExpanded
      ? sortedConceptSchemes.slice(0, showCount)
      : sortedConceptSchemes;

  const handleToggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const handleConceptSchemeClick = (conceptSchemeId: string) => {
    if (onConceptSchemeClick) {
      onConceptSchemeClick(conceptSchemeId);
    }
  };

  return (
    <div className="mx-1 mb-8 space-y-1">
      {displayedConceptSchemes.map((conceptScheme: StructureNode) => {
        const isSelected = selectedConceptSchemeId === conceptScheme.id;
        const className = `${
          isSelected
            ? "bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 font-medium"
            : "text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800"
        }`;

        if (useLinks) {
          return (
            <Link
              key={conceptScheme.id}
              to="/app/classes"
              search={{ concept_scheme_id: conceptScheme.id }}
              className={className}
              title={conceptScheme.definition || conceptScheme.title}
            >
              {conceptScheme.title}
            </Link>
          );
        } else {
          return (
            <div
              key={conceptScheme.id}
              className={className}
              title={conceptScheme.definition || conceptScheme.title}
              onClick={() => handleConceptSchemeClick(conceptScheme.id)}
            >
              {conceptScheme.title}
            </div>
          );
        }
      })}

      {shouldShowExpandButton && (
        <Button
          size="xs"
          color={"light"}
          onClick={handleToggleExpanded}
          className="mt-2 w-full justify-start border-none text-xs text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <div className="flex items-center justify-center gap-1">
            {isExpanded ? (
              <>
                <ChevronUp size={12} />
                Show Less ({sortedConceptSchemes.length - showCount} hidden)
              </>
            ) : (
              <>
                <ChevronDown size={12} />
                Show All ({sortedConceptSchemes.length - showCount} more)
              </>
            )}
          </div>
        </Button>
      )}
    </div>
  );
};

export { CollapsibleConceptSchemesList };
