/**
 * SourceDropdown Component
 *
 * Simple dropdown for selecting which reference sources to search
 */

import React, { useState, useEffect } from "react";
import { Select } from "flowbite-react";
import { SOURCE_METADATA, SourceType } from "@/api/types/unified";

interface SourceDropdownProps {
  className?: string;
  selectedSources?: SourceType[];
  onSourcesChange?: (sources: SourceType[]) => void;
}

const DEFAULT_SOURCES: SourceType[] = [
  "conceptnet",
  "dbpedia",
  "wikidata",
  "schema_org",
];

export const SourceDropdown: React.FC<SourceDropdownProps> = ({
  className = "",
  selectedSources = DEFAULT_SOURCES,
  onSourcesChange,
}) => {
  const [dropdownValue, setDropdownValue] = useState("all");

  // Create dropdown options
  const getDropdownOptions = () => {
    const options = [
      { value: "all", label: "All Sources" },
    ];

    // Add individual source options
    DEFAULT_SOURCES.forEach((source) => {
      const meta = SOURCE_METADATA[source] || { label: source };
      options.push({ value: source, label: meta.label });
    });

    return options;
  };

  // Update dropdown value when selected sources change
  useEffect(() => {
    if (selectedSources.length === DEFAULT_SOURCES.length) {
      if (dropdownValue !== "all") {
        setDropdownValue("all");
      }
    } else if (selectedSources.length === 1) {
      if (dropdownValue !== selectedSources[0]) {
        setDropdownValue(selectedSources[0]);
      }
    } else if (selectedSources.length > 1) {
      if (dropdownValue !== "custom") {
        setDropdownValue("custom");
      }
    }
  }, [selectedSources, dropdownValue]);

  // Initialize with all sources on mount
  useEffect(() => {
    if (selectedSources.length === 0) {
      onSourcesChange?.(DEFAULT_SOURCES);
    }
  }, [selectedSources.length, onSourcesChange]);

  const handleDropdownChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setDropdownValue(value);

    if (value === "all") {
      onSourcesChange?.(DEFAULT_SOURCES);
    } else if (value === "custom") {
      // Don't change selection for custom - let user handle this
      return;
    } else {
      // Single source selection
      onSourcesChange?.([value as SourceType]);
    }
  };

  const options = getDropdownOptions();

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <Select
        id="source-select"
        value={dropdownValue}
        onChange={handleDropdownChange}
        disabled={false}
        className="min-w-40"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}

        {/* Show custom option if multiple but not all sources are selected */}
        {selectedSources.length > 1 &&
         selectedSources.length < DEFAULT_SOURCES.length && (
          <option value="custom">
            Custom ({selectedSources.length} sources)
          </option>
        )}
      </Select>
    </div>
  );
};

export default SourceDropdown;