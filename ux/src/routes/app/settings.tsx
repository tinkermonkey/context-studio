import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Folder, Cpu, Layers, Type, Database, RefreshCw } from "lucide-react";
import { useConfig, useUpdateConfig } from "@/api/hooks/admin";
import { useToasts } from "@/components/ui/Toast";
import { Skeleton } from "@/components/ui/Skeleton";
import { ConfigTile } from "@/components/settings/ConfigTile";
import { EditConfigModal, type ConfigField } from "@/components/settings/EditConfigModal";
import { COPY } from "./settings/copy";

export const Route = createFileRoute("/app/settings")({
  component: SettingsPage,
});

export function SettingsPage() {
  const navigate = useNavigate();
  const { toast } = useToasts();
  const { data: config, isLoading } = useConfig();
  const updateMutation = useUpdateConfig();

  const [openSection, setOpenSection] = useState<string | null>(null);

  const handleUpdateSection = async (section: string, updates: { [key: string]: unknown }) => {
    await updateMutation.mutateAsync({ section, data: { updates } });
    toast("success", COPY.settingsUpdatedSuccess(section));
  };

  if (isLoading) {
    return (
      <div data-testid="settings-page">
        <div className="page-head">
          <Skeleton height={60} width={400} />
          <Skeleton height={20} width={300} style={{ marginTop: "8px" }} />
        </div>
        <div className="config-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height={180} />
          ))}
        </div>
      </div>
    );
  }

  const sections = config?.sections || {};

  // Workspace section
  const workspaceConfig = sections.workspace || {};
  const workspaceFields: ConfigField[] = [
    {
      key: "display_name",
      label: COPY.workspaceDisplayNameLabel,
      placeholder: COPY.workspaceDisplayNamePlaceholder,
      required: true,
    },
    {
      key: "path",
      label: COPY.workspacePathLabel,
      readOnly: true,
    },
  ];

  // LLM Provider section
  const llmConfig = sections.llm || {};
  const llmFields: ConfigField[] = [
    {
      key: "provider",
      label: COPY.llmProviderLabel,
      options: [
        { label: COPY.llmProviderAnthropicOption, value: "anthropic" },
        { label: COPY.llmProviderOpenAIOption, value: "openai" },
        { label: COPY.llmProviderOllamaOption, value: "ollama" },
      ],
      required: true,
    },
    {
      key: "model",
      label: COPY.llmModelLabel,
      placeholder: COPY.llmModelPlaceholder,
      required: true,
    },
    {
      key: "api_key",
      label: COPY.llmApiKeyLabel,
      type: "password",
      sensitive: true,
      placeholder: COPY.llmApiKeyPlaceholder,
    },
    ...(llmConfig.provider === "ollama"
      ? [
          {
            key: "base_url",
            label: COPY.llmBaseUrlLabel,
            type: "url",
            placeholder: COPY.llmBaseUrlPlaceholder,
          } as ConfigField,
        ]
      : []),
  ];

  // Embedding Model section
  const embeddingConfig = sections.embedding || {};
  const embeddingFields: ConfigField[] = [
    {
      key: "model_name",
      label: COPY.embeddingModelNameLabel,
      placeholder: COPY.embeddingModelNamePlaceholder,
      required: true,
    },
    {
      key: "vector_dimensions",
      label: COPY.embeddingVectorDimensionsLabel,
      type: "number",
      readOnly: true,
    },
  ];

  // NLP Model section
  const nlpConfig = sections.nlp || {};
  const nlpFields: ConfigField[] = [
    {
      key: "model_name",
      label: COPY.nlpModelNameLabel,
      placeholder: COPY.nlpModelNamePlaceholder,
      required: true,
    },
  ];

  // Sync Target section
  const syncConfig = sections.sync || {};
  const syncFields: ConfigField[] = [
    {
      key: "target_type",
      label: COPY.syncTargetTypeLabel,
      options: [
        { label: COPY.syncTargetTypeLocalOption, value: "local" },
        { label: COPY.syncTargetTypeS3Option, value: "s3" },
      ],
      required: true,
    },
    {
      key: "path",
      label: syncConfig.target_type === "s3" ? COPY.syncTargetS3BucketLabel : COPY.syncTargetPathLabel,
      placeholder: syncConfig.target_type === "s3" ? COPY.syncTargetS3BucketPlaceholder : COPY.syncTargetPathPlaceholder,
    },
    ...(syncConfig.target_type === "s3"
      ? [
          {
            key: "aws_access_key_id",
            label: COPY.syncTargetAwsAccessKeyLabel,
            type: "password",
            sensitive: true,
          } as ConfigField,
          {
            key: "aws_secret_access_key",
            label: COPY.syncTargetAwsSecretKeyLabel,
            type: "password",
            sensitive: true,
          } as ConfigField,
        ]
      : []),
  ];

  const referenceSourcesCount =
    (Array.isArray(sections.reference_sources) ? sections.reference_sources.length : 0) || 0;

  return (
    <div data-testid="settings-page">
      {/* Page Header */}
      <div className="page-head">
        <div>
          <h1>{COPY.settingsPageTitle}</h1>
          <p>{COPY.settingsPageSubtitle}</p>
        </div>
      </div>

      {/* Config Tiles Grid */}
      <div className="config-grid">
        {/* Workspace */}
        <ConfigTile
          icon={Folder}
          title={COPY.workspaceTileTitle}
          description={COPY.workspaceTileDescription}
          summary={
            <span>
              {String(workspaceConfig.display_name || COPY.workspaceUnnamed)}
              {workspaceConfig.path ? (
                <>
                  <br />
                  <span className="config-tile-meta">
                    {String(workspaceConfig.path)}
                  </span>
                </>
              ) : null}
            </span>
          }
          testid="config-tile-workspace"
          onEdit={() => setOpenSection("workspace")}
          isLoading={isLoading}
        />

        {/* LLM Provider */}
        <ConfigTile
          icon={Cpu}
          title={COPY.llmProviderTileTitle}
          description={COPY.llmProviderTileDescription}
          summary={
            <span>
              {llmConfig.provider ? (
                <>
                  {String(llmConfig.provider).charAt(0).toUpperCase() + String(llmConfig.provider).slice(1)}
                  <br />
                  <span className="config-tile-meta">
                    {String(llmConfig.model || COPY.notConfigured)}
                  </span>
                </>
              ) : (
                COPY.notConfigured
              )}
            </span>
          }
          testid="config-tile-llm"
          onEdit={() => setOpenSection("llm")}
          isLoading={isLoading}
        />

        {/* Embedding Model */}
        <ConfigTile
          icon={Layers}
          title={COPY.embeddingModelTileTitle}
          description={COPY.embeddingModelTileDescription}
          summary={
            <span>
              {String(embeddingConfig.model_name || COPY.notConfigured)}
              {embeddingConfig.vector_dimensions ? (
                <>
                  <br />
                  <span className="config-tile-meta">
                    {COPY.embeddingDimensionsMeta(Number(embeddingConfig.vector_dimensions))}
                  </span>
                </>
              ) : null}
            </span>
          }
          testid="config-tile-embedding"
          onEdit={() => setOpenSection("embedding")}
          isLoading={isLoading}
        />

        {/* NLP Model */}
        <ConfigTile
          icon={Type}
          title={COPY.nlpModelTileTitle}
          description={COPY.nlpModelTileDescription}
          summary={
            <span>{String(nlpConfig.model_name || COPY.notConfigured)}</span>
          }
          testid="config-tile-nlp"
          onEdit={() => setOpenSection("nlp")}
          isLoading={isLoading}
        />

        {/* Reference Sources */}
        <ConfigTile
          icon={Database}
          title={COPY.referenceSourcesTileTitle}
          description={COPY.referenceSourcesTileDescription}
          summary={<span>{COPY.referenceSourcesMeta(referenceSourcesCount)}</span>}
          testid="config-tile-reference-sources"
          onNavigate={() => navigate({ to: "/app/reference/sources" })}
          isLoading={isLoading}
        />

        {/* Sync Target */}
        <ConfigTile
          icon={RefreshCw}
          title={COPY.syncTargetTileTitle}
          description={COPY.syncTargetTileDescription}
          summary={
            <span style={{ color: syncConfig.path ? undefined : "var(--canvas-fg-3)" }}>
              {String(syncConfig.path || COPY.notConfigured)}
            </span>
          }
          testid="config-tile-sync"
          onEdit={() => setOpenSection("sync")}
          isLoading={isLoading}
        />
      </div>

      {/* Modals */}
      <EditConfigModal
        open={openSection === "workspace"}
        onClose={() => setOpenSection(null)}
        section="workspace"
        title={COPY.editWorkspaceSettingsTitle}
        fields={workspaceFields}
        values={workspaceConfig}
        onSave={(updates) => handleUpdateSection("workspace", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "llm"}
        onClose={() => setOpenSection(null)}
        section="llmprovider"
        title={COPY.editLlmProviderSettingsTitle}
        fields={llmFields}
        values={llmConfig}
        onSave={(updates) => handleUpdateSection("llm", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "embedding"}
        onClose={() => setOpenSection(null)}
        section="embedding"
        title={COPY.editEmbeddingModelSettingsTitle}
        fields={embeddingFields}
        values={embeddingConfig}
        onSave={(updates) => handleUpdateSection("embedding", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "nlp"}
        onClose={() => setOpenSection(null)}
        section="nlp"
        title={COPY.editNlpModelSettingsTitle}
        fields={nlpFields}
        values={nlpConfig}
        onSave={(updates) => handleUpdateSection("nlp", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "sync"}
        onClose={() => setOpenSection(null)}
        section="sync"
        title={COPY.editSyncTargetSettingsTitle}
        fields={syncFields}
        values={syncConfig}
        onSave={(updates) => handleUpdateSection("sync", updates)}
        isLoading={updateMutation.isPending}
      />
    </div>
  );
}
