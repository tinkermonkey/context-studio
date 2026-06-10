import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useRunPipeline } from "@/api/hooks/pipeline/usePipelineMutations";
import { usePipelineRun } from "@/api/hooks/pipeline/usePipelineRuns";
import { useCreateRelationship } from "@/api/hooks/ontology/useRelationships";
import { useToasts } from "@/components/ui/Toast";
import type { SchemaNodeConnectionRefinementOutputSummary, Delta } from "@/api/hooks/pipeline/outputSummaryTypes";
import "./Suggesters.css";

interface RelationshipSuggesterProps {
  classId: string;
}

function getDeltaKey(delta: Delta): string {
  return `${delta.source_id}:${delta.relationship_type}:${delta.target_id}`;
}

export function RelationshipSuggester({ classId }: RelationshipSuggesterProps) {
  const [runId, setRunId] = useState<string | null>(null);
  const [dismissedKeys, setDismissedKeys] = useState<Set<string>>(new Set());
  const [acceptingKey, setAcceptingKey] = useState<string | null>(null);

  const runMutation = useRunPipeline();
  const createRelationship = useCreateRelationship();
  const { toast } = useToasts();
  const { data: run } = usePipelineRun(runId ?? "");

  const isRunning =
    runMutation.isPending ||
    run?.status === "PENDING" ||
    run?.status === "RUNNING";
  const isCompleted = run?.status === "COMPLETED";

  const outputSummary = isCompleted
    ? (run?.output_summary as SchemaNodeConnectionRefinementOutputSummary | null)
    : null;

  const visibleDeltas = (outputSummary?.deltas ?? [])
    .filter((d) => d.operation === "add")
    .filter((d) => !dismissedKeys.has(getDeltaKey(d)));

  const handleSuggest = async () => {
    setRunId(null);
    setDismissedKeys(new Set());
    try {
      const result = await runMutation.mutateAsync({
        type: "schema_node_connection_refinement",
        request: {
          implementation_id: "default",
          configuration_ref: "default",
          node_id: classId,
        },
      });
      setRunId(result.id);
    } catch {
      // error visible via toast from mutation
    }
  };

  const handleAccept = async (delta: Delta) => {
    const key = getDeltaKey(delta);
    setAcceptingKey(key);
    try {
      await createRelationship.mutateAsync({
        source_id: delta.source_id,
        target_id: delta.target_id,
        relationship_type: delta.relationship_type,
      });
      setDismissedKeys((prev) => new Set([...prev, key]));
      toast("success", "Relationship created");
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to create relationship");
    } finally {
      setAcceptingKey(null);
    }
  };

  const handleDismiss = (delta: Delta) => {
    setDismissedKeys((prev) => new Set([...prev, getDeltaKey(delta)]));
  };

  const hasRun = isCompleted || isRunning;

  return (
    <div className="relationship-suggester" data-testid="relationship-suggester">
      {!hasRun && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void handleSuggest()}
          data-testid="relationship-suggester-btn"
        >
          ✦ Suggest relationships
        </Button>
      )}

      {isRunning && (
        <div className="relationship-suggester-shimmer" data-testid="relationship-suggester-loading">
          <div className="skeleton" style={{ height: 72 }} />
          <div className="skeleton" style={{ height: 72 }} />
        </div>
      )}

      {isCompleted && visibleDeltas.length === 0 && (
        <>
          <p className="relationship-suggester-empty">No relationship suggestions available</p>
          <div className="relationship-suggester-footer">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleSuggest()}
              data-testid="relationship-suggester-retry-btn"
            >
              ✦ Suggest again
            </Button>
          </div>
        </>
      )}

      {isCompleted && visibleDeltas.length > 0 && (
        <>
          {visibleDeltas.map((delta) => {
            const key = getDeltaKey(delta);
            const isAccepting = acceptingKey === key;
            return (
              <div
                key={key}
                className="relationship-suggestion-card"
                data-testid={`relationship-suggestion-${key}`}
              >
                <div className="relationship-suggestion-triple">
                  <span className="relationship-suggestion-source">
                    {delta.source_label || delta.source_id.slice(0, 8)}
                  </span>
                  <span className="relationship-suggestion-predicate">
                    {delta.relationship_type}
                  </span>
                  <span className="relationship-suggestion-target">
                    {delta.target_label || delta.target_id.slice(0, 8)}
                  </span>
                </div>
                <div className="relationship-suggestion-confidence">
                  <div
                    className="relationship-suggestion-confidence-fill"
                    style={{ width: `${delta.confidence * 100}%` }}
                    aria-label={`${(delta.confidence * 100).toFixed(0)}% confidence`}
                  />
                </div>
                <div className="relationship-suggestion-meta">
                  <span>{(delta.confidence * 100).toFixed(0)}% confidence</span>
                  <span>·</span>
                  <span>{delta.source}</span>
                </div>
                <div className="relationship-suggestion-actions">
                  <button
                    type="button"
                    className="relationship-suggestion-accept-btn"
                    onClick={() => void handleAccept(delta)}
                    disabled={isAccepting}
                    data-testid={`relationship-accept-${key}`}
                  >
                    {isAccepting ? "Creating…" : "Accept"}
                  </button>
                  <button
                    type="button"
                    className="relationship-suggestion-dismiss-btn"
                    onClick={() => handleDismiss(delta)}
                    data-testid={`relationship-dismiss-${key}`}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            );
          })}
          <div className="relationship-suggester-footer">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleSuggest()}
              data-testid="relationship-suggester-retry-btn"
            >
              ✦ Suggest again
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
