import { useState, useMemo } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@tinkermonkey/heimdall-ui";
import { EmptyState } from "@/components/ui/EmptyState";
import { useProposalConflicts, useResolveConflicts } from "@/api/hooks/versioning";
import { useIndividuals, useTaxonomies, useClasses } from "@/api/hooks/ontology";
import { useToasts } from "@/components/ui/Toast";
import { COPY } from "@/routes/app/versioning/copy";
import type { components } from "@/api/types";

type ConflictResponse = components["schemas"]["ConflictResponse"];

interface ConflictResolverProps {
  proposalId: string | undefined;
  onResolved?: () => void;
}

interface ResolutionState {
  [entityId: string]: {
    [fieldName: string]: unknown;
  };
}

function ConflictRow({
  conflict,
  entityName,
  isResolved,
  onKeepOurs,
  onKeepTheirs,
  onEdit,
  onEditCancel,
  isEditing,
  editValue,
  onEditChange,
  onEditSubmit,
}: {
  conflict: ConflictResponse;
  entityName: string;
  isResolved: boolean;
  onKeepOurs: () => void;
  onKeepTheirs: () => void;
  onEdit: () => void;
  onEditCancel: () => void;
  isEditing: boolean;
  editValue: string;
  onEditChange: (value: string) => void;
  onEditSubmit: () => void;
}) {
  const [showDiff, setShowDiff] = useState(false);

  return (
    <div
      data-testid={`conflict-row-${conflict.entity_id}-${conflict.field_name}`}
      className="conflict-row"
      style={{
        padding: "12px 16px",
        borderBottom: "1px solid var(--canvas-border)",
        display: "grid",
        gridTemplateColumns: "150px 1fr 1fr 1fr 120px",
        gap: "12px",
        alignItems: "center",
        opacity: isResolved ? 0.6 : 1,
      }}
    >
      <div
        style={{
          fontSize: "13px",
          fontWeight: 500,
          color: "var(--canvas-fg-1)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {entityName}
      </div>

      <div
        onMouseEnter={() => setShowDiff(true)}
        onMouseLeave={() => setShowDiff(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setShowDiff(!showDiff);
          }
        }}
        role="button"
        tabIndex={0}
        aria-label={`View diff for ${conflict.field_name}`}
        style={{
          position: "relative",
          fontSize: "13px",
          color: "var(--canvas-fg-2)",
          cursor: "help",
        }}
      >
        {conflict.field_name}
        {showDiff && (
          <div className="diff-tooltip" role="tooltip">
            <div className="diff-container">
              <div className="diff-column diff-removed">
                <div className="diff-label">{COPY.diffLabelOurs}</div>
                <div className="diff-value">{JSON.stringify(conflict.base_value)}</div>
              </div>
              <div className="diff-column diff-added">
                <div className="diff-label">{COPY.diffLabelTheirs}</div>
                <div className="diff-value">{JSON.stringify(conflict.incoming_value)}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mono muted">{JSON.stringify(conflict.base_value)}</div>

      <div className="mono muted">{JSON.stringify(conflict.incoming_value)}</div>

      {isResolved ? (
        <div style={{ fontSize: "11px", fontWeight: 500 }}>
          <span className="chip emerald">{COPY.resolvedChip}</span>
        </div>
      ) : isEditing ? (
        <div className="flex-gap-sm">
          <input
            type="text"
            value={editValue}
            onChange={(e) => onEditChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onEditSubmit();
              if (e.key === "Escape") onEditCancel();
            }}
            style={{
              flex: 1,
              padding: "4px 8px",
              fontSize: "12px",
              border: "1px solid var(--canvas-border)",
              borderRadius: "var(--radius-sm, 4px)",
              backgroundColor: "var(--canvas-bg)",
              color: "var(--canvas-fg)",
            }}
            autoFocus
            aria-label={`Edit resolution for ${conflict.field_name}`}
          />
          <Button size="sm" variant="primary" onClick={onEditSubmit}>
            ✓
          </Button>
          <Button size="sm" variant="ghost" onClick={onEditCancel}>
            ✕
          </Button>
        </div>
      ) : (
        <div className="flex-gap-sm">
          <Button
            data-testid={`conflict-keep-ours-${conflict.entity_id}-${conflict.field_name}`}
            size="sm"
            variant="ghost"
            onClick={onKeepOurs}
          >
            {COPY.ourValue}
          </Button>
          <Button
            data-testid={`conflict-keep-theirs-${conflict.entity_id}-${conflict.field_name}`}
            size="sm"
            variant="ghost"
            onClick={onKeepTheirs}
          >
            {COPY.theirValue}
          </Button>
          <Button
            data-testid={`conflict-edit-${conflict.entity_id}-${conflict.field_name}`}
            size="sm"
            variant="ghost"
            onClick={onEdit}
          >
            {COPY.editButton}
          </Button>
        </div>
      )}
    </div>
  );
}

function ConflictGroup({
  entityId,
  entityName,
  conflicts,
  resolutions,
  editingKey,
  editValue,
  onKeepOurs,
  onKeepTheirs,
  onEdit,
  onEditCancel,
  onEditChange,
  onEditSubmit,
}: {
  entityId: string;
  entityName: string;
  conflicts: ConflictResponse[];
  resolutions: ResolutionState;
  editingKey: string | null;
  editValue: string;
  onKeepOurs: (fieldName: string) => void;
  onKeepTheirs: (fieldName: string) => void;
  onEdit: (fieldName: string) => void;
  onEditCancel: () => void;
  onEditChange: (value: string) => void;
  onEditSubmit: (fieldName: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const resolvedCount = conflicts.filter(
    (c) => resolutions[entityId]?.[c.field_name] !== undefined,
  ).length;

  return (
    <div
      data-testid={`conflict-group-${entityId}`}
      style={{ borderBottom: "1px solid var(--canvas-border)" }}
    >
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        aria-controls={`conflict-group-contents-${entityId}`}
        style={{
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          backgroundColor: "var(--canvas-bg-2)",
          userSelect: "none",
        }}
      >
        <div className="flex-row-center" style={{ gap: "8px" }}>
          <span
            style={{
              width: "20px",
              height: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transform: isExpanded ? "rotate(0deg)" : "rotate(-90deg)",
              transition: "transform 0.2s",
              fontSize: "12px",
            }}
            aria-hidden="true"
          >
            ▼
          </span>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--canvas-fg-1)" }}>
            {entityName}
          </span>
          <span className="chip gray" style={{ fontSize: "11px" }}>
            {resolvedCount}/{conflicts.length}
          </span>
        </div>
      </div>

      {isExpanded && (
        <div id={`conflict-group-contents-${entityId}`}>
          {/* Header row */}
          <div
            style={{
              padding: "8px 16px",
              display: "grid",
              gridTemplateColumns: "150px 1fr 1fr 1fr 120px",
              gap: "12px",
              borderBottom: "1px solid var(--canvas-border)",
              backgroundColor: "var(--canvas-bg)",
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--canvas-fg-3)",
              textTransform: "uppercase",
            }}
          >
            <div>{COPY.entityHeader}</div>
            <div>{COPY.fieldHeader}</div>
            <div>{COPY.oursHeader}</div>
            <div>{COPY.theirsHeader}</div>
            <div>{COPY.actionHeader}</div>
          </div>

          {/* Conflict rows */}
          {conflicts.map((conflict) => {
            const key = `${conflict.entity_id}-${conflict.field_name}`;
            const isResolved = resolutions[entityId]?.[conflict.field_name] !== undefined;
            const isEditing = editingKey === key;

            return (
              <ConflictRow
                key={key}
                conflict={conflict}
                entityName={entityName}
                isResolved={isResolved}
                onKeepOurs={() => onKeepOurs(conflict.field_name)}
                onKeepTheirs={() => onKeepTheirs(conflict.field_name)}
                onEdit={() => onEdit(conflict.field_name)}
                onEditCancel={onEditCancel}
                isEditing={isEditing}
                editValue={editValue}
                onEditChange={onEditChange}
                onEditSubmit={() => onEditSubmit(conflict.field_name)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ConflictResolver({ proposalId, onResolved }: ConflictResolverProps) {
  const { toast } = useToasts();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [resolutions, setResolutions] = useState<ResolutionState>({});

  const {
    data: conflictReport,
    isLoading: conflictsLoading,
    error: conflictsError,
    refetch: refetchConflicts,
  } = useProposalConflicts(proposalId);

  const resolveConflictsMutation = useResolveConflicts();

  const conflicts = useMemo(() => {
    return conflictReport?.conflicts || [];
  }, [conflictReport]);

  const uniqueEntityIds = useMemo(() => {
    return [...new Set(conflicts.map((c) => c.entity_id))];
  }, [conflicts]);

  const {
    data: individuals = [],
    error: individualsError,
    refetch: refetchIndividuals,
  } = useIndividuals();
  const {
    data: taxonomyResp,
    error: taxonomiesError,
    refetch: refetchTaxonomies,
  } = useTaxonomies();
  const { data: classesResp, error: classesError, refetch: refetchClasses } = useClasses();

  const entityMap = useMemo(() => {
    const map = new Map<string, string>();

    const indItems =
      (individuals as { items?: Array<{ id: string; title?: string }> })?.items || [];
    indItems.forEach((ind) => {
      map.set(ind.id, ind.title || ind.id.substring(0, 8));
    });

    const taxItems =
      (taxonomyResp as { items?: Array<{ id: string; title: string }> })?.items || [];
    taxItems.forEach((tax) => {
      map.set(tax.id, tax.title || tax.id.substring(0, 8));
    });

    const clsItems = (classesResp as { items?: Array<{ id: string; title: string }> })?.items || [];
    clsItems.forEach((cls) => {
      map.set(cls.id, cls.title || cls.id.substring(0, 8));
    });

    return map;
  }, [individuals, taxonomyResp, classesResp]);

  const getEntityName = (entityId: string): string => {
    return entityMap.get(entityId) || entityId.substring(0, 8);
  };

  const handleKeepOurs = (entityId: string, fieldName: string) => {
    const conflict = conflicts.find((c) => c.entity_id === entityId && c.field_name === fieldName);
    if (!conflict) return;

    setResolutions((prev) => ({
      ...prev,
      [entityId]: {
        ...prev[entityId],
        [fieldName]: conflict.base_value,
      },
    }));
    setEditingKey(null);
  };

  const handleKeepTheirs = (entityId: string, fieldName: string) => {
    const conflict = conflicts.find((c) => c.entity_id === entityId && c.field_name === fieldName);
    if (!conflict) return;

    setResolutions((prev) => ({
      ...prev,
      [entityId]: {
        ...prev[entityId],
        [fieldName]: conflict.incoming_value,
      },
    }));
    setEditingKey(null);
  };

  const handleEdit = (entityId: string, fieldName: string) => {
    const conflict = conflicts.find((c) => c.entity_id === entityId && c.field_name === fieldName);
    if (!conflict) return;

    const currentValue = resolutions[entityId]?.[fieldName] ?? conflict.base_value;
    setEditingKey(`${entityId}-${fieldName}`);
    setEditValue(JSON.stringify(currentValue));
  };

  const handleEditCancel = () => {
    setEditingKey(null);
    setEditValue("");
  };

  const handleEditSubmit = (entityId: string, fieldName: string) => {
    let parsedValue;
    try {
      parsedValue = JSON.parse(editValue);
    } catch {
      toast("error", COPY.invalidJSONValue);
      return;
    }

    setResolutions((prev) => ({
      ...prev,
      [entityId]: {
        ...prev[entityId],
        [fieldName]: parsedValue,
      },
    }));
    setEditingKey(null);
    setEditValue("");
  };

  const allConflictsResolved =
    conflicts.length > 0 &&
    conflicts.every((c) => resolutions[c.entity_id]?.[c.field_name] !== undefined);

  const handleApplyResolutions = async () => {
    if (!proposalId || !allConflictsResolved) return;

    try {
      await resolveConflictsMutation.mutateAsync({
        proposalId,
        resolutions,
      });
      setResolutions({});
      onResolved?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : COPY.failedToResolveConflicts;
      toast("error", message);
    }
  };

  if (conflictsLoading) {
    return (
      <div className="stack-lg" style={{ flex: 1, overflow: "auto" }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} height="64px" style={{ borderRadius: "var(--radius-md, 6px)" }} />
        ))}
      </div>
    );
  }

  if (conflictsError) {
    return (
      <ErrorBanner
        error={conflictsError}
        onRetry={refetchConflicts}
        message={COPY.couldNotLoadConflicts}
      />
    );
  }

  const entityDataError = individualsError || taxonomiesError || classesError;
  if (entityDataError) {
    const refetchAll = () => {
      refetchIndividuals();
      refetchTaxonomies();
      refetchClasses();
    };
    return (
      <ErrorBanner
        error={entityDataError}
        onRetry={refetchAll}
        message="Failed to load entity names for conflict resolution"
      />
    );
  }

  if (!conflicts || conflicts.length === 0) {
    return <EmptyState title={COPY.noConflicts} description={COPY.allClear} icon="✓" />;
  }

  return (
    <div
      data-testid="conflict-resolver"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        gap: "12px",
      }}
    >
      <div
        data-testid="conflict-list"
        style={{
          flex: 1,
          overflow: "auto",
          border: "1px solid var(--canvas-border)",
          borderRadius: "var(--radius-md, 6px)",
        }}
      >
        {uniqueEntityIds.map((entityId) => {
          const entityConflicts = conflicts.filter((c) => c.entity_id === entityId);
          return (
            <ConflictGroup
              key={entityId}
              entityId={entityId}
              entityName={getEntityName(entityId)}
              conflicts={entityConflicts}
              resolutions={resolutions}
              editingKey={editingKey}
              editValue={editValue}
              onKeepOurs={(fieldName) => handleKeepOurs(entityId, fieldName)}
              onKeepTheirs={(fieldName) => handleKeepTheirs(entityId, fieldName)}
              onEdit={(fieldName) => handleEdit(entityId, fieldName)}
              onEditCancel={handleEditCancel}
              onEditChange={setEditValue}
              onEditSubmit={(fieldName) => handleEditSubmit(entityId, fieldName)}
            />
          );
        })}
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", paddingTop: "12px" }}>
        <Button
          data-testid="conflict-apply-resolutions-button"
          variant="primary"
          onClick={handleApplyResolutions}
          disabled={!allConflictsResolved || resolveConflictsMutation.isPending}
        >
          {resolveConflictsMutation.isPending
            ? COPY.applyingResolutionsButton
            : COPY.applyResolutionsButton}
        </Button>
      </div>
    </div>
  );
}
