import { useState, useMemo } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useProposalConflicts, useResolveConflicts } from "@/api/hooks/versioning";
import { useIndividuals, useTaxonomies, useClasses } from "@/api/hooks/ontology";
import { useToasts } from "@/components/ui/Toast";
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
  resolvedValue,
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
  resolvedValue?: unknown;
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
        borderBottom: "1px solid var(--canvas-bd)",
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
        style={{
          position: "relative",
          fontSize: "13px",
          color: "var(--canvas-fg-2)",
          cursor: "help",
        }}
      >
        {conflict.field_name}
        {showDiff && (
          <div className="diff-tooltip">
            <div className="diff-container">
              <div className="diff-column diff-removed">
                <div className="diff-label">Ours</div>
                <div className="diff-value">{JSON.stringify(conflict.base_value)}</div>
              </div>
              <div className="diff-column diff-added">
                <div className="diff-label">Theirs</div>
                <div className="diff-value">{JSON.stringify(conflict.incoming_value)}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div
        style={{
          fontSize: "12px",
          color: "var(--canvas-fg-3)",
          fontFamily: "var(--mono)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {JSON.stringify(conflict.base_value)}
      </div>

      <div
        style={{
          fontSize: "12px",
          color: "var(--canvas-fg-3)",
          fontFamily: "var(--mono)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {JSON.stringify(conflict.incoming_value)}
      </div>

      {isResolved ? (
        <div style={{ fontSize: "11px", fontWeight: 500 }}>
          <span className="chip emerald">✓ resolved</span>
        </div>
      ) : isEditing ? (
        <div style={{ display: "flex", gap: "4px" }}>
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
              border: "1px solid var(--canvas-bd)",
              borderRadius: "var(--radius-sm, 4px)",
              backgroundColor: "var(--canvas-bg)",
              color: "var(--canvas-fg)",
            }}
            autoFocus
          />
          <Button size="sm" variant="primary" onClick={onEditSubmit}>
            ✓
          </Button>
          <Button size="sm" variant="ghost" onClick={onEditCancel}>
            ✕
          </Button>
        </div>
      ) : (
        <div style={{ display: "flex", gap: "4px" }}>
          <Button
            data-testid={`conflict-keep-ours-${conflict.entity_id}-${conflict.field_name}`}
            size="sm"
            variant="ghost"
            onClick={onKeepOurs}
          >
            Ours
          </Button>
          <Button
            data-testid={`conflict-keep-theirs-${conflict.entity_id}-${conflict.field_name}`}
            size="sm"
            variant="ghost"
            onClick={onKeepTheirs}
          >
            Theirs
          </Button>
          <Button
            data-testid={`conflict-edit-${conflict.entity_id}-${conflict.field_name}`}
            size="sm"
            variant="ghost"
            onClick={onEdit}
          >
            Edit
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
    <div data-testid={`conflict-group-${entityId}`} style={{ borderBottom: "1px solid var(--canvas-bd)" }}>
      <div
        onClick={() => setIsExpanded(!isExpanded)}
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
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
        <>
          {/* Header row */}
          <div
            style={{
              padding: "8px 16px",
              display: "grid",
              gridTemplateColumns: "150px 1fr 1fr 1fr 120px",
              gap: "12px",
              borderBottom: "1px solid var(--canvas-bd)",
              backgroundColor: "var(--canvas-bg)",
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--canvas-fg-3)",
              textTransform: "uppercase",
            }}
          >
            <div>Entity</div>
            <div>Field</div>
            <div>Ours</div>
            <div>Theirs</div>
            <div>Action</div>
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
                resolvedValue={resolutions[entityId]?.[conflict.field_name]}
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
        </>
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

  const conflicts = conflictReport?.conflicts || [];

  const uniqueEntityIds = useMemo(() => {
    return [...new Set(conflicts.map((c) => c.entity_id))];
  }, [conflicts]);

  const { data: individuals = [] } = useIndividuals();
  const { data: taxonomyResp } = useTaxonomies();
  const { data: classesResp } = useClasses();

  const entityMap = useMemo(() => {
    const map = new Map<string, string>();

    if (individuals && typeof individuals === "object" && "items" in individuals) {
      (individuals.items as Array<{ id: string; title?: string }>).forEach((ind) => {
        map.set(ind.id, ind.title || ind.id.substring(0, 8));
      });
    }

    if (taxonomyResp && typeof taxonomyResp === "object" && "items" in taxonomyResp) {
      (taxonomyResp.items as Array<{ id: string; title: string }>).forEach((tax) => {
        map.set(tax.id, tax.title || tax.id.substring(0, 8));
      });
    }

    if (classesResp && typeof classesResp === "object" && "items" in classesResp) {
      (classesResp.items as Array<{ id: string; title: string }>).forEach((cls) => {
        map.set(cls.id, cls.title || cls.id.substring(0, 8));
      });
    }

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
    try {
      const parsedValue = JSON.parse(editValue);
      setResolutions((prev) => ({
        ...prev,
        [entityId]: {
          ...prev[entityId],
          [fieldName]: parsedValue,
        },
      }));
      setEditingKey(null);
      setEditValue("");
    } catch {
      toast("error", "Invalid JSON value");
    }
  };

  const allConflictsResolved =
    conflicts.length > 0 &&
    conflicts.every(
      (c) => resolutions[c.entity_id]?.[c.field_name] !== undefined,
    );

  const handleApplyResolutions = async () => {
    if (!proposalId || !allConflictsResolved) return;

    try {
      await resolveConflictsMutation.mutateAsync({
        proposalId,
        resolutions,
      });
      setResolutions({});
      toast("success", "Conflicts resolved successfully");
      onResolved?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to resolve conflicts";
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
        message="Could not load conflicts"
      />
    );
  }

  if (!conflicts || conflicts.length === 0) {
    return (
      <EmptyState
        title="No conflicts"
        description="All clear"
        icon="✓"
      />
    );
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
          border: "1px solid var(--canvas-bd)",
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
          {resolveConflictsMutation.isPending ? "Applying..." : "Apply Resolutions"}
        </Button>
      </div>
    </div>
  );
}
