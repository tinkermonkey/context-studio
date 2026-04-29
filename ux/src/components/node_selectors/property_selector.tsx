/**
 * Property Selector Component
 *
 * Dropdown selector for choosing a single property definition
 */

import { PropertyDefinitionOut } from "@/api/services/propertyDefinitions";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { usePropertyDefinitions } from "@/api/hooks/propertyDefinitions";

export interface PropertySelectorProps {
  onSelect?: (property: PropertyDefinitionOut | undefined) => void;
  value?: string;
  placeholder?: string;
  disabled?: boolean;
}

export const PropertySelector: React.FC<PropertySelectorProps> = ({
  onSelect,
  value,
}) => {
  const { data: properties, isLoading, error } = usePropertyDefinitions();

  return (
    <PortalRecordSelector
      records={properties?.data ?? []}
      loading={isLoading}
      error={error ? "Failed to load properties" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as PropertyDefinitionOut | undefined)}
      value={value}
    />
  );
};
