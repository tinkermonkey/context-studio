import { PageHeader, ConfigTile, TabBar, Field, TextInput, Select } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useConfig, useUpdateConfig } from "@/api/hooks/admin";
import { useToasts } from "@/components/ui/Toast";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { COPY } from "./settings/copy";

export const Route = createFileRoute("/app/settings")({
  component: SettingsPage,
});

export function SettingsPage() {
  const { toast } = useToasts();
  const { data: config, isLoading, error, refetch } = useConfig();
  const updateMutation = useUpdateConfig();

  const [activeTab, setActiveTab] = useState("general");

  const handleFieldBlur = async (section: string, key: string, value: string) => {
    try {
      await updateMutation.mutateAsync({ section, data: { updates: { [key]: value } } });
      toast("success", COPY.settingsUpdatedSuccess(section));
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : COPY.failedToSaveSettings;
      toast("error", errorMsg);
    }
  };

  if (isLoading) {
    return (
      <div data-testid="settings-page">
        <div style={{ marginBottom: "24px" }}>
          <div className="skeleton" style={{ height: 60, width: 400 }} />
          <div className="skeleton" style={{ height: 20, width: 300, marginTop: "8px" }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: "24px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 60 }} />
            ))}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 100 }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="settings-page">
        <PageHeader
          eyebrow="settings"
          title={COPY.settingsPageTitle}
          idChip="/settings"
        />
        <ErrorBanner error={error} onRetry={refetch} message="Failed to load settings" />
      </div>
    );
  }

  const sections = config?.sections || {};
  const workspaceConfig = sections.workspace || {};
  const llmConfig = sections.llm || {};
  const embeddingConfig = sections.embedding || {};

  return (
    <div data-testid="settings-page">
      {/* Page Header */}
      <PageHeader
        eyebrow="settings"
        title={COPY.settingsPageTitle}
        idChip="/settings"
        subtitle={COPY.settingsPageSubtitle}
      />

      {/* Settings tabs */}
      <div style={{ marginBottom: "var(--space-4)" }}>
        <TabBar
          tabs={[
            { id: "general", label: "General", count: 5 },
            { id: "pipelines", label: "Pipelines", count: 0 },
            { id: "storage", label: "Storage", count: 0 },
            { id: "members", label: "Members", count: 0 },
            { id: "integrations", label: "Integrations", count: 0 },
          ]}
          activeTabId={activeTab}
          onSelectTab={setActiveTab}
        />
      </div>

      {/* General tab — two-column layout */}
      {activeTab === "general" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 280px",
            gap: "24px",
            alignItems: "start",
          }}
        >
          {/* Left column: form fields */}
          <div
            data-testid="settings-general-form"
            style={{ display: "flex", flexDirection: "column", gap: "16px" }}
          >
            <Field label={COPY.workspaceDisplayNameLabel}>
              <TextInput
                data-testid="settings-workspace-name-input"
                defaultValue={String(workspaceConfig.display_name || "")}
                placeholder={COPY.workspaceDisplayNamePlaceholder}
                onBlur={(e) => handleFieldBlur("workspace", "display_name", e.target.value)}
              />
            </Field>

            <Field label={COPY.workspacePathLabel}>
              <TextInput
                data-testid="settings-workspace-path-input"
                mono
                defaultValue={String(workspaceConfig.path || "")}
                readOnly
              />
            </Field>

            <Field label={COPY.llmProviderLabel}>
              <Select
                data-testid="settings-llm-provider-select"
                defaultValue={String(llmConfig.provider || "")}
                onBlur={(e) => handleFieldBlur("llm", "provider", e.target.value)}
              >
                <option value="">{COPY.selectOptionPlaceholder}</option>
                <option value="anthropic">{COPY.llmProviderAnthropicOption}</option>
                <option value="openai">{COPY.llmProviderOpenAIOption}</option>
                <option value="ollama">{COPY.llmProviderOllamaOption}</option>
              </Select>
            </Field>

            <Field label={COPY.llmModelLabel}>
              <TextInput
                data-testid="settings-llm-model-input"
                defaultValue={String(llmConfig.model || "")}
                placeholder={COPY.llmModelPlaceholder}
                onBlur={(e) => handleFieldBlur("llm", "model", e.target.value)}
              />
            </Field>

            <Field label={COPY.embeddingModelNameLabel}>
              <TextInput
                data-testid="settings-embedding-model-input"
                defaultValue={String(embeddingConfig.model_name || "")}
                placeholder={COPY.embeddingModelNamePlaceholder}
                onBlur={(e) => handleFieldBlur("embedding", "model_name", e.target.value)}
              />
            </Field>
          </div>

          {/* Right column: summary ConfigTile cards */}
          <div
            data-testid="settings-summary-tiles"
            style={{ display: "flex", flexDirection: "column", gap: "12px" }}
          >
            <ConfigTile
              icon="hardDrive"
              title="Backups"
              description="Local database backup configuration"
              summary={[
                { label: "Status", value: "Not configured" },
                { label: "Last backup", value: "Never" },
              ]}
              onClick={() => {}}
              data-testid="config-tile-backups"
            />

            <ConfigTile
              icon="zap"
              title="Performance"
              description="Indexing and cache settings"
              summary={[
                { label: "Cache", value: "Enabled" },
                { label: "Index", value: "Up to date" },
              ]}
              onClick={() => {}}
              data-testid="config-tile-performance"
            />

            <ConfigTile
              icon="bell"
              title="Telemetry"
              description="Usage and error reporting"
              summary={[
                { label: "Reporting", value: "Disabled" },
              ]}
              onClick={() => {}}
              data-testid="config-tile-telemetry"
            />
          </div>
        </div>
      )}
    </div>
  );
}
