/**
 * Predicate Set Selector Component
 * 
 * Multi-select interface for choosing multiple predicates
 */

import React, { useState, useMemo } from "react";
import { Button, Badge, TextInput, Spinner, Checkbox } from "flowbite-react";
import { ChevronDown, X, Search } from "lucide-react";
import { PredicateOut } from "@/api/services/predicates";
import { usePredicates } from "@/api/hooks/predicates";

export interface PredicateSetSelectorProps {
  value?: string[]; // Array of predicate IDs
  onSelectionChange: (predicateIds: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  maxSelections?: number; // Optional limit
}

export const PredicateSetSelector: React.FC<PredicateSetSelectorProps> = ({
  value = [],
  onSelectionChange,
  placeholder = "Select predicates...",
  disabled = false,
  maxSelections
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const { data: predicates, isLoading } = usePredicates();
  
  // Filter predicates based on search
  const filteredPredicates = useMemo(() => {
    if (!predicates?.data) return [];
    return predicates.data.filter(predicate =>
      predicate.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      predicate.identifier.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [predicates, searchTerm]);

  const handleTogglePredicate = (predicateId: string) => {
    const newSelection = value.includes(predicateId)
      ? value.filter(id => id !== predicateId)
      : [...value, predicateId];
    
    // Check max selections limit
    if (maxSelections && newSelection.length > maxSelections) {
      return; // Could show toast notification
    }
    
    onSelectionChange(newSelection);
  };

  const getPredicateById = (id: string): PredicateOut | undefined => {
    return predicates?.data?.find(p => p.id === id);
  };

  return (
    <div className="relative">
      {/* Dropdown Button */}
      <Button
        color="light"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        className="w-full justify-between"
      >
        <span>
          {value.length === 0 
            ? placeholder 
            : `${value.length} predicate${value.length !== 1 ? 's' : ''} selected`
          }
        </span>
        <ChevronDown className="h-4 w-4" />
      </Button>

      {/* Selected Items Pills */}
      {value.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {value.map(predicateId => {
            const predicate = getPredicateById(predicateId);
            return predicate ? (
              <Badge key={predicateId} className="flex items-center gap-1 py-1 px-2">
                {predicate.title}
                <X
                  className="h-3 w-3 ml-1 cursor-pointer hover:text-red-500 inline-flex"
                  onClick={() => handleTogglePredicate(predicateId)}
                />
              </Badge>
            ) : null;
          })}
        </div>
      )}

      {/* Dropdown Content */}
      {isOpen && (
        <div className="absolute z-10 mt-1 w-full bg-white border rounded-md shadow-lg dark:bg-gray-800 dark:border-gray-700">
          {/* Search Bar */}
          <div className="p-2 border-b dark:border-gray-700">
            <TextInput
              placeholder="Search predicates..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              icon={Search}
            />
          </div>
          
          {/* Predicate List */}
          <div className="max-h-60 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-center">
                <Spinner size="sm" />
              </div>
            ) : filteredPredicates.length === 0 ? (
              <div className="p-4 text-center text-gray-500 dark:text-gray-400">
                No predicates found
              </div>
            ) : (
              filteredPredicates.map(predicate => (
                <div
                  key={predicate.id}
                  className="flex items-center p-2 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                  onClick={() => handleTogglePredicate(predicate.id)}
                >
                  <Checkbox
                    checked={value.includes(predicate.id)}
                    onChange={() => handleTogglePredicate(predicate.id)}
                    className="mr-2"
                  />
                  <div className="flex-1">
                    <div className="font-medium">{predicate.title}</div>
                    {predicate.definition && (
                      <div className="text-sm text-gray-500 dark:text-gray-400 truncate">
                        {predicate.definition}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
