import { useState, useRef, useEffect } from "react";
import { ChevronDown, CheckCircle, X } from "lucide-react";
import { useCreateClass, useClasses, useSchemes } from "@/api/hooks/ontology";
import { useToasts } from "@/components/ui/Toast";
import { Panel } from "@/components/ui/Panel";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Chip } from "@/components/ui/Chip";
import { Skeleton } from "@/components/ui/Skeleton";
import type { components } from "@/api/types";

type ExtractedEntitySchema = components["schemas"]["ExtractedEntitySchema"];

interface EntityReviewPanelProps {
  entities: ExtractedEntitySchema[];
  layerIndex: number;
  isLoading?: boolean;
}

interface LinkingState {
  entityId: string;
  searchQuery: string;
}

export function EntityReviewPanel({
  entities,
  layerIndex,
  isLoading = false,
}: EntityReviewPanelProps) {
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());
  const [linkedIds, setLinkedIds] = useState<Set<string>>(new Set());
  const [linkingState, setLinkingState] = useState<LinkingState | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const { toast } = useToasts();
  const dropdownRef = useRef<HTMLDivElement>(null);

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
    (e) => !e.matched_class_id && !rejectedIds.has(e.id) && !linkedIds.has(e.id)
  );

  // Determine state
  const isHidden = entities.length === 0;
  const isEmpty = !isLoading && unlinkedEntities.length === 0;
  const isPopulated = unlinkedEntities.length > 0 && !isLoading;

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

  const handleApprove = async (entity: ExtractedEntitySchema) => {
    try {
      setIsProcessing(true);
      const defaultScheme = schemesList?.items?.[0];
      if (!defaultScheme) {
        toast("error", "No concept scheme available for creating classes");
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
      toast("success", `Created class: ${entity.label}`);
    } catch (error) {
      toast(
        "error",
        `Failed to create class: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = (entityId: string) => {
    setRejectedIds((prev) => new Set([...prev, entityId]));
    toast("info", "Entity rejected");
  };

  const handleLinkConfirm = (entity: ExtractedEntitySchema, targetClassId: string) => {
    setLinkedIds((prev) => new Set([...prev, entity.id]));
    setLinkingState(null);
    toast("success", `Entity linked to class`);
    // TODO: persist via relationship API once available
  };

  const handleApproveAll = async () => {
    if (unlinkedEntities.length === 0) return;

    try {
      setIsProcessing(true);
      const defaultScheme = schemesList?.items?.[0];
      if (!defaultScheme) {
        toast("error", "No concept scheme available for creating classes");
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
          })
        )
      );

      const successful = results.filter((r) => r.status === "fulfilled").length;
      const failed = results.filter((r) => r.status === "rejected").length;

      if (successful > 0) {
        setLinkedIds(
          (prev) => new Set([...prev, ...unlinkedEntities.map((e) => e.id)])
        );
        toast("success", `Created ${successful} class(es)`);
      }
      if (failed > 0) {
        toast("error", `Failed to create ${failed} class(es)`);
      }
    } catch (error) {
      toast(
        "error",
        `Batch operation failed: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRejectAll = () => {
    setRejectedIds(
      (prev) => new Set([...prev, ...unlinkedEntities.map((e) => e.id)])
    );
    toast("info", "All entities rejected");
  };

  // Hidden state
  if (isHidden) {
    return null;
  }

  // Loading state
  if (isLoading) {
    return (
      <div data-testid={`entity-review-panel-${layerIndex}`}>
        <Panel title={`Entity Review — ${layerName}`}>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {[0, 1, 2].map((i) => (
              <div key={i} style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <Skeleton width="200px" height="32px" />
                <Skeleton width="60px" height="24px" />
                <div style={{ marginLeft: "auto", display: "flex", gap: "6px" }}>
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
        <Panel title={`Entity Review — ${layerName}`}>
          <div style={{ padding: "12px", color: "var(--canvas-fg-2)", textAlign: "center" }}>
            <CheckCircle size={20} style={{ margin: "0 auto 8px", display: "block" }} />
            <p style={{ margin: 0 }}>All suggestions reviewed</p>
          </div>
        </Panel>
      </div>
    );
  }

  // Batch actions
  const batchActions = (
    <div style={{ display: "flex", gap: "6px" }}>
      <Button
        variant="primary"
        size="sm"
        onClick={handleApproveAll}
        disabled={isProcessing}
        data-testid="entity-review-approve-all-button"
      >
        Approve All
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleRejectAll}
        disabled={isProcessing}
        data-testid="entity-review-reject-all-button"
      >
        Reject All
      </Button>
    </div>
  );

  // Populated state
  return (
    <div data-testid={`entity-review-panel-${layerIndex}`}>
      <Panel title={`Entity Review — ${layerName} (${unlinkedEntities.length})`} actions={batchActions}>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {unlinkedEntities.map((entity, index) => {
            const availableClasses = classesList?.items?.filter(
              (cls) => !cls.id.startsWith("_")
            ) || [];

            const filteredClasses = linkingState?.entityId === entity.id
              ? availableClasses.filter((cls: typeof availableClasses[0]) =>
                  cls.title.toLowerCase().includes(linkingState.searchQuery.toLowerCase()) ||
                  cls.id.toLowerCase().includes(linkingState.searchQuery.toLowerCase())
                )
              : [];

            return (
              <div
                key={entity.id}
                data-testid={`entity-suggestion-row-${index}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px",
                  backgroundColor: "var(--canvas-bg-2)",
                  borderRadius: "var(--radius-md)",
                  borderLeft: "3px solid var(--cyan-500)",
                }}
              >
                {/* Entity info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, marginBottom: "4px" }}>
                    {entity.label}
                  </div>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
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
                      {(entity.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: "6px" }}>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleApprove(entity)}
                    disabled={isProcessing}
                    data-testid={`entity-review-approve-${entity.id}`}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleReject(entity.id)}
                    disabled={isProcessing}
                    data-testid={`entity-review-reject-${entity.id}`}
                  >
                    Reject
                  </Button>
                  <div style={{ position: "relative" }} ref={dropdownRef}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setLinkingState({
                          entityId: entity.id,
                          searchQuery: "",
                        })
                      }
                      disabled={isProcessing || linkingState?.entityId === entity.id}
                      data-testid={`entity-review-link-${entity.id}`}
                    >
                      Link
                      {linkingState?.entityId === entity.id && (
                        <ChevronDown
                          size={14}
                          style={{
                            marginLeft: "4px",
                            transform: "rotate(180deg)",
                          }}
                        />
                      )}
                    </Button>

                    {linkingState?.entityId === entity.id && (
                      <div
                        style={{
                          position: "absolute",
                          top: "100%",
                          right: 0,
                          background: "var(--canvas-bg)",
                          border: "1px solid var(--canvas-fg-4)",
                          borderRadius: "var(--radius-sm)",
                          marginTop: "4px",
                          zIndex: 10,
                          minWidth: "200px",
                          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
                        }}
                      >
                        <div style={{ padding: "8px" }}>
                          <Input
                            type="text"
                            placeholder="Search classes..."
                            value={linkingState.searchQuery}
                            onChange={(e) => {
                              setLinkingState({
                                ...linkingState,
                                searchQuery: e.target.value,
                              });
                            }}
                            data-testid="entity-review-link-input"
                            style={{ marginBottom: "8px" }}
                          />
                          {filteredClasses.length > 0 ? (
                            <div
                              style={{
                                maxHeight: "200px",
                                overflowY: "auto",
                              }}
                            >
                              {filteredClasses.map((cls: typeof availableClasses[0]) => (
                                <button
                                  key={cls.id}
                                  type="button"
                                  onClick={() => handleLinkConfirm(entity, cls.id)}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "var(--space-2)",
                                    padding: "var(--space-2) var(--space-3)",
                                    width: "100%",
                                    background: "none",
                                    border: "none",
                                    cursor: "pointer",
                                    textAlign: "left",
                                    fontSize: "var(--text-sm)",
                                    color: "var(--canvas-fg)",
                                    borderBottom: "1px solid var(--canvas-fg-4)",
                                  }}
                                  data-testid={`entity-review-link-option-${cls.id}`}
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
                              No classes found
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Close linking */}
                {linkingState?.entityId === entity.id && (
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
          })}
        </div>
      </Panel>
    </div>
  );
}
