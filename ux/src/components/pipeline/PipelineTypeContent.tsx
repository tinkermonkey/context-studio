import { useState } from "react";
import { Button, Icon, Chip, VersionPill } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";
import { ConfigEditor } from "./ConfigEditor";
import type { components } from "@/api/types";
import "./PipelineTypeDetail.css";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type EditorMode = "view" | "edit" | "create";

interface PipelineTypeContentProps {
  pipelineType: string;
}

export function PipelineTypeContent({ pipelineType }: PipelineTypeContentProps) {
  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<EditorMode>("view");
  const [draftKey, setDraftKey] = useState(0);

  const { data: implementations } = usePipelineImplementations(pipelineType);
  const implId = implementations?.[0]?.id ?? "";

  const {
    data: configurations,
    isLoading: configLoading,
    error: configError,
    refetch: refetchConfig,
  } = usePipelineConfigurations(pipelineType, implId);

  const selectedConfig: PipelineConfigurationResponse | null =
    selectedConfigId && configurations
      ? (configurations.find((c) => c.id === selectedConfigId) ?? null)
      : null;

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

  const showEditor = editorMode === "create" || selectedConfig !== null;

  return (
    <div
      className={`pipeline-type-content-layout ${showEditor ? "has-editor" : ""}`}
      data-testid={`pipeline-type-content-${pipelineType}`}
    >
      {/* Configs list */}
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
              data-testid={`pipeline-new-config-btn-${pipelineType}`}
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

      {/* Editor */}
      {showEditor && implId && (
        <ConfigEditor
          key={editorMode === "create" ? `create-${draftKey}` : `${selectedConfigId}-${editorMode}`}
          pipelineType={pipelineType}
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
  );
}
