import { useState } from "react";
import { useParams, useNavigate } from "@tanstack/react-router";
import {
  PageHeader,
  Icon,
  Button,
  Panel,
  Chip,
  VersionPill,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";
import { ImplementationList } from "./ImplementationList";
import { ConfigEditor } from "./ConfigEditor";
import type { components } from "@/api/types";
import "./PipelineTypeDetail.css";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];

type EditorMode = "view" | "edit" | "create";

export function PipelineTypeDetail() {
  const { type } = useParams({ from: "/app/pipelines/types/$type" as any });
  const navigate = useNavigate();

  const [selectedImplId, setSelectedImplId] = useState<string | undefined>();
  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<EditorMode>("view");
  const [draftKey, setDraftKey] = useState(0);

  const {
    data: implementations,
    isLoading: implLoading,
    error: implError,
    refetch: refetchImpl,
  } = usePipelineImplementations(type);

  const implId = selectedImplId ?? (implementations?.[0]?.id ?? "");

  const {
    data: configurations,
    isLoading: configLoading,
    error: configError,
    refetch: refetchConfig,
  } = usePipelineConfigurations(type, implId);

  const selectedConfig: PipelineConfigurationResponse | null =
    selectedConfigId && configurations
      ? (configurations.find((c) => c.id === selectedConfigId) ?? null)
      : null;

  const handleSelectImplementation = (id: string) => {
    setSelectedImplId(id);
    setSelectedConfigId(null);
    setEditorMode("view");
  };

  const handleSelectConfig = (config: PipelineConfigurationResponse) => {
    setSelectedConfigId(config.id);
    setEditorMode("view");
  };

  const handleNewConfig = () => {
    setSelectedConfigId(null);
    setEditorMode("create");
    setDraftKey((k) => k + 1);
  };

  const handleCreated = (id: string) => {
    setSelectedConfigId(id);
    setEditorMode("view");
  };

  const handleDuplicated = (id: string) => {
    setSelectedConfigId(id);
    setEditorMode("view");
  };

  const handleDeleted = () => {
    setSelectedConfigId(null);
    setEditorMode("view");
  };

  if (implError) {
    return (
      <div data-testid="pipeline-type-detail-page">
        <PageHeader eyebrow="Pipelines" title={`Type: ${type}`} />
        <ErrorBanner
          error={implError}
          onRetry={() => refetchImpl()}
          message="Failed to load implementations"
        />
      </div>
    );
  }

  if (!implLoading && (!implementations || implementations.length === 0)) {
    return (
      <div data-testid="pipeline-type-detail-page">
        <PageHeader eyebrow="Pipelines" title={`Type: ${type}`} />
        <EmptyState
          title="No implementations found"
          description="This pipeline type has no registered implementations."
          icon={<Icon name="pipeline" size={48} />}
        />
      </div>
    );
  }

  const showEditor = editorMode === "create" || selectedConfig !== null;

  return (
    <div data-testid="pipeline-type-detail-page" className="pipeline-type-detail">
      <PageHeader
        eyebrow="Pipelines"
        title={`Type: ${type}`}
        subtitle="Select a configuration or create a new one"
        actions={
          implId ? (
            <Button
              variant="primary"
              onClick={handleNewConfig}
              data-testid="pipeline-new-config-btn"
            >
              <Icon name="plus" size={13} /> New configuration
            </Button>
          ) : undefined
        }
      />

      <div className="pipeline-detail-content">
        <div className={`pipeline-detail-layout ${showEditor ? "has-editor" : ""}`}>
          {/* Left: implementation list */}
          <ImplementationList
            implementations={implementations ?? []}
            selectedId={implId}
            onSelect={handleSelectImplementation}
            isLoading={implLoading}
            error={implError}
            onRetry={() => refetchImpl()}
          />

          {/* Center: configurations list */}
          {implId && (
            <div className="pipeline-cfg-list-col">
              <div className="pipeline-cfg-list-header">
                <span className="cfg-section-title" style={{ margin: 0 }}>
                  Configurations · {configurations?.length ?? 0}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  icon
                  onClick={handleNewConfig}
                  title="New configuration"
                  data-testid="pipeline-new-config-icon-btn"
                >
                  <Icon name="plus" size={13} />
                </Button>
              </div>

              {configLoading && (
                <div className="pipeline-cfg-skeletons">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="pipeline-cfg-skeleton" />
                  ))}
                </div>
              )}

              {configError && (
                <ErrorBanner
                  error={configError}
                  onRetry={() => refetchConfig()}
                  message="Failed to load configurations"
                />
              )}

              {!configLoading && !configError && configurations?.length === 0 && (
                <div className="pipeline-cfg-empty">No configurations yet.</div>
              )}

              {!configLoading &&
                configurations?.map((cfg) => {
                  const isActive = cfg.id === selectedConfigId && editorMode !== "create";
                  return (
                    <button
                      key={cfg.id}
                      className={`pipeline-cfg-row ${isActive ? "pipeline-cfg-row--active" : ""}`}
                      onClick={() => handleSelectConfig(cfg)}
                      data-testid={`pipeline-cfg-row-${cfg.config_ref}`}
                    >
                      <span
                        className="pipeline-cfg-dot"
                        style={{
                          background: cfg.enabled
                            ? "rgb(var(--status-emerald))"
                            : "rgb(var(--canvas-fg-4))",
                        }}
                      />
                      <span className="pipeline-cfg-body">
                        <span className="pipeline-cfg-name">{cfg.name}</span>
                        <span className="pipeline-cfg-model">
                          {cfg.provider} · {cfg.model}
                        </span>
                      </span>
                      <div className="pipeline-cfg-badges">
                        {cfg.is_system && <Chip variant="neutral">system</Chip>}
                        <VersionPill>{cfg.version}</VersionPill>
                      </div>
                    </button>
                  );
                })}
            </div>
          )}

          {/* Right: ConfigEditor */}
          {showEditor && implId && (
            <ConfigEditor
              key={
                editorMode === "create"
                  ? `create-${draftKey}`
                  : `${selectedConfigId}-${editorMode}`
              }
              pipelineType={type}
              implId={implId}
              config={selectedConfig}
              mode={editorMode}
              onEnterEdit={() => setEditorMode("edit")}
              onDone={() => setEditorMode("view")}
              onCreated={handleCreated}
              onDuplicate={handleDuplicated}
              onCancel={() => setEditorMode("view")}
              onDeleted={handleDeleted}
            />
          )}

          {!showEditor && implId && (
            <div
              className="pipeline-cfg-empty-inspector"
              data-testid="pipeline-cfg-empty-inspector"
            >
              <Icon name="settings" size={32} />
              <p>Select a configuration or create a new one.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
