import { useState, useMemo } from "react";
import { EntityPicker, Button } from "@tinkermonkey/heimdall-ui";
import { useEntityTypeQuery } from "@/api/hooks/ontology/useEntityTypeQuery";

export interface Entity {
  id: string;
  label: string;
}

export interface EntitySearchPickerProps {
  entityType: "Class" | "Taxonomy" | "ConceptScheme" | "Individual" | "PropertyDefinition";
  selectedId?: string;
  onSelect: (entity: Entity | null) => void;
  placeholder?: string;
  disabled?: boolean;
  "data-testid"?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}

export function EntitySearchPicker({
  entityType,
  selectedId,
  onSelect,
  placeholder = "Search entities…",
  disabled = false,
  "data-testid": testId,
  "aria-invalid": ariaInvalid,
  "aria-describedby": ariaDescribedBy,
}: EntitySearchPickerProps) {
  const [query, setQuery] = useState("");
  const currentQuery = useEntityTypeQuery(entityType);

  const errorMessage = currentQuery.isError
    ? currentQuery.error instanceof Error
      ? currentQuery.error.message
      : `Failed to load ${entityType.toLowerCase()}s`
    : undefined;

  const entities = useMemo(() => currentQuery.data?.items || [], [currentQuery.data?.items]);

  const results = useMemo(() => {
    if (!query.trim()) return [];

    const filtered = entities.filter(
      (e: any) =>
        e.title?.toLowerCase().includes(query.toLowerCase()) ||
        e.id?.toLowerCase().includes(query.toLowerCase())
    );

    return filtered.slice(0, 50).map((e: any) => ({
      id: e.id,
      label: e.title || e.id,
    }));
  }, [entities, query]);

  const selectedEntity = useMemo(
    () => entities.find((e: any) => e.id === selectedId),
    [entities, selectedId]
  );

  const handleSelect = (result: Entity) => {
    onSelect(result);
    setQuery("");
  };

  const handleClear = () => {
    onSelect(null);
    setQuery("");
  };

  return (
    <div data-testid={testId} className="entity-search-picker">
      {errorMessage && (
        <div className="entity-picker-error" role="alert">
          {errorMessage}
        </div>
      )}
      {selectedEntity ? (
        <div className="selected-entity">
          <span>{selectedEntity.title || selectedEntity.id}</span>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleClear}
            disabled={disabled || currentQuery.isLoading}
            aria-label={`Clear ${entityType} selection`}
            data-testid={testId ? `${testId}-clear` : undefined}
          >
            ✕
          </Button>
        </div>
      ) : (
        <EntityPicker
          query={query}
          onQueryChange={setQuery}
          results={results}
          onSelect={handleSelect}
          onClear={handleClear}
          placeholder={placeholder}
          disabled={disabled || currentQuery.isLoading || currentQuery.isError}
          data-testid={testId ? `${testId}-input` : undefined}
          aria-invalid={ariaInvalid || currentQuery.isError}
          aria-describedby={ariaDescribedBy}
        />
      )}
    </div>
  );
}
