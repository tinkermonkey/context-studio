import { useState, useMemo } from "react";
import { EntityPicker, Button } from "@tinkermonkey/heimdall-ui";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";

export interface Entity {
  id: string;
  label: string;
}

export interface EntitySearchPickerProps {
  entityType: "Class" | "Taxonomy" | "ConceptScheme" | "Individual";
  selectedId?: string;
  onSelect: (entity: Entity | null) => void;
  placeholder?: string;
  disabled?: boolean;
  "data-testid"?: string;
}

export function EntitySearchPicker({
  entityType,
  selectedId,
  onSelect,
  placeholder = "Search entities…",
  disabled = false,
  "data-testid": testId,
}: EntitySearchPickerProps) {
  const [query, setQuery] = useState("");

  const classesQuery = useClasses();
  const taxonomiesQuery = useTaxonomies();
  const schemesQuery = useSchemes();
  const individualsQuery = useIndividuals();

  const currentQuery = useMemo(() => {
    switch (entityType) {
      case "Class":
        return classesQuery;
      case "Taxonomy":
        return taxonomiesQuery;
      case "ConceptScheme":
        return schemesQuery;
      case "Individual":
        return individualsQuery;
    }
  }, [entityType, classesQuery, taxonomiesQuery, schemesQuery, individualsQuery]);

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
      {selectedEntity ? (
        <div className="selected-entity">
          <span>{selectedEntity.title || selectedEntity.id}</span>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleClear}
            disabled={disabled}
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
          disabled={disabled || currentQuery.isLoading}
          data-testid={testId ? `${testId}-input` : undefined}
        />
      )}
    </div>
  );
}
