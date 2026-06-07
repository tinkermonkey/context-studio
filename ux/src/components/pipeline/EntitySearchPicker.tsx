import { useState, useMemo } from "react";
import { EntityPicker, Button } from "@tinkermonkey/heimdall-ui";
import { useEntityTypeQuery } from "@/api/hooks/ontology/useEntityTypeQuery";
import "./EntitySearchPicker.css";

export interface Entity {
  id: string;
  label: string;
}

export interface EntitySearchPickerProps {
  entityType: "Class" | "Taxonomy" | "ConceptScheme" | "Individual" | "PropertyDefinition";
  selectedId?: string;
  selectedIds?: string[];
  onSelect?: (entity: Entity | null) => void;
  onSelectMultiple?: (entities: Entity[]) => void;
  multiSelect?: boolean;
  placeholder?: string;
  disabled?: boolean;
  "data-testid"?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}

interface ApiEntity {
  id: string;
  title?: string;
}

export function EntitySearchPicker({
  entityType,
  selectedId,
  selectedIds = [],
  onSelect,
  onSelectMultiple,
  multiSelect = false,
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

  const entities = useMemo<ApiEntity[]>(() => currentQuery.data?.items || [], [currentQuery.data?.items]);

  const results = useMemo(() => {
    if (!query.trim()) return [];

    const filtered = entities.filter(
      (e: ApiEntity) =>
        e.title?.toLowerCase().includes(query.toLowerCase()) ||
        e.id?.toLowerCase().includes(query.toLowerCase()),
    );

    return filtered.slice(0, 50).map((e: ApiEntity) => ({
      id: e.id,
      label: e.title || e.id,
    }));
  }, [entities, query]);

  const selectedEntity = useMemo(
    () => entities.find((e: ApiEntity) => e.id === selectedId),
    [entities, selectedId],
  );

  const selectedEntities = useMemo(
    () => entities.filter((e: ApiEntity) => selectedIds.includes(e.id)).map((e: ApiEntity) => ({
      id: e.id,
      label: e.title || e.id,
    })),
    [entities, selectedIds],
  );

  const handleSelect = (result: Entity) => {
    if (multiSelect && onSelectMultiple) {
      if (selectedIds.includes(result.id)) {
        onSelectMultiple(selectedEntities.filter((e) => e.id !== result.id));
      } else {
        onSelectMultiple([...selectedEntities, result]);
      }
    } else if (onSelect) {
      onSelect(result);
    }
    setQuery("");
  };

  const handleClear = () => {
    if (multiSelect && onSelectMultiple) {
      onSelectMultiple([]);
    } else if (onSelect) {
      onSelect(null);
    }
    setQuery("");
  };

  const handleRemoveEntity = (id: string) => {
    if (multiSelect && onSelectMultiple) {
      onSelectMultiple(selectedEntities.filter((e) => e.id !== id));
    }
  };

  return (
    <div data-testid={testId} className="entity-search-picker">
      {errorMessage && (
        <div className="error-banner-compact" role="alert" data-testid="entity-picker-error">
          {errorMessage}
        </div>
      )}
      {multiSelect ? (
        <>
          {selectedEntities.length > 0 && (
            <div className="selected-entities-list" role="list" data-testid={testId ? `${testId}-list` : undefined}>
              {selectedEntities.map((entity) => (
                <div key={entity.id} className="selected-entity-chip" role="listitem">
                  <span>{entity.label}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleRemoveEntity(entity.id)}
                    disabled={disabled || currentQuery.isLoading}
                    aria-label={`Remove ${entity.label}`}
                    data-testid={testId ? `${testId}-remove-${entity.id}` : undefined}
                  >
                    ✕
                  </Button>
                </div>
              ))}
            </div>
          )}
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
        </>
      ) : selectedEntity ? (
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
