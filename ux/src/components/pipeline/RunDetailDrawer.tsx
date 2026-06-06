import { useState } from "react";
import { Loader, AlertCircle, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { InspectorPanel, KVGrid, Chip, Button } from "@tinkermonkey/heimdall-ui";
import { usePipelineRun } from "@/api/hooks/pipeline/usePipelineRuns";
import { formatDate } from "@/utils/dateFormatting";
import {
  SchemaExtractionReview,
  IndividualExtractionReview,
  GroundingReview,
  DefinitionRefinementReview,
  ConnectionRefinementReview,
} from "./review";
import { RunApplyControls } from "./RunApplyControls";
import { RunRevertControls } from "./RunRevertControls";
import type {
  SchemaExtractionOutputSummary,
  IndividualExtractionOutputSummary,
  SchemaNodeGroundingOutputSummary,
  SchemaNodeDefinitionRefinementOutputSummary,
  SchemaNodeConnectionRefinementOutputSummary,
} from "@/api/hooks/pipeline/outputSummaryTypes";
import type { components } from "@/api/types";
import "./RunDetailDrawer.css";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];
type ApplyRunResponse = components["schemas"]["ApplyRunResponse"];
type RevertRunResponse = components["schemas"]["RevertRunResponse"];

interface RunDetailDrawerProps {
  runId: string;
  onClose?: () => void;
}

export function RunDetailDrawer({ runId, onClose }: RunDetailDrawerProps) {
  const queryClient = useQueryClient();

  const { data: run, isLoading, error } = usePipelineRun(runId);

  // Selection state for SchemaExtractionReview
  const [selectedClasses, setSelectedClasses] = useState<(string | number)[]>([]);
  const [selectedProperties, setSelectedProperties] = useState<(string | number)[]>([]);
  const [selectedRelationships, setSelectedRelationships] = useState<(string | number)[]>([]);

  // Selection state for IndividualExtractionReview
  const [selectedTriples, setSelectedTriples] = useState<(string | number)[]>([]);

  // Selection state for GroundingReview
  const [candidateStatus, setCandidateStatus] = useState<
    Record<string, "pending" | "accepted" | "rejected">
  >({});

  // Selection state for DefinitionRefinementReview
  const [selectedOption, setSelectedOption] = useState<"current" | number>("current");

  // Selection state for ConnectionRefinementReview
  const [activeOperation, setActiveOperation] = useState<"add" | "remove" | "modify">("add");
  const [deltaStatus, setDeltaStatus] = useState<
    Record<string, "pending" | "accepted" | "rejected">
  >({});

  // Apply/revert state from React Query cache
  const getCachedApplyStatus = () => {
    return (
      queryClient.getQueryData<{
        applyResult: ApplyRunResponse | null;
        revertResult: RevertRunResponse | null;
        isReverted: boolean;
      }>(["pipeline-runs", runId, "apply-status"]) || {
        applyResult: null,
        revertResult: null,
        isReverted: false,
      }
    );
  };

  const setCachedApplyStatus = (status: {
    applyResult: ApplyRunResponse | null;
    revertResult: RevertRunResponse | null;
    isReverted: boolean;
  }) => {
    queryClient.setQueryData(["pipeline-runs", runId, "apply-status"], status);
  };

  const cachedStatus = getCachedApplyStatus();
  const applyResult = cachedStatus.applyResult;
  const revertResult = cachedStatus.revertResult;
  const isReverted = cachedStatus.isReverted;

  const closeButton = onClose && (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClose}
      aria-label="Close run details"
      data-testid="run-detail-close-button"
    >
      <X size={16} />
    </Button>
  );

  if (isLoading) {
    return (
      <InspectorPanel
        eyebrow="run"
        title="Loading…"
        id="loading"
        data-testid="run-detail-drawer"
        actions={closeButton}
      >
        <div className="run-detail-loading">
          <Loader size={20} className="spin" />
        </div>
      </InspectorPanel>
    );
  }

  if (error || !run) {
    return (
      <InspectorPanel
        eyebrow="run"
        title="Error"
        id="error"
        data-testid="run-detail-drawer"
        actions={closeButton}
      >
        <div className="run-detail-error">
          <AlertCircle size={16} className="run-detail-error-icon" />
          Failed to load run details
        </div>
      </InspectorPanel>
    );
  }

  const pipelineTypeDisplay = run.pipeline_type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  const statusColorMap: Record<
    string,
    "emerald" | "amber" | "rose" | "cyan" | "violet" | "neutral"
  > = {
    PENDING: "amber",
    RUNNING: "cyan",
    COMPLETED: "emerald",
    FAILED: "rose",
  };

  const metadataRows = [
    { key: "ID", value: <span className="run-detail-id">{run.id}</span> },
    { key: "Type", value: pipelineTypeDisplay },
    { key: "Implementation", value: run.configuration_slug || "—" },
    { key: "Configuration", value: `${run.configuration_ref} (v${run.configuration_version})` },
    {
      key: "Status",
      value: <Chip variant={statusColorMap[run.status] || "neutral"}>{run.status}</Chip>,
    },
    { key: "Started", value: formatDate(run.started_at) },
    { key: "Updated", value: formatDate(run.updated_at) },
  ];

  const renderReviewComponent = (runData: PipelineRunResponse) => {
    const outputSummary = runData.output_summary;

    switch (runData.pipeline_type) {
      case "schema_extraction":
        return (
          <SchemaExtractionReview
            outputSummary={outputSummary as SchemaExtractionOutputSummary}
            selectedClasses={selectedClasses}
            onSelectClasses={setSelectedClasses}
            selectedProperties={selectedProperties}
            onSelectProperties={setSelectedProperties}
            selectedRelationships={selectedRelationships}
            onSelectRelationships={setSelectedRelationships}
          />
        );
      case "individual_extraction":
        return (
          <IndividualExtractionReview
            outputSummary={outputSummary as IndividualExtractionOutputSummary}
            selectedTriples={selectedTriples}
            onSelectTriples={setSelectedTriples}
          />
        );
      case "schema_node_grounding":
        return (
          <GroundingReview
            outputSummary={outputSummary as SchemaNodeGroundingOutputSummary}
            candidateStatus={candidateStatus}
            onCandidateStatusChange={setCandidateStatus}
          />
        );
      case "schema_node_definition_refinement":
        return (
          <DefinitionRefinementReview
            outputSummary={outputSummary as SchemaNodeDefinitionRefinementOutputSummary}
            selectedOption={selectedOption}
            onSelectOption={setSelectedOption}
          />
        );
      case "schema_node_connection_refinement":
        return (
          <ConnectionRefinementReview
            outputSummary={outputSummary as SchemaNodeConnectionRefinementOutputSummary}
            activeOperation={activeOperation}
            onOperationChange={setActiveOperation}
            deltaStatus={deltaStatus}
            onDeltaStatusChange={setDeltaStatus}
          />
        );
      default:
        return (
          <div className="run-detail-placeholder">
            Unknown pipeline type: {runData.pipeline_type}
          </div>
        );
    }
  };

  return (
    <InspectorPanel
      eyebrow="run"
      title={pipelineTypeDisplay}
      id={run.id}
      data-testid="run-detail-drawer"
      actions={closeButton}
    >
      <InspectorPanel.Section title="Metadata">
        <KVGrid rows={metadataRows} />
      </InspectorPanel.Section>

      {run.status === "FAILED" && run.failure_reason && (
        <InspectorPanel.Section title="Error">
          <div className="run-detail-failure-reason" data-testid="run-failure-reason">
            {run.failure_reason}
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "COMPLETED" && (
        <InspectorPanel.Section title="Results">
          <div className="run-detail-results-section" data-testid="run-completed-section">
            <div className="run-detail-results-item">
              <strong>Review</strong>
              <div className="run-detail-results-item-content">{renderReviewComponent(run)}</div>
            </div>

            <div className="run-detail-results-item">
              <strong>Apply</strong>
              <div className="run-detail-apply-section" data-testid="run-apply-section">
                <div className="run-detail-apply-controls">
                  <RunApplyControls
                    run={run}
                    pipelineType={run.pipeline_type}
                    outputSummary={run.output_summary}
                    selectedCandidates={{
                      classes: selectedClasses,
                      properties: selectedProperties,
                      relationships: selectedRelationships,
                      individuals: selectedTriples,
                      groundingCandidates: Object.entries(candidateStatus)
                        .filter(([, status]) => status === "accepted")
                        .map(([key]) => key),
                      refinementCandidates:
                        run.pipeline_type === "schema_node_definition_refinement"
                          ? selectedOption === "current"
                            ? []
                            : [`definition-${selectedOption}`]
                          : Object.entries(deltaStatus)
                              .filter(([, status]) => status === "accepted")
                              .map(([key]) => key),
                    }}
                    isApplied={!!applyResult}
                    onApplySuccess={(result) => {
                      setCachedApplyStatus({
                        applyResult: result,
                        revertResult: null,
                        isReverted: false,
                      });
                    }}
                  />
                </div>

                {applyResult && (
                  <div className="run-detail-apply-result" data-testid="run-apply-result">
                    <div className="apply-result-header">
                      <span className="apply-result-status">✓ Applied</span>
                    </div>

                    <div className="apply-result-grid">
                      {applyResult.classes_created > 0 && (
                        <div className="apply-result-item">
                          <span className="item-count">{applyResult.classes_created}</span>
                          <span className="item-label">
                            {applyResult.classes_created === 1
                              ? "Class created"
                              : "Classes created"}
                          </span>
                        </div>
                      )}

                      {applyResult.classes_updated > 0 && (
                        <div className="apply-result-item">
                          <span className="item-count">{applyResult.classes_updated}</span>
                          <span className="item-label">
                            {applyResult.classes_updated === 1
                              ? "Class updated"
                              : "Classes updated"}
                          </span>
                        </div>
                      )}

                      {applyResult.properties_created > 0 && (
                        <div className="apply-result-item">
                          <span className="item-count">{applyResult.properties_created}</span>
                          <span className="item-label">
                            {applyResult.properties_created === 1
                              ? "Property created"
                              : "Properties created"}
                          </span>
                        </div>
                      )}

                      {(applyResult.relationships_created || 0) +
                        (applyResult.relationships_modified || 0) >
                        0 && (
                        <div className="apply-result-item">
                          <span className="item-count">
                            {(applyResult.relationships_created || 0) +
                              (applyResult.relationships_modified || 0)}
                          </span>
                          <span className="item-label">Relationships affected</span>
                        </div>
                      )}

                      {applyResult.individuals_created > 0 && (
                        <div className="apply-result-item">
                          <span className="item-count">{applyResult.individuals_created}</span>
                          <span className="item-label">
                            {applyResult.individuals_created === 1
                              ? "Individual created"
                              : "Individuals created"}
                          </span>
                        </div>
                      )}

                      {applyResult.external_references_created > 0 && (
                        <div className="apply-result-item">
                          <span className="item-count">
                            {applyResult.external_references_created}
                          </span>
                          <span className="item-label">External references added</span>
                        </div>
                      )}
                    </div>

                    {applyResult.created_class_ids && applyResult.created_class_ids.length > 0 && (
                      <div className="apply-result-sample-ids">
                        <span className="sample-ids-label">Sample IDs:</span>
                        <div className="sample-ids-list">
                          {applyResult.created_class_ids.slice(0, 3).map((id, idx) => (
                            <code key={idx} className="sample-id" title={id}>
                              {id}
                            </code>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="run-detail-revert-controls">
                      <RunRevertControls
                        run={run}
                        applyResult={applyResult}
                        isReverted={isReverted}
                        onRevertSuccess={(result) => {
                          setCachedApplyStatus({
                            applyResult,
                            revertResult: result,
                            isReverted: true,
                          });
                        }}
                      />
                    </div>
                  </div>
                )}

                {revertResult && (
                  <div className="run-detail-revert-result" data-testid="run-revert-result">
                    <div className="revert-result-header">
                      <span className="revert-result-status" data-testid="run-status-reverted">
                        ✓ Reverted
                      </span>
                    </div>

                    {revertResult.events_reverted === 0 ? (
                      <div className="revert-result-empty-message">
                        No changes to revert
                      </div>
                    ) : (
                      <div className="revert-result-grid">
                        {revertResult.classes_deleted > 0 && (
                          <div className="revert-result-item">
                            <span className="item-count">{revertResult.classes_deleted}</span>
                            <span className="item-label">
                              {revertResult.classes_deleted === 1
                                ? "Class removed"
                                : "Classes removed"}
                            </span>
                          </div>
                        )}

                        {revertResult.individuals_deleted > 0 && (
                          <div className="revert-result-item">
                            <span className="item-count">{revertResult.individuals_deleted}</span>
                            <span className="item-label">
                              {revertResult.individuals_deleted === 1
                                ? "Individual removed"
                                : "Individuals removed"}
                            </span>
                          </div>
                        )}

                        {revertResult.relationships_deleted > 0 && (
                          <div className="revert-result-item">
                            <span className="item-count">{revertResult.relationships_deleted}</span>
                            <span className="item-label">
                              {revertResult.relationships_deleted === 1
                                ? "Relationship removed"
                                : "Relationships removed"}
                            </span>
                          </div>
                        )}

                        {revertResult.properties_deleted > 0 && (
                          <div className="revert-result-item">
                            <span className="item-count">{revertResult.properties_deleted}</span>
                            <span className="item-label">
                              {revertResult.properties_deleted === 1
                                ? "Property removed"
                                : "Properties removed"}
                            </span>
                          </div>
                        )}

                        {revertResult.entities_restored > 0 && (
                          <div className="revert-result-item">
                            <span className="item-count">{revertResult.entities_restored}</span>
                            <span className="item-label">
                              {revertResult.entities_restored === 1
                                ? "Entity restored"
                                : "Entities restored"}
                            </span>
                          </div>
                        )}

                        {revertResult.events_reverted > 0 &&
                          revertResult.classes_deleted === 0 &&
                          revertResult.individuals_deleted === 0 &&
                          revertResult.relationships_deleted === 0 &&
                          revertResult.properties_deleted === 0 &&
                          revertResult.entities_restored === 0 && (
                            <div className="revert-result-empty-message">
                              {revertResult.events_reverted} change event
                              {revertResult.events_reverted === 1 ? "" : "s"} reverted
                            </div>
                          )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "PENDING" && (
        <InspectorPanel.Section title="Status">
          <div className="run-detail-pending-placeholder" data-testid="run-pending-placeholder">
            This run is pending execution
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "RUNNING" && (
        <InspectorPanel.Section title="Status">
          <div className="run-detail-running-placeholder" data-testid="run-running-placeholder">
            <Loader size={14} className="spin" />
            This run is currently executing
          </div>
        </InspectorPanel.Section>
      )}
    </InspectorPanel>
  );
}
