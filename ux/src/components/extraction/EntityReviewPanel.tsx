import { useState, useRef, useEffect } from "react";
import { ChevronDown, CheckCircle, X } from "lucide-react";
import { useCreateClass, useClasses, useSchemes } from "@/api/hooks/ontology";
import { useToasts } from "@/components/ui/Toast";
import { Panel } from "@/components/ui/Panel";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Chip } from "@/components/ui/Chip";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatConfidence } from "@/utils/confidence";
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
  availableClasses: Array<{ id: string; title: string }>;
  onApprove: (entity: ExtractedEntitySchema) => void;
  onReject: (entityId: string) => void;
  onLink: (entity: ExtractedEntitySchema, _targetClassId: string) => void;
}

function EntityRow({
  entity,
  index,
  isProcessing,
  availableClasses,
  onApprove,
  onReject,
  onLink,
}: EntityRowProps) {
  const [linkingState, setLinkingState] = useState<{ searchQuery: string } | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Handle click-outside for dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setLinkingState(null);
      }
    };
    if (linkingState) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [linkingState]);

  const filteredClasses = linkingState
    ? availableClasses.filter(
        (cls) =>
          cls.title.toLowerCase().includes(linkingState.searchQuery.toLowerCase()) ||
          cls.id.toLowerCase().includes(linkingState.searchQuery.toLowerCase()),
      )
    : [];

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
        <div style={{ position: "relative" }} ref={dropdownRef}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              setLinkingState({
                searchQuery: "",
              })
            }
            disabled={isProcessing || linkingState !== null}
            data-testid={`entity-review-link-${entity.id}`}
          >
            {COPY.LINK_BUTTON}
            {linkingState !== null && (
              <ChevronDown
                size={14}
                style={{
                  marginLeft: "4px",
                  transform: "rotate(180deg)",
                }}
              />
            )}
          </Button>

          {linkingState !== null && (
            <div className="dropdown-popover" role="listbox">
              <div style={{ padding: "8px" }}>
                <Input
                  type="text"
                  placeholder={COPY.SEARCH_CLASSES_PLACEHOLDER}
                  value={linkingState.searchQuery}
                  onChange={(e) => {
                    setLinkingState({
                      ...linkingState,
                      searchQuery: e.target.value,
                    });
                  }}
                  data-testid="entity-review-link-input"
                  style={{ marginBottom: "8px" }}
                  role="combobox"
                  aria-expanded={linkingState !== null}
                  aria-controls="entity-review-options"
                />
                {filteredClasses.length > 0 ? (
                  <div
                    id="entity-review-options"
                    style={{
                      maxHeight: "200px",
                      overflowY: "auto",
                    }}
                  >
                    {filteredClasses.map((cls) => (
                      <button
                        key={cls.id}
                        type="button"
                        onClick={() => {
                          onLink(entity, cls.id);
                          setLinkingState(null);
                        }}
                        className="dropdown-option"
                        data-testid={`entity-review-link-option-${cls.id}`}
                        role="option"
                      >
                        <span
                          className="mono"
                          style={{
                            fontSize: "var(--text-xs)",
                            color: "var(--canvas-fg-3)",
                          }}
                        >
                          {cls.id.slice(0, 8)}
                        </span>
                        <span>{cls.title}</span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "8px",
                      textAlign: "center",
                      color: "var(--canvas-fg-2)",
                      fontSize: "var(--text-sm)",
                    }}
                  >
                    {COPY.NO_CLASSES_FOUND}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Close linking */}
      {linkingState !== null && (
        <button
          type="button"
          onClick={() => setLinkingState(null)}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "4px",
            display: "flex",
            alignItems: "center",
          }}
          aria-label="Close"
        >
          <X size={16} color="var(--canvas-fg-3)" />
        </button>
      )}
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
  const { data: classesList } = useClasses();
  const { data: schemesList } = useSchemes();

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

  const handleLinkConfirm = (entity: ExtractedEntitySchema, targetClassId: string) => {
    // TODO: Implement entity-to-class linking API call when backend supports it
    // For now, this optimistically updates UI state as placeholder
    setLinkedIds((prev) => new Set([...prev, entity.id]));
    toast("info", "Link recorded locally. API persistence coming soon.");
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
        toast("success", `${COPY.CLASSES_CREATED}${fulfilledEntityIds.length}${COPY.CLASSES_CREATED_SUFFIX}`);
      }
      if (failedResults.length > 0) {
        toast("error", `${COPY.CLASSES_CREATION_FAILED}${failedResults.length}${COPY.CLASSES_CREATION_FAILED_SUFFIX}`);
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

  // Populated state
  const availableClasses = classesList?.items?.filter((cls) => !cls.id.startsWith("_")) || [];

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
              availableClasses={availableClasses}
              onApprove={handleApprove}
              onReject={handleReject}
              onLink={handleLinkConfirm}
            />
          ))}
        </div>
      </Panel>
    </div>
  );
}
