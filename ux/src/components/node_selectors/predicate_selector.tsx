/**
 * Predicate Selector Component
 *
 * Dropdown selector for choosing a single predicate
 */

import { PredicateOut } from "@/api/services/predicates";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { usePredicates } from "@/api/hooks/predicates";

export interface PredicateSelectorProps {
  onSelect?: (predicate: PredicateOut | undefined) => void;
  value?: string;
  placeholder?: string;
  disabled?: boolean;
}

export const PredicateSelector: React.FC<PredicateSelectorProps> = ({
  onSelect,
  value,
  placeholder = "Select predicate...",
  disabled = false,
}) => {
  const { data: predicates, isLoading, error } = usePredicates();

  return (
    <PortalRecordSelector
      records={predicates?.data ?? []}
      loading={isLoading}
      error={error ? "Failed to load predicates" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as PredicateOut | undefined)}
      value={value}
    />
  );
};
