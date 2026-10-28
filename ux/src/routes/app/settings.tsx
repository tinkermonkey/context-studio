import { PageHeader, ConfigTile, TabBar, Field, TextInput } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { useConfig, useUpdateConfig } from "@/api/hooks/admin";
import { useChatStatus } from "@/api/hooks/chat";
import { useToasts } from "@/components/ui/Toast";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { McpConnectionPanel } from "@/components/settings/McpConnectionPanel";
import { COPY } from "./settings/copy";

export const Route = createFileRoute("/app/settings")({
  component: SettingsPage,
});

export function SettingsPage() {
  const { toast } = useToasts();
  const { data: config, isLoading, error, refetch } = useConfig();
  const updateMutation = useUpdateConfig();

  const { data: chatStatus } = useChatStatus();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState("general");
  const [chatModelError, setChatModelError] = useState<string | undefined>();

  const handleFieldBlur = async (section: string, key: string, value: string) => {
    try {
      await updateMutation.mutateAsync({ section, data: { updates: { [key]: value } } });
      toast("success", COPY.settingsUpdatedSuccess(section));
      return true;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : COPY.failedToSaveSettings;
      toast("error", errorMsg);
      return false;
    }
  };

  const handleChatModelBlur = async (value: string) => {
    const model = value.trim();
    if (!model) {
      setChatModelError(COPY.chatModelRequired);
      return;
    }
    if (model === String(config?.sections?.chat?.model ?? "")) return;
    if (await handleFieldBlur("chat", "model", model)) {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.chatStatus });
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
        <PageHeader eyebrow="settings" title={COPY.settingsPageTitle} idChip="/settings" />
        <ErrorBanner error={error} onRetry={refetch} message="Failed to load settings" />
      </div>
    );
  }

  const sections = config?.sections || {};
  const workspaceConfig = sections.workspace || {};
  const chatConfig = sections.chat || {};
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
            { id: "general", label: "General", count: 4 },
            { id: "storage", label: "Storage", count: 0 },
            { id: "members", label: "Members", count: 0 },
            { id: "integrations", label: "Integrations", count: 1 },
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

            <Field
              label={COPY.chatModelLabel}
              htmlFor="settings-chat-model"
              hint={chatModelError ? undefined : COPY.chatModelHint}
              error={chatModelError}
              errorId="settings-chat-model-error"
            >
              <TextInput
                id="settings-chat-model"
                data-testid="settings-chat-model-input"
                mono
                list="settings-chat-model-options"
                defaultValue={String(chatConfig.model || "")}
                placeholder={COPY.chatModelPlaceholder}
                error={Boolean(chatModelError)}
                aria-invalid={Boolean(chatModelError)}
                aria-describedby={chatModelError ? "settings-chat-model-error" : undefined}
                onChange={() => setChatModelError(undefined)}
                onBlur={(e) => handleChatModelBlur(e.target.value)}
              />
              <datalist id="settings-chat-model-options" data-testid="settings-chat-model-options">
                {(chatStatus?.available_models ?? []).map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
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
              summary={[{ label: "Reporting", value: "Disabled" }]}
              onClick={() => {}}
              data-testid="config-tile-telemetry"
            />
          </div>
        </div>
      )}

      {/* Integrations tab — mounted only when open, so its request is lazy */}
      {activeTab === "integrations" && <McpConnectionPanel />}
    </div>
  );
}
