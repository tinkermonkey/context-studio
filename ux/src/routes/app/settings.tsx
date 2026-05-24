import { PageHeader, ConfigTile, TabBar } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useConfig, useUpdateConfig } from "@/api/hooks/admin";
import { useToasts } from "@/components/ui/Toast";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EditConfigModal, type ConfigField } from "@/components/settings/EditConfigModal";
import { COPY } from "./settings/copy";

export const Route = createFileRoute("/app/settings")({
  component: SettingsPage,
});

export function SettingsPage() {
  const navigate = useNavigate();
  const { toast } = useToasts();
  const { data: config, isLoading, error, refetch } = useConfig();
  const updateMutation = useUpdateConfig();

  const [openSection, setOpenSection] = useState<string | null>(null);

  const handleUpdateSection = async (section: string, updates: { [key: string]: unknown }) => {
    try {
      await updateMutation.mutateAsync({ section, data: { updates } });
      toast("success", COPY.settingsUpdatedSuccess(section));
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : COPY.failedToSaveSettings;
      toast("error", errorMsg);
      throw error;
    }
  };

  if (isLoading) {
    return (
      <div data-testid="settings-page">
        <div style={{ marginBottom: "24px" }}>
          <Skeleton height={60} width={400} />
          <Skeleton height={20} width={300} style={{ marginTop: "8px" }} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height={180} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="settings-page">
        <PageHeader
          eyebrow="Administration"
          title={COPY.settingsPageTitle}
          idChip="/settings"
        />
        <ErrorBanner error={error} onRetry={refetch} message="Failed to load settings" />
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
      label:
        syncConfig.target_type === "s3" ? COPY.syncTargetS3BucketLabel : COPY.syncTargetPathLabel,
      placeholder:
        syncConfig.target_type === "s3"
          ? COPY.syncTargetS3BucketPlaceholder
          : COPY.syncTargetPathPlaceholder,
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
      <PageHeader
        eyebrow="Administration"
        title={COPY.settingsPageTitle}
        subtitle={COPY.settingsPageSubtitle}
      />

      {/* Settings tabs */}
      <div style={{ marginBottom: "var(--space-4)" }}>
        <TabBar
          tabs={[
            { id: "general", label: "General" },
            { id: "pipelines", label: "Pipelines" },
            { id: "storage", label: "Storage" },
            { id: "members", label: "Members" },
            { id: "integrations", label: "Integrations" },
          ]}
          activeTabId="general"
          onSelectTab={() => {}}
        />
      </div>

      {/* Config Tiles Grid */}
      <div className="grid grid-cols-2 gap-3">
        {/* Workspace */}
        <ConfigTile
          icon="schema"
          title={COPY.workspaceTileTitle}
          description={COPY.workspaceTileDescription}
          summary={[
            { label: "Name", value: String(workspaceConfig.display_name || COPY.workspaceUnnamed) },
            { label: "Path", value: String(workspaceConfig.path || COPY.notConfigured) },
          ]}
          onClick={() => setOpenSection("workspace")}
          data-testid="config-tile-workspace"
        />

        {/* LLM Provider */}
        <ConfigTile
          icon="pipeline"
          title={COPY.llmProviderTileTitle}
          description={COPY.llmProviderTileDescription}
          summary={[
            { label: "Provider", value: llmConfig.provider ? String(llmConfig.provider).charAt(0).toUpperCase() + String(llmConfig.provider).slice(1) : COPY.notConfigured },
            { label: "Model", value: String(llmConfig.model || COPY.notConfigured) },
          ]}
          onClick={() => setOpenSection("llm")}
          data-testid="config-tile-llm"
        />

        {/* Embedding Model */}
        <ConfigTile
          icon="layout"
          title={COPY.embeddingModelTileTitle}
          description={COPY.embeddingModelTileDescription}
          summary={[
            { label: "Model", value: String(embeddingConfig.model_name || COPY.notConfigured) },
            { label: "Dimensions", value: embeddingConfig.vector_dimensions ? COPY.embeddingDimensionsMeta(Number(embeddingConfig.vector_dimensions)) : COPY.notConfigured },
          ]}
          onClick={() => setOpenSection("embedding")}
          data-testid="config-tile-embedding"
        />

        {/* NLP Model */}
        <ConfigTile
          icon="component"
          title={COPY.nlpModelTileTitle}
          description={COPY.nlpModelTileDescription}
          summary={[
            { label: "Model", value: String(nlpConfig.model_name || COPY.notConfigured) },
          ]}
          onClick={() => setOpenSection("nlp")}
          data-testid="config-tile-nlp"
        />

        {/* Reference Sources */}
        <ConfigTile
          icon="data"
          title={COPY.referenceSourcesTileTitle}
          description={COPY.referenceSourcesTileDescription}
          summary={[
            { label: "Sources", value: COPY.referenceSourcesMeta(referenceSourcesCount) },
          ]}
          onClick={() => navigate({ to: "/app/reference/sources" })}
          data-testid="config-tile-reference-sources"
        />

        {/* Sync Target */}
        <ConfigTile
          icon="reload"
          title={COPY.syncTargetTileTitle}
          description={COPY.syncTargetTileDescription}
          summary={[
            { label: "Target", value: String(syncConfig.path || COPY.notConfigured) },
          ]}
          onClick={() => setOpenSection("sync")}
          data-testid="config-tile-sync"
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
