/**
 * SourceSelector Component
 *
 * Dropdown selector for reference sources with checkboxes
 */

import React, { useState, useRef, useEffect } from "react";
import { Checkbox, Label, Button } from "flowbite-react";
import { ChevronDown, Filter } from "lucide-react";
import { SOURCE_METADATA, SourceType } from "@/api/types/unified";

interface SourceSelectorProps {
  selectedSources: SourceType[];
  onSourcesChange: (sources: SourceType[]) => void;
  disabled?: boolean;
  "data-testid"?: string;
}

const ALL_SOURCES: SourceType[] = [
  "conceptnet",
  "dbpedia",
  "wikidata",
  "schema_org",
];

export const SourceSelector: React.FC<SourceSelectorProps> = ({
  selectedSources,
  onSourcesChange,
  disabled = false,
  "data-testid": dataTestId,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const handleSourceToggle = (source: SourceType) => {
    if (selectedSources.includes(source)) {
      onSourcesChange(selectedSources.filter((s) => s !== source));
    } else {
      onSourcesChange([...selectedSources, source]);
    }
  };

  const handleSelectAll = () => {
    if (selectedSources.length === ALL_SOURCES.length) {
      onSourcesChange([]);
    } else {
      onSourcesChange(ALL_SOURCES);
    }
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const allSelected = selectedSources.length === ALL_SOURCES.length;
  const noneSelected = selectedSources.length === 0;

  const getButtonText = () => {
    if (noneSelected) return "Select Sources";
    if (allSelected) return "All Sources";
    return `${selectedSources.length} Sources`;
  };

  const getButtonColor = () => {
    if (noneSelected) return "failure";
    return "gray";
  };

  return (
    <div className="relative" ref={dropdownRef} data-testid={dataTestId}>
      <Button
        color={getButtonColor()}
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        className="flex items-center gap-2"
      >
        <Filter className="h-4 w-4" />
        {getButtonText()}
        <ChevronDown
          className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </Button>

      {isOpen && (
        <div className="absolute top-full left-0 z-50 mt-1 w-64 rounded-lg border border-gray-200 bg-white shadow-lg">
          <div className="space-y-3 p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-900">
                Reference Sources
              </h3>
              <button
                onClick={handleSelectAll}
                disabled={disabled}
                className="text-xs text-blue-600 hover:text-blue-500 disabled:text-gray-400"
              >
                {allSelected ? "Clear All" : "Select All"}
              </button>
            </div>

            {noneSelected && (
              <p className="text-xs text-red-600">
                Please select at least one source
              </p>
            )}

            <div className="space-y-2">
              {ALL_SOURCES.map((source) => {
                const metadata = SOURCE_METADATA[source];
                const isSelected = selectedSources.includes(source);

                return (
                  <div key={source} className="flex items-center gap-2">
                    <Checkbox
                      id={`source-${source}`}
                      checked={isSelected}
                      onChange={() => handleSourceToggle(source)}
                      disabled={disabled}
                    />
                    <Label
                      htmlFor={`source-${source}`}
                      className="flex cursor-pointer items-center gap-2 text-sm"
                    >
                      <span
                        className={`inline-block h-2 w-2 rounded-full bg-${metadata.color}-500`}
                      />
                      {metadata.label}
                    </Label>
                  </div>
                );
              })}
            </div>

            <div className="border-t border-gray-100 pt-2 text-xs text-gray-500">
              {selectedSources.length} of {ALL_SOURCES.length} sources selected
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SourceSelector;
