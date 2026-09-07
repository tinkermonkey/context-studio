import { InspectorPanel, KVGrid, VersionPill, Chip } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";
import "./ConfigurationDrawer.css";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];

interface ConfigurationDrawerProps {
  configuration: PipelineConfigurationResponse | null;
}

export function ConfigurationDrawer({ configuration }: ConfigurationDrawerProps) {
  if (!configuration) return null;

  const paramEntries = configuration.parameters
    ? [
        { key: "temperature", value: String(configuration.parameters.temperature) },
        { key: "max_tokens", value: String(configuration.parameters.max_tokens) },
        { key: "top_p", value: String(configuration.parameters.top_p) },
      ]
    : [];

  return (
    <div
      className="configuration-drawer"
      data-testid={`configuration-drawer-${configuration.config_ref}-${configuration.version}`}
    >
      <InspectorPanel
        eyebrow="configuration"
        title={configuration.name ?? configuration.config_ref}
        id={`${configuration.config_ref}_v${configuration.version}`}
        version={configuration.version}
      >
        <InspectorPanel.Section title="Identity">
          <KVGrid
            rows={[
              { key: "Provider", value: configuration.provider ?? "—" },
              { key: "Model", value: configuration.model ?? "—" },
              {
                key: "Status",
                value: configuration.enabled ? (
                  <Chip variant="emerald">enabled</Chip>
                ) : (
                  <Chip variant="neutral">disabled</Chip>
                ),
              },
            ]}
          />
        </InspectorPanel.Section>

        {paramEntries.length > 0 && (
          <InspectorPanel.Section title="Parameters">
            <KVGrid rows={paramEntries} />
          </InspectorPanel.Section>
        )}

        <InspectorPanel.Section title="Metadata">
          <KVGrid
            rows={[
              { key: "Reference", value: configuration.config_ref },
              { key: "Version", value: <VersionPill>{configuration.version}</VersionPill> },
              { key: "Type", value: configuration.is_system ? "system" : "user" },
            ]}
          />
        </InspectorPanel.Section>
      </InspectorPanel>
    </div>
  );
}
