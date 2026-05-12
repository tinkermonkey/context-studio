import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Folder, Cpu, Layers, Type, Database, RefreshCw } from "lucide-react";
import { useConfig, useUpdateConfig } from "@/api/hooks/admin";
import { useToasts } from "@/components/ui/Toast";
import { Skeleton } from "@/components/ui/Skeleton";
import { ConfigTile } from "@/components/settings/ConfigTile";
import { EditConfigModal, type ConfigField } from "@/components/settings/EditConfigModal";

export const Route = createFileRoute("/app/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const navigate = useNavigate();
  const { toast } = useToasts();
  const { data: config, isLoading } = useConfig();
  const updateMutation = useUpdateConfig();

  const [openSection, setOpenSection] = useState<string | null>(null);

  const handleUpdateSection = async (section: string, updates: { [key: string]: unknown }) => {
    try {
      await updateMutation.mutateAsync({ section, data: { updates } });
      toast("success", `${section} settings updated`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to update settings";
      toast("error", message);
      throw error;
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: "var(--space-6)" }}>
        <div style={{ marginBottom: "var(--space-6)" }}>
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
      label: "Workspace Name",
      placeholder: "Enter workspace display name",
      required: true,
    },
    {
      key: "path",
      label: "Workspace Path",
      readOnly: true,
    },
  ];

  // LLM Provider section
  const llmConfig = sections.llm || {};
  const llmFields: ConfigField[] = [
    {
      key: "provider",
      label: "Provider",
      options: [
        { label: "Anthropic", value: "anthropic" },
        { label: "OpenAI", value: "openai" },
        { label: "Ollama", value: "ollama" },
      ],
      required: true,
    },
    {
      key: "model",
      label: "Model Name",
      placeholder: "e.g., claude-3-5-sonnet, gpt-4-turbo",
      required: true,
    },
    {
      key: "api_key",
      label: "API Key",
      type: "password",
      sensitive: true,
      placeholder: "Enter API key (write-only)",
    },
    ...(llmConfig.provider === "ollama"
      ? [
          {
            key: "base_url",
            label: "Base URL",
            type: "url",
            placeholder: "http://localhost:11434",
          } as ConfigField,
        ]
      : []),
  ];

  // Embedding Model section
  const embeddingConfig = sections.embedding || {};
  const embeddingFields: ConfigField[] = [
    {
      key: "model_name",
      label: "Model Name",
      placeholder: "e.g., sentence-transformers/all-MiniLM-L6-v2",
      required: true,
    },
    {
      key: "vector_dimensions",
      label: "Vector Dimensions",
      type: "number",
      readOnly: true,
    },
  ];

  // NLP Model section
  const nlpConfig = sections.nlp || {};
  const nlpFields: ConfigField[] = [
    {
      key: "model_name",
      label: "spaCy Model Name",
      placeholder: "e.g., en_core_web_sm",
      required: true,
    },
  ];

  // Sync Target section
  const syncConfig = sections.sync || {};
  const syncFields: ConfigField[] = [
    {
      key: "target_type",
      label: "Sync Target Type",
      options: [
        { label: "Local Path", value: "local" },
        { label: "S3", value: "s3" },
      ],
      required: true,
    },
    {
      key: "path",
      label: syncConfig.target_type === "s3" ? "S3 Bucket" : "Local Path",
      placeholder: syncConfig.target_type === "s3" ? "my-bucket" : "/path/to/sync",
    },
    ...(syncConfig.target_type === "s3"
      ? [
          {
            key: "aws_access_key_id",
            label: "AWS Access Key ID",
            type: "password",
            sensitive: true,
          } as ConfigField,
          {
            key: "aws_secret_access_key",
            label: "AWS Secret Access Key",
            type: "password",
            sensitive: true,
          } as ConfigField,
        ]
      : []),
  ];

  const referenceSourcesCount =
    (Array.isArray(sections.reference_sources) ? sections.reference_sources.length : 0) || 0;

  return (
    <div style={{ padding: "var(--space-6)" }} data-testid="settings-page">
      {/* Page Header */}
      <div className="page-head" style={{ marginBottom: "var(--space-6)" }}>
        <div>
          <h1>Settings</h1>
          <p>Configure application settings and external integrations</p>
        </div>
      </div>

      {/* Config Tiles Grid */}
      <div className="config-grid">
        {/* Workspace */}
        <ConfigTile
          icon={Folder}
          title="Workspace"
          description="Workspace configuration"
          summary={
            <span>
              {String(workspaceConfig.display_name || "Unnamed")}
              {workspaceConfig.path ? (
                <>
                  <br />
                  <span style={{ fontSize: "10px", color: "var(--canvas-fg-4)" }}>
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
          title="LLM Provider"
          description="Language model configuration"
          summary={
            <span>
              {String(llmConfig.provider || "Not configured")
                .charAt(0)
                .toUpperCase() + String(llmConfig.provider || "not").slice(1)}
              <br />
              <span style={{ fontSize: "10px", color: "var(--canvas-fg-4)" }}>
                {String(llmConfig.model || "Not configured")}
              </span>
            </span>
          }
          testid="config-tile-llm"
          onEdit={() => setOpenSection("llm")}
          isLoading={isLoading}
        />

        {/* Embedding Model */}
        <ConfigTile
          icon={Layers}
          title="Embedding Model"
          description="Vector embedding configuration"
          summary={
            <span>
              {String(embeddingConfig.model_name || "Not configured")}
              {embeddingConfig.vector_dimensions ? (
                <>
                  <br />
                  <span style={{ fontSize: "10px", color: "var(--canvas-fg-4)" }}>
                    {String(embeddingConfig.vector_dimensions)} dimensions
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
          title="NLP Model"
          description="Natural language processing"
          summary={
            <span>{String(nlpConfig.model_name || "Not configured")}</span>
          }
          testid="config-tile-nlp"
          onEdit={() => setOpenSection("nlp")}
          isLoading={isLoading}
        />

        {/* Reference Sources */}
        <ConfigTile
          icon={Database}
          title="Reference Sources"
          description="Manage knowledge sources"
          summary={<span>{referenceSourcesCount} source(s) configured</span>}
          testid="config-tile-reference-sources"
          onNavigate={() => navigate({ to: "/app/reference/sources" })}
          isLoading={isLoading}
        />

        {/* Sync Target */}
        <ConfigTile
          icon={RefreshCw}
          title="Sync Target"
          description="Remote synchronization"
          summary={
            <span style={{ color: syncConfig.path ? undefined : "var(--canvas-fg-3)" }}>
              {String(syncConfig.path || "Not configured")}
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
        title="Edit Workspace Settings"
        fields={workspaceFields}
        values={workspaceConfig}
        onSave={(updates) => handleUpdateSection("workspace", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "llm"}
        onClose={() => setOpenSection(null)}
        section="llmprovider"
        title="Edit LLM Provider Settings"
        fields={llmFields}
        values={llmConfig}
        onSave={(updates) => handleUpdateSection("llm", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "embedding"}
        onClose={() => setOpenSection(null)}
        section="embedding"
        title="Edit Embedding Model Settings"
        fields={embeddingFields}
        values={embeddingConfig}
        onSave={(updates) => handleUpdateSection("embedding", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "nlp"}
        onClose={() => setOpenSection(null)}
        section="nlp"
        title="Edit NLP Model Settings"
        fields={nlpFields}
        values={nlpConfig}
        onSave={(updates) => handleUpdateSection("nlp", updates)}
        isLoading={updateMutation.isPending}
      />

      <EditConfigModal
        open={openSection === "sync"}
        onClose={() => setOpenSection(null)}
        section="sync"
        title="Edit Sync Target Settings"
        fields={syncFields}
        values={syncConfig}
        onSave={(updates) => handleUpdateSection("sync", updates)}
        isLoading={updateMutation.isPending}
      />
    </div>
  );
}
