import { useState } from "react";
import { Button, Chip, Field, Icon, Select, VersionPill } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";
import type { PipelineConfiguration } from "@/api/services/pipeline";
import { ConfigEditor } from "./ConfigEditor";
import "./PipelineTypeContent.css";

type EditorMode = "view" | "edit" | "create";

/** What the page shows of a pipeline type: an implementation and one of its configurations. */
export interface PipelineTypeSelection {
  impl?: string;
  config?: string;
}

interface PipelineTypeContentProps {
  pipelineType: string;
  /** The implementation to show; the type's default implementation when not given. */
  implementationId?: string;
  /** The config_ref of the configuration open in the editor. */
  configRef?: string;
  onSelect: (selection: PipelineTypeSelection) => void;
  /** Open the type's run wizard; not given for a type without one. */
  onRun?: () => void;
}

/**
 * The configurations of a pipeline type, one implementation at a time: see,
 * create and edit them, with the default implementation and each
 * implementation's default configuration marked as the API reports them.
 */
export function PipelineTypeContent({
  pipelineType,
  implementationId,
  configRef,
  onSelect,
  onRun,
}: PipelineTypeContentProps) {
  const [editorMode, setEditorMode] = useState<EditorMode>("view");
  const [draftKey, setDraftKey] = useState(0);

  const {
    data: implementations,
    error: implementationsError,
    refetch: refetchImplementations,
  } = usePipelineImplementations(pipelineType);
  const implementation =
    implementations?.find((i) => i.id === implementationId) ??
    implementations?.find((i) => i.is_default);
  const implId = implementation?.id ?? "";

  const {
    data: configurations,
    isLoading: configLoading,
    error: configError,
    refetch: refetchConfig,
  } = usePipelineConfigurations(pipelineType, implId);

  const selectedConfig: PipelineConfiguration | null =
    (editorMode !== "create" && configurations?.find((c) => c.config_ref === configRef)) || null;
  const defaultConfig = configurations?.find((c) => c.is_default) ?? null;

  const openConfig = (config: PipelineConfiguration) => {
    setEditorMode("view");
    onSelect({ impl: implId, config: config.config_ref });
  };

  const handleNewConfig = () => {
    setEditorMode("create");
    setDraftKey((k) => k + 1);
    onSelect({ impl: implId });
  };

  const showEditor = editorMode === "create" || selectedConfig !== null;
  const selectId = `pipeline-implementation-${pipelineType}`;

  return (
    <div className="pipeline-type-content" data-testid={`pipeline-type-content-${pipelineType}`}>
      {implementationsError && (
        <ErrorBanner
          error={implementationsError}
          onRetry={() => refetchImplementations()}
          message="Failed to load implementations"
        />
      )}

      <div className="pipeline-type-toolbar">
        <Field label="Implementation" htmlFor={selectId}>
          <div className="pipeline-type-toolbar__implementation">
            <Select
              id={selectId}
              value={implId}
              onChange={(id) => {
                setEditorMode("view");
                onSelect({ impl: id });
              }}
              placeholder="Choose an implementation"
              ariaLabel="Implementation"
              disabled={!implementations?.length}
              data-testid="pipeline-implementation"
            >
              {(implementations ?? []).map((i) => (
                <Select.Item
                  key={i.id}
                  value={i.id}
                  description={i.is_default ? "Default implementation" : undefined}
                >
                  {i.id}
                </Select.Item>
              ))}
            </Select>
            {implementation?.is_default && (
              <Chip variant="cyan" data-testid="pipeline-implementation-default">
                default
              </Chip>
            )}
          </div>
        </Field>
        {onRun && (
          <Button
            variant="primary"
            size="sm"
            onClick={onRun}
            aria-label={`Run ${pipelineType}`}
            data-testid="pipeline-run-btn"
          >
            <Icon name="zap" size={13} /> Run
          </Button>
        )}
      </div>

      {implId && (
        <div className="pipeline-type-content-layout">
          <div className="pipeline-cfg-list-col">
            <div className="pipeline-cfg-list-header">
              <span className="cfg-section-title cfg-section-title--flush">
                Configurations · {configurations?.length ?? 0}
              </span>
              <Button
                variant="ghost"
                size="sm"
                icon
                onClick={handleNewConfig}
                title="New configuration"
                aria-label={`New configuration of ${implId}`}
                data-testid="pipeline-new-config-btn"
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

            {!configLoading && !!configurations?.length && (
              <div
                className="pipeline-cfg-list"
                role="listbox"
                aria-label={`Configurations of ${implId}`}
                data-testid="pipeline-cfg-list"
              >
                {configurations.map((cfg) => {
                  const isActive = cfg.id === selectedConfig?.id;
                  return (
                    <button
                      key={cfg.id}
                      className={`pipeline-cfg-row ${isActive ? "pipeline-cfg-row--active" : ""}`}
                      onClick={() => openConfig(cfg)}
                      role="option"
                      aria-selected={isActive}
                      data-testid={`pipeline-cfg-row-${cfg.config_ref}`}
                    >
                      <span
                        className={`pipeline-cfg-dot ${cfg.enabled ? "pipeline-cfg-dot--enabled" : "pipeline-cfg-dot--disabled"}`}
                      />
                      <span className="pipeline-cfg-body">
                        <span className="pipeline-cfg-name">{cfg.name}</span>
                        <span className="pipeline-cfg-model">
                          {cfg.provider} · {cfg.model}
                        </span>
                      </span>
                      <span className="pipeline-cfg-badges">
                        {cfg.is_default && <Chip variant="cyan">default</Chip>}
                        {cfg.is_system && <Chip variant="neutral">system</Chip>}
                        <VersionPill>{cfg.version}</VersionPill>
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {showEditor ? (
            <ConfigEditor
              key={
                editorMode === "create"
                  ? `create-${draftKey}`
                  : `${selectedConfig?.id}-${editorMode}`
              }
              pipelineType={pipelineType}
              implId={implId}
              config={selectedConfig}
              template={defaultConfig}
              mode={editorMode}
              onEnterEdit={() => setEditorMode("edit")}
              onDone={() => setEditorMode("view")}
              onCreated={openConfig}
              onDuplicate={openConfig}
              onCancel={() => setEditorMode("view")}
              onDeleted={() => {
                setEditorMode("view");
                onSelect({ impl: implId });
              }}
            />
          ) : (
            <div
              className="pipeline-cfg-empty-inspector"
              data-testid="pipeline-cfg-empty-inspector"
            >
              <Icon name="settings" size={32} />
              <p>Select a configuration or create a new one.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
