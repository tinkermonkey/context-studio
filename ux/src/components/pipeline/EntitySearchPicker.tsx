import { useMemo, useRef, useState } from "react";
import { EntityPicker, Button } from "@tinkermonkey/heimdall-ui";
import { useEntitiesById, useEntityTypeQuery } from "@/api/hooks/ontology/useEntityTypeQuery";
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
  // Matches are searched on the server; the selection is resolved by id so its
  // label shows even when it is not among the current matches.
  const currentQuery = useEntityTypeQuery(entityType, query);
  const wantedIds = multiSelect ? selectedIds : selectedId ? [selectedId] : [];
  const selectionQuery = useEntitiesById(entityType, wantedIds);

  const failed = currentQuery.isError ? currentQuery : selectionQuery.isError ? selectionQuery : null;
  const errorMessage = failed
    ? failed.error instanceof Error
      ? failed.error.message
      : `Failed to load ${entityType.toLowerCase()}s`
    : undefined;

  const results = useMemo(() => {
    if (!query.trim()) return [];
    return (currentQuery.data?.items ?? []).map((e: ApiEntity) => ({
      id: e.id,
      label: e.title || e.id,
    }));
  }, [currentQuery.data?.items, query]);

  const selectedPool = useMemo<ApiEntity[]>(
    () => selectionQuery.data?.items ?? [],
    [selectionQuery.data?.items],
  );

  const selectedEntity = useMemo(
    () => selectedPool.find((e: ApiEntity) => e.id === selectedId),
    [selectedPool, selectedId],
  );

  // Labels seen for picked entities, so a pick made before its id lookup
  // returns still shows (and is emitted with) its label.
  const pickedLabels = useRef(new Map<string, string>());

  // The selection is the caller's selectedIds; resolved entities only supply
  // labels. Building it from the async lookup instead would drop a pick made
  // while the lookup was still loading, or an id that never resolves.
  const selectedEntities = useMemo<Entity[]>(() => {
    const titles = new Map(selectedPool.map((e: ApiEntity) => [e.id, e.title || e.id]));
    return selectedIds.map((id) => ({
      id,
      label: titles.get(id) ?? pickedLabels.current.get(id) ?? id,
    }));
  }, [selectedPool, selectedIds]);

  const handleSelect = (result: Entity) => {
    pickedLabels.current.set(result.id, result.label);
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
            <div
              className="selected-entities-list"
              role="list"
              data-testid={testId ? `${testId}-list` : undefined}
            >
              {selectedEntities.map((entity) => (
                <div key={entity.id} className="selected-entity-chip" role="listitem">
                  <span>{entity.label}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleRemoveEntity(entity.id)}
                    disabled={disabled}
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
            disabled={disabled || !!failed}
            data-testid={testId ? `${testId}-input` : undefined}
            aria-invalid={ariaInvalid || !!failed}
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
          disabled={disabled || !!failed}
          data-testid={testId ? `${testId}-input` : undefined}
          aria-invalid={ariaInvalid || !!failed}
          aria-describedby={ariaDescribedBy}
        />
      )}
    </div>
  );
}
