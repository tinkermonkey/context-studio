import React from "react";
import type { Taxonomy } from "@/api/types/ontology";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useTaxonomies } from "@/api/hooks/taxonomies";

export interface TaxonomySelectorProps {
  onSelect?: (taxonomy: Taxonomy | undefined) => void;
  value?: string;
  placeholder?: string;
  "data-testid"?: string;
}

export const TaxonomySelector: React.FC<TaxonomySelectorProps> = ({
  onSelect,
  value,
  placeholder,
  "data-testid": dataTestId,
}) => {
  const { data: taxonomies, isLoading, error } = useTaxonomies();
  return (
    <PortalRecordSelector
      records={taxonomies ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title" }}
      onSelect={(r) => onSelect && onSelect(r as Taxonomy | undefined)}
      value={value}
      placeholder={placeholder}
      data-testid={dataTestId}
    />
  );
};
