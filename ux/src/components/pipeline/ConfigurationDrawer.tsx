import { InspectorPanel, KVGrid, VersionPill } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";
import "./ConfigurationDrawer.css";

type ConfigurationResponse = components["schemas"]["ConfigurationResponse"];

interface ConfigurationDrawerProps {
  configuration: ConfigurationResponse | null;
}

export function ConfigurationDrawer({ configuration }: ConfigurationDrawerProps) {
  if (!configuration) return null;

  const configEntries = Object.entries(configuration.config || {}).map(([key, value]) => ({
    key,
    value: typeof value === "object" ? JSON.stringify(value, null, 2) : String(value),
  }));

  return (
    <div
      className="configuration-drawer"
      data-testid={`configuration-drawer-${configuration.config_ref}-${configuration.version}`}
    >
      <InspectorPanel
        eyebrow="configuration"
        title={configuration.config_ref}
        id={`${configuration.config_ref}_v${configuration.version}`}
        version={configuration.version}
      >
        <InspectorPanel.Section title="Configuration Data">
          {configEntries.length > 0 ? (
            <KVGrid rows={configEntries} />
          ) : (
            <div className="configuration-empty">No configuration data</div>
          )}
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Metadata">
          <KVGrid
            rows={[
              { key: "Reference", value: configuration.config_ref },
              { key: "Version", value: <VersionPill>{configuration.version}</VersionPill> },
            ]}
          />
        </InspectorPanel.Section>
      </InspectorPanel>
    </div>
  );
}
