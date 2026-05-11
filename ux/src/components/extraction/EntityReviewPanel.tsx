import { useState } from "react";
import { CheckCircle } from "lucide-react";
import { useCreateClass, useClasses, useSchemes } from "@/api/hooks/ontology";
import { useToasts } from "@/components/ui/Toast";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Panel } from "@/components/ui/Panel";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatConfidence } from "@/utils/formatters";
import { COPY } from "@/routes/app/extraction/-copy";
import type { components } from "@/api/types";

type ExtractedEntitySchema = components["schemas"]["ExtractedEntitySchema"];

interface EntityReviewPanelProps {
  entities: ExtractedEntitySchema[];
  layerIndex: number;
  isLoading?: boolean;
}

interface EntityRowProps {
  entity: ExtractedEntitySchema;
  index: number;
  isProcessing: boolean;
  onApprove: (entity: ExtractedEntitySchema) => void;
  onReject: (entityId: string) => void;
}

function EntityRow({
  entity,
  index,
  isProcessing,
  onApprove,
  onReject,
}: EntityRowProps) {

  return (
    <div
      key={entity.id}
      data-testid={`entity-suggestion-row-${index}`}
      className="flex-between"
      style={{
        padding: "12px",
        backgroundColor: "var(--canvas-bg-2)",
        borderRadius: "var(--radius-md)",
        borderLeft: "3px solid var(--cyan-500)",
        gap: "12px",
      }}
    >
      {/* Entity info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 500, marginBottom: "4px" }}>{entity.label}</div>
        <div className="flex-row-center">
          {entity.entity_type && (
            <Chip color="gray" className="text-xs">
              {entity.entity_type}
            </Chip>
          )}
          <span
            className="mono"
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--canvas-fg-3)",
            }}
          >
            {formatConfidence(entity.confidence)}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex-gap-sm">
        <Button
          variant="primary"
          size="sm"
          onClick={() => onApprove(entity)}
          disabled={isProcessing}
          data-testid={`entity-review-approve-${entity.id}`}
        >
          {COPY.APPROVE_BUTTON}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onReject(entity.id)}
          disabled={isProcessing}
          data-testid={`entity-review-reject-${entity.id}`}
        >
          {COPY.REJECT_BUTTON}
        </Button>
      </div>
    </div>
  );
}

export function EntityReviewPanel({
  entities,
  layerIndex,
  isLoading = false,
}: EntityReviewPanelProps) {
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());
  const [linkedIds, setLinkedIds] = useState<Set<string>>(new Set());
  const [isProcessing, setIsProcessing] = useState(false);

  const { toast } = useToasts();

  const createClassMutation = useCreateClass();
  const { data: classesList, error: classesError, refetch: refetchClasses } = useClasses();
  const { data: schemesList, error: schemesError, refetch: refetchSchemes } = useSchemes();

  const layerNames: Record<number, string> = {
    0: "KG Context",
    1: "LLM Extraction",
    2: "NLP Gap Fill",
    3: "Reference Enrichment",
  };

  const layerName = layerNames[layerIndex] || `Layer ${layerIndex}`;

  // Filter entities: only show unlinked, unrejected entities
  const unlinkedEntities = entities.filter(
    (e) => !e.matched_class_id && !rejectedIds.has(e.id) && !linkedIds.has(e.id),
  );

  // Determine state
  const isHidden = entities.length === 0;
  const isEmpty = !isLoading && unlinkedEntities.length === 0;

  const handleApprove = async (entity: ExtractedEntitySchema) => {
    try {
      setIsProcessing(true);
      const defaultScheme = schemesList?.items?.[0];
      if (!defaultScheme) {
        toast("error", COPY.NO_CONCEPT_SCHEME);
        return;
      }

      await createClassMutation.mutateAsync({
        schemeId: defaultScheme.id,
        data: {
          title: entity.label,
          description: entity.description || null,
        },
      });

      setLinkedIds((prev) => new Set([...prev, entity.id]));
      toast("success", `${COPY.CLASS_CREATED}${entity.label}`);
    } catch (error) {
      toast(
        "error",
        `${COPY.CLASS_CREATION_FAILED}${error instanceof Error ? error.message : "Unknown error"}`,
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = (entityId: string) => {
    setRejectedIds((prev) => new Set([...prev, entityId]));
    toast("info", COPY.ENTITY_REJECTED);
  };

  const handleApproveAll = async () => {
    if (unlinkedEntities.length === 0) return;

    try {
      setIsProcessing(true);
      const defaultScheme = schemesList?.items?.[0];
      if (!defaultScheme) {
        toast("error", COPY.NO_CONCEPT_SCHEME);
        return;
      }

      const results = await Promise.allSettled(
        unlinkedEntities.map((entity) =>
          createClassMutation.mutateAsync({
            schemeId: defaultScheme.id,
            data: {
              title: entity.label,
              description: entity.description || null,
            },
          }),
        ),
      );

      const failedResults = results.filter((r) => r.status === "rejected");
      const fulfilledEntityIds = results
        .map((r, i) => (r.status === "fulfilled" ? unlinkedEntities[i].id : null))
        .filter((id): id is string => id !== null);

      if (fulfilledEntityIds.length > 0) {
        setLinkedIds((prev) => new Set([...prev, ...fulfilledEntityIds]));
        toast(
          "success",
          `${COPY.CLASSES_CREATED}${fulfilledEntityIds.length}${COPY.CLASSES_CREATED_SUFFIX}`,
        );
      }
      if (failedResults.length > 0) {
        toast(
          "error",
          `${COPY.CLASSES_CREATION_FAILED}${failedResults.length}${COPY.CLASSES_CREATION_FAILED_SUFFIX}`,
        );
      }
    } catch (error) {
      toast(
        "error",
        `${COPY.BATCH_OPERATION_FAILED}${error instanceof Error ? error.message : "Unknown error"}`,
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRejectAll = () => {
    setRejectedIds((prev) => new Set([...prev, ...unlinkedEntities.map((e) => e.id)]));
    toast("info", COPY.ALL_ENTITIES_REJECTED);
  };

  // Hidden state
  if (isHidden) {
    return null;
  }

  // Error state: if either query failed, show error banner
  if (classesError || schemesError) {
    const failedQuery = classesError ? "classes" : "concept schemes";
    return (
      <div data-testid={`entity-review-panel-${layerIndex}`}>
        <Panel title={`${COPY.ENTITY_REVIEW_PANEL_TITLE} — ${layerName}`}>
          <div className="stack">
            <ErrorBanner
              error={classesError || schemesError}
              onRetry={() => {
                if (classesError) refetchClasses();
                if (schemesError) refetchSchemes();
              }}
              message={`Failed to load ${failedQuery}`}
              compact
            />
          </div>
        </Panel>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div data-testid={`entity-review-panel-${layerIndex}`}>
        <Panel title={`${COPY.ENTITY_REVIEW_PANEL_TITLE} — ${layerName}`}>
          <div className="stack">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex-row-center">
                <Skeleton width="200px" height="32px" />
                <Skeleton width="60px" height="24px" />
                <div style={{ marginLeft: "auto" }} className="flex-gap-sm">
                  <Skeleton width="60px" height="28px" />
                  <Skeleton width="60px" height="28px" />
                  <Skeleton width="60px" height="28px" />
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    );
  }

  // Empty state
  if (isEmpty) {
    return (
      <div data-testid={`entity-review-panel-${layerIndex}`}>
        <Panel title={`${COPY.ENTITY_REVIEW_PANEL_TITLE} — ${layerName}`}>
          <div
            className="stack"
            style={{
              padding: "12px",
              color: "var(--canvas-fg-2)",
              textAlign: "center",
              alignItems: "center",
            }}
          >
            <CheckCircle size={20} />
            <p style={{ margin: 0 }}>{COPY.ALL_SUGGESTIONS_REVIEWED}</p>
          </div>
        </Panel>
      </div>
    );
  }

  // Batch actions
  const batchActions = (
    <div className="flex-gap-sm">
      <Button
        variant="primary"
        size="sm"
        onClick={handleApproveAll}
        disabled={isProcessing}
        data-testid="entity-review-approve-all-button"
      >
        {COPY.APPROVE_ALL_BUTTON}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleRejectAll}
        disabled={isProcessing}
        data-testid="entity-review-reject-all-button"
      >
        {COPY.REJECT_ALL_BUTTON}
      </Button>
    </div>
  );

  return (
    <div data-testid={`entity-review-panel-${layerIndex}`}>
      <Panel
        title={`${COPY.ENTITY_REVIEW_PANEL_TITLE} — ${layerName} (${unlinkedEntities.length})`}
        actions={batchActions}
      >
        <div className="stack">
          {unlinkedEntities.map((entity, index) => (
            <EntityRow
              key={entity.id}
              entity={entity}
              index={index}
              isProcessing={isProcessing}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      </Panel>
    </div>
  );
}
