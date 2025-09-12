/**
 * Predicate Set Selector Component
 *
 * Multi-select interface for choosing multiple predicates
 */

import React from "react";
import { PredicateOut } from "@/api/services/predicates";
import { usePredicates } from "@/api/hooks/predicates";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";

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
  maxSelections,
}) => {
  const { data: predicates, isLoading } = usePredicates();

  return (
    <PortalRecordSelector
      records={predicates?.data ?? []}
      loading={isLoading}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      placeholder={placeholder}
      disabled={disabled}
      multi
      value={value}
      maxSelections={maxSelections}
      onSelectionChange={onSelectionChange}
    />
  );
};
